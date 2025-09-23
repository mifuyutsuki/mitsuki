# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy
import attrs
import uuid
import re

import asyncio
import contextlib
from copy import deepcopy, copy
from urllib.parse import urlparse
from string import Template
from typing import Optional, Union, List, Any
from collections.abc import Callable, Awaitable

from mitsuki.utils import escape_text
from mitsuki.logger import logger
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import utils

__all__ = (
  "add_timeout",
  "reset_timeout",
  "force_timeout",
  "clear_timeout",
  "timeout_resetter",
  "timeout_clearer",
  "View",
  "TargetMixin",
)


_timeouts: dict[ipy.Snowflake, "Timeout"] = {}
_timeout_lock = asyncio.Lock()


async def add_timeout(view: "View", seconds: float, *, hide: bool = False):
  _ = await Timeout.add(view, seconds, hide=hide)


async def reset_timeout(message_id: ipy.Snowflake):
  global _timeouts
  if timeout := _timeouts.get(message_id):
    if timeout.running:
      await timeout.reset()


async def force_timeout(message_id: ipy.Snowflake):
  global _timeouts
  if timeout := _timeouts.get(message_id):
    if timeout.running:
      await timeout.timeout()


async def clear_timeout(message_id: ipy.Snowflake):
  global _timeouts
  if timeout := _timeouts.get(message_id):
    if timeout.running:
      await timeout.clear()


def timeout_resetter[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Make a component reset (refresh) its attached message's timeout when invoked.

  Use this function as a decorator on the target component callback.

  Args:
    callback: Component callback coroutine
  """
  async def _callback[T](self, ctx: ipy.ComponentContext, *args, **kwargs) -> T:
    result = await callback(self, ctx=ctx, *args, **kwargs)
    await reset_timeout(ctx.message_id)
    return result

  return _callback


def timeout_clearer[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Make a component clear (remove) its attached message's timeout when invoked.

  Use this function as a decorator on the target component callback.

  Args:
    callback: Component callback coroutine
  """
  async def _callback[T](self, ctx: ipy.ComponentContext) -> T:
    result = await callback(self, ctx=ctx)
    await clear_timeout(ctx.message_id)
    return result

  return _callback


def timeout_invoker[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Make a component trigger its attached message's timeout *after* invoked.

  Use this function as a decorator on the target component callback. The
  timeout action is only done after the main callback runs without errors.
  If invocation before the callback is needed, use timeout_preinvoker().

  Args:
    callback: Component callback coroutine
  """
  async def _callback[T](self, ctx: ipy.ComponentContext) -> T:
    result = await callback(self, ctx=ctx)
    await force_timeout(ctx.message_id)
    return result

  return _callback


def timeout_preinvoker[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Make a component trigger its attached message's timeout *before* invoked.

  Use this function as a decorator on the target component callback. The
  timeout action is done before the main callback executes. If invocation
  after the callback is needed, use timeout_invoker().

  Args:
    callback: Component callback coroutine
  """
  async def _callback[T](self, ctx: ipy.ComponentContext) -> T:
    await force_timeout(ctx.message_id)
    return await callback(self, ctx=ctx)

  return _callback


@attrs.define(kw_only=True, slots=False)
class Timeout:
  view: "View"
  duration: float
  hide: bool = attrs.field(default=False)

  running: bool = attrs.field(init=False)
  task: asyncio.Task = attrs.field(init=False)
  reset_event: asyncio.Event = attrs.field(init=False)


  def __attrs_post_init__(self):
    self.running = True
    self.reset_event = asyncio.Event()
    self.task = asyncio.create_task(self._timeout_task())


  @property
  def ctx(self):
    return self.view.ctx


  async def _timeout_task(self):
    while self.running:
      try:
        _ = await asyncio.wait_for(self.reset_event.wait(), timeout=self.duration)
      except (TimeoutError, asyncio.CancelledError):
        self.running = False
        if not self.view.is_disabled:
          with contextlib.suppress(ipy.errors.HTTPException):
            await self.view.disable(hide=self.hide)
      else:
        self.reset_event.clear()

    with contextlib.suppress(asyncio.CancelledError):
      await self.clear()


  @classmethod
  async def add(cls, view: "View", seconds: float, *, hide: bool = False):
    global _timeouts, _timeout_lock

    if not view.is_sent:
      raise ValueError("Cannot add timeout from an unsent interaction")
    if seconds < 0.0:
      raise ValueError(f"Timeout cannot be less than zero ('{seconds}' was given)")

    timeout = cls(view=view, duration=seconds, hide=hide)
    if view.message.id in _timeouts:
      await _timeouts[view.message.id].clear()

    # Adding a timeout with seconds=0 is equivalent to Timeout.clear()
    async with _timeout_lock:
      if seconds > 0.0:
        _timeouts[view.message.id] = timeout

    return timeout


  async def reset(self):
    self.reset_event.set()


  async def timeout(self):
    global _timeouts, _timeout_lock

    async with _timeout_lock:
      if self.ctx.id in _timeouts:
        _ = _timeouts.pop(self.ctx.id)

    # By immediately calling cancel(), the timeout task will run the timeout
    # action, as the task loop catches CancelledError.
    self.task.cancel()


  async def clear(self):
    global _timeouts, _timeout_lock

    async with _timeout_lock:
      if self.ctx.id in _timeouts:
        _ = _timeouts.pop(self.ctx.id)

    # By disabling `running` and setting the reset event, the timeout task will
    # not run the timeout action, as no TimeoutError/CancelledError is raised.
    if self.running:
      self.running = False
      self.reset_event.set()

    self.task.cancel()


@attrs.define(slots=False)
class View:
  """
  A Discord message response view.

  Inherit this object with `attrs.define(slots=False)` to create a new message
  view, and override the following methods:
  - `get_context()` to set the data, given attributes (default: `{}`)
  - `content()` to set the text message content (default: `None`)
  - `embeds()` to set the message embeds (default: `None`)
  - `components()` to set the message components, including v2 components
    (default: `None`)

  Additional attributes can be added in your inherited view to provide
  information to the view content. These attributes would be set at instance
  creation, e.g. `MyView(ctx, target=target_user)`.
  """

  ctx: ipy.InteractionContext = attrs.field(kw_only=False)
  """Interaction context for this view."""

  _message: Optional[ipy.Message] = attrs.field(init=False, repr=False)
  _is_disabled: bool = attrs.field(init=False, repr=False)
  _is_preloaded: bool = attrs.field(init=False, repr=False)
  _send_kwargs: dict = attrs.field(init=False, repr=False)


  def __attrs_post_init__(self):
    self._message = None
    self._is_disabled = False
    self._is_preloaded = False
    self._send_kwargs = None


  @property
  def client(self) -> ipy.Client:
    """Mitsuki client instance provided by the interaction."""
    return self.ctx.client


  @property
  def caller(self) -> Union[ipy.Member, ipy.User]:
    """The user who called the interaction."""
    return self.ctx.author


  @property
  def message(self) -> Optional[ipy.Message]:
    """Message instance that was sent to Discord, if any."""
    return self._message


  @property
  def sent_components(self) -> Optional[List[ipy.BaseComponent]]:
    """Components that have been sent, if any."""
    if self._send_kwargs:
      return self._send_kwargs.get("components")


  @property
  def has_origin(self) -> bool:
    """Whether this interaction has an origin message."""
    return hasattr(self.ctx, "edit_origin") and asyncio.iscoroutinefunction(self.ctx.edit_origin)


  @property
  def is_sent(self) -> bool:
    """Whether this view has been sent."""
    return self.ctx.responded


  @property
  def is_disabled(self) -> bool:
    """Whether this view is disabled, i.e. interactable non-link components are disabled or hidden."""
    return self._is_disabled


  @property
  def is_preloaded(self) -> bool:
    """Whether this view was preloaded using View.preload()"""
    return self._is_preloaded


  @property
  def is_components_v2(self) -> bool:
    """Whether this view uses v2 components."""
    components = self.components()
    if not components:
      return False

    for component in components:
      match component:
        case (ipy.Button(), ipy.BaseSelectMenu()):
          continue
        case ipy.ActionRow():
          continue
        case _:
          return True
    return self.content() is None and self.embeds() is None and len(components) > 0


  def get_master_context(self) -> dict[str, Any]:
    """
    Get interaction context data for this view, including information on the
    caller and this application.

    The output of this method is provided automatically from the interaction
    data and should not be overriden. The output would be used to string-
    substitute text in the message content, including its text content, embeds,
    and components using `string.Template`.

    Returns:
      Dictionary of interaction context data
    """
    result = {
      "client_id": self.client.user.id,
      "client_mention": self.client.user.mention,
      "client_username": self.client.user.tag,
      "client_name": self.client.user.display_name,
      "client_name_esc": escape_text(self.client.user.display_name),
      "client_avatar_url": self.client.user.avatar_url,

      "caller_id": self.caller.id,
      "caller_mention": self.caller.mention,
      "caller_username": self.caller.tag,
      "caller_name": self.caller.display_name,
      "caller_name_esc": escape_text(self.caller.display_name),
      "caller_avatar_url": self.caller.avatar_url,
    }
    if guild := self.ctx.guild:
      result |= {
        "guild_id": guild.id,
        "guild_name": guild.name,
        "guild_name_esc": escape_text(guild.name),
      }
      if icon := guild.icon:
        result |= {"guild_avatar_url": icon.as_url()}
    return result


  def get_context(self) -> dict[str, Any]:
    """
    Get context data for this view.

    Override this method to set this view's message context data. Define
    additional attributes in your inherited view to include additional data.
    By default, returns an empty dict `{}`.

    The output would be used to string-substitute text in the message content,
    including its text content, embeds, and components using `string.Template`.

    Returns:
      Dictionary of view context data
    """
    return {}


  def content(self) -> Optional[str]:
    """
    Generate the message content of this view.

    Override this method to set this view's message content. This method cannot
    be set when using v2 components. By default, returns `None`.

    Text in this message would be string-substituted using `string.Template` on
    sending using data given by `View.get_master_context()` and
    `View.get_context()`.

    Returns:
      Message text content, or `None` to leave unset
    """
    return None


  def embeds(self) -> Optional[List[ipy.Embed]]:
    """
    Generate message embeds for this view.

    Override this method to set this view's message embeds. This method cannot
    be set when using v2 components. By default, returns `None`.

    Text in this message would be string-substituted using `string.Template` on
    sending using data given by `View.get_master_context()` and
    `View.get_context()`.

    Returns:
      List of message embeds, or `None` to leave unset
    """
    return None


  def components(self) -> Optional[List[ipy.BaseComponent]]:
    """
    Generate message components for this view.

    Override this method to set this view's message components. Content and
    embeds must not be set when using v2 components. By default, returns
    `None`.

    Text in this message would be string-substituted using `string.Template` on
    sending using data given by `View.get_master_context()` and
    `View.get_context()`.

    Returns:
      List of message components, or `None` to leave unset
    """
    return None


  def files(self) -> Optional[List[ipy.UPLOADABLE_TYPE]]:
    """
    Generate files to send for this view.

    Override this method to set this view's file attachments. The interaction
    must be deferred before sending. When using components v2, files are only
    shown via a file component linking to `attachment://<filename>`. By
    default, returns `None`.

    Returns:
      List of files to attach, or `None` to leave unset
    """
    return None


  def preload(self) -> None:
    """
    Preload the view with context data.

    Text in this message would be string-substituted using `string.Template` on
    sending using data given by `View.get_master_context()` and
    `View.get_context()`.
    """
    self._send_kwargs = self._generate()
    self._is_preloaded = True


  async def send(
    self,
    *,
    mention_users: Optional[List[ipy.BaseUser]] = None,
    timeout: Optional[float] = None,
    hide_on_timeout: bool = False,
    ephemeral: bool = False,
  ) -> ipy.Message:
    """
    Send this view as a message.

    Note that the ephemeral status of this message is overriden by deferring this interaction.

    Args:
      mention_users: Users to mention with ping in the message
      timeout: Timeout duration of this view, or leave unset to post a persistent message
      hide_on_timeout: Whether to hide interactable non-link components when timed out
      ephemeral: Whether the message should only be viewable by the caller

    Returns:
      Sent message object

    Raises:
      HTTPException: Could not send the message to Discord
    """
    send_kwargs = self._send_kwargs or self._generate()
    mention_users = mention_users or []

    if self.ctx.deferred:
      message = await self.ctx.send(allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs)
    elif getattr(self.ctx, "editing_origin", False):
      message = await self.ctx.edit_origin(allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs)
    elif self.has_origin:
      message = await self.ctx.edit_origin(allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs)
    else:
      message = await self.ctx.send(
        ephemeral=ephemeral, allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs
      )

    self._message = message
    self._send_kwargs = send_kwargs

    if timeout and timeout > 0 and len(send_kwargs["components"]) > 0:
      await add_timeout(self, timeout, hide=hide_on_timeout)
    await self._post_send(
      mention_users=mention_users, timeout=timeout, hide_on_timeout=hide_on_timeout, ephemeral=ephemeral
    )

    return message


  async def edit(self):
    """
    Edit the message sent by this view using new data, e.g. updated attributes.

    If this view has a timeout, the timeout would be reset (refreshed).

    Returns:
      Edited message object

    Raises:
      HTTPException: Could not edit the message in Discord
    """
    send_kwargs = self._generate()

    if send_kwargs:
      message = await self.ctx.edit(**send_kwargs)
      self._send_kwargs = send_kwargs
      self._message = message

    await reset_timeout(self.ctx)
    return message


  async def disable(self, hide: bool = False) -> None:
    """
    Disable this view by disabling or hiding interactable non-link components (buttons and select menus).

    Args:
      hide: Whether to hide instead of disabling the interactable components

    Raises:
      ValueError: Disabling would create an empty message due to `hide=True`
      HTTPException: Could not edit the message in Discord
    """
    if not self.is_sent:
      return

    old_components = self.sent_components
    if not old_components or len(old_components) == 0:
      return

    new_components = utils.disable_components(old_components, hide=hide)
    if len(new_components) == 0 and self.is_components_v2:
      raise ValueError("Cannot disable View with hide=True resulting in an empty message")

    if self.message:
      allowed_mentions = ipy.AllowedMentions(users=self.message._mention_ids, roles=self.message._mention_roles)
    else:
      allowed_mentions = ipy.AllowedMentions()

    try:
      self._is_disabled = True
      message = await self.ctx.edit(components=new_components, allowed_mentions=allowed_mentions)
    except ipy.errors.HTTPException:
      self._is_disabled = False
      raise
    self._send_kwargs["components"] = new_components
    self._message = message


  async def _post_send(self, *args, **kwargs):
    pass


  def _generate(self):
    context = self.get_master_context() | self.get_context()

    if content := self.content():
      content = utils.subst(context, content)

    if embeds := self.embeds():
      for embed in embeds:
        embed = utils.subst_embed(embed, context)

    if components := self.components():
      components = utils.subst_components(components, context)

    return {
      "content": content,
      "embeds": embeds,
      "components": components,
      "files": self.files(),
    }