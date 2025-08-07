# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""
Mitsuki interactions view framework.

Extends the creation of interaction responses with advanced features, such as
context loading, pagination, and timeouts.
"""

import interactions as ipy
import attrs

import asyncio
import contextlib
from copy import deepcopy
from urllib.parse import urlparse
from string import Template
from typing import Optional, Union, List, Any
from collections.abc import Callable, Awaitable

from mitsuki.logger import logger

__all__ = (
  "add_timeout",
  "reset_timeout",
  "force_timeout",
  "clear_timeout",
  "View",
  "TargetMixin",
)

_timeouts: dict[ipy.Snowflake, "Timeout"] = {}
_timeout_lock = asyncio.Lock()


async def add_timeout(ctx: ipy.InteractionContext, seconds: float, *, hide: bool = False):
  _ = await Timeout.add(ctx, seconds, hide=hide)


async def reset_timeout(ctx: ipy.InteractionContext):
  global _timeouts
  if timeout := _timeouts.get(ctx.message_id):
    if timeout.running:
      await timeout.reset()


async def force_timeout(ctx: ipy.InteractionContext):
  global _timeouts
  if timeout := _timeouts.get(ctx.message_id):
    if timeout.running:
      await timeout.timeout()


async def clear_timeout(ctx: ipy.InteractionContext):
  global _timeouts
  if timeout := _timeouts.get(ctx.message_id):
    if timeout.running:
      await timeout.clear()


def timeout_resetter[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Wrap a component callback to make it reset (refresh) its origin message's timeout when called.

  Args:
    callback: Callback coroutine with a ComponentContext argument
  """
  async def _callback[T](ctx: ipy.ComponentContext) -> T:
    result = await callback(ctx=ctx)
    await reset_timeout(ctx)
    return result

  return _callback


def timeout_clearer[T](callback: Awaitable[T]) -> Callable[[ipy.ComponentContext], Awaitable[T]]:
  """
  Wrap a component callback to make it clear (remove) its origin message's timeout when called.

  Args:
    callback: Callback coroutine with a ComponentContext argument
  """
  async def _callback[T](ctx: ipy.ComponentContext) -> T:
    result = await callback(ctx=ctx)
    await reset_timeout(ctx)
    return result

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
    self.task = asyncio.create_task(self._timeout_task)


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
    if view.ctx.message_id in _timeouts:
      await _timeouts[view.ctx.message_id].clear()

    # Adding a timeout with seconds=0 is equivalent to Timeout.clear()
    async with _timeout_lock:
      if seconds > 0.0:
        _timeouts[view.ctx.message_id] = timeout

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
  - `get_context()` to set the data, given attributes
  - `content()` to set the text message content
  - `embeds()` to set the message embeds
  - `components()` to set the message components, including v2 components

  Additional attributes can be added in your inherited view to provide
  information to the view content. These attributes would be set at instance
  creation, e.g. `MyView(ctx, target=target_user)`.
  """

  ctx: ipy.InteractionContext = attrs.field(kw_only=False)
  """Interaction context for this view."""

  _is_disabled: bool = attrs.field(init=False, repr=False)
  _is_preloaded: bool = attrs.field(init=False, repr=False)
  _send_kwargs: dict = attrs.field(init=False, repr=False)


  def __attrs_post_init__(self):
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
    for component in self.components():
      match component:
        case (ipy.Button(), ipy.BaseSelectMenu()):
          continue
        case ipy.ActionRow():
          continue
        case _:
          return True
    return self.content() is None and self.embeds() is None


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
      "client_avatar_url": self.client.user.avatar_url,

      "caller_id": self.caller.id,
      "caller_mention": self.caller.mention,
      "caller_username": self.caller.tag,
      "caller_name": self.caller.display_name,
      "caller_avatar_url": self.caller.avatar_url,
    }
    if guild := self.ctx.guild:
      result |= {
        "guild_id": guild.id,
        "guild_name": guild.name,
      }
      if icon := guild.icon:
        result |= {"guild_avatar_url": icon.as_url()}
    return result


  def get_context(self) -> dict[str, Any]:
    """
    Get context data for this view.

    Override this method to set this view's message context data. Define
    additional attributes in your inherited view to include additional data.

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
    be set when using v2 components.

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
    be set when using v2 components.

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
    embeds must not be set when using v2 components.

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
    shown via a file component linking to `attachment://<filename>`.

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

    if self.has_origin:
      send = self.ctx.edit_origin
    elif getattr(self.ctx, "editing_origin", False):
      send = self.ctx.edit_origin
    else:
      send = self.ctx.send

    message = await send(ephemeral=ephemeral, allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs)

    if timeout and timeout > 0 and len(send_kwargs["components"]) > 0:
      await add_timeout(self.ctx, timeout, hide=hide_on_timeout)

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

    if send_kwargs != self._send_kwargs:
      message = await self.ctx.edit(**send_kwargs)

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

    new_components = []
    old_components = self.sent_components
    if not old_components or len(old_components) == 0:
      return

    for old_component in old_components:
      add_component = old_component

      if isinstance(old_component, ipy.ActionRow):
        action_row = []

        for c in old_component.components:
          if isinstance(c, ipy.BaseSelectMenu) or (isinstance(c, ipy.Button) and c.style != ipy.ButtonStyle.LINK):
            if hide:
              continue
            c.disabled = True
          action_row.append(c)

        if len(action_row) == 0:
          continue
        add_component = ipy.ActionRow(*action_row)

      elif isinstance(old_component, ipy.Button):
        if not old_component.style == ipy.ButtonStyle.LINK:
          old_component.disabled = True

      elif isinstance(old_component, ipy.BaseSelectMenu):
        old_component.disabled = True

      elif (
        isinstance(old_component, ipy.SectionComponent)
        and isinstance(old_component.accessory, ipy.Button)
      ):
        if hide:
          add_component = ipy.TextDisplayComponent("\n".join([c.content for c in old_component.components]))
        else:
          old_component.accessory.disabled = True

      new_components.append(add_component)

    if len(new_components) == 0 and self.is_components_v2:
      raise ValueError("Cannot disable View with hide=True resulting in an empty message")

    try:
      self._is_disabled = True
      await self.ctx.edit(components=new_components)
    except ipy.errors.HTTPException:
      self._is_disabled = False
      raise
    self._send_kwargs["components"] = new_components


  def _generate(self):
    context = self.get_master_context() | self.get_context()

    if content := self.content():
      content = Template(content).safe_substitute(**context)

    if embeds := self.embeds():
      for embed in embeds:
        embed = _subst_embed(embed)

    if components := self.components():
      for idx, component in enumerate(components):
        components[idx] = _subst_component(component, context)

    return {
      "content": content,
      "embeds": embeds,
      "components": components,
      "files": self.files(),
    }


@attrs.define(slots=False)
class TargetMixin:
  """
  View mixin for commands with a target user.

  Inherit this in your View object before `View` to implement this mixin.
  """

  target: Union[ipy.User, ipy.Member] = attrs.field(kw_only=True)


  def set_target(self, target_user: Optional[Union[ipy.User, ipy.Member]] = None) -> "View":
    """
    Set the target user for this view.

    Args:
      target_user: Target user, or the interaction caller if unset

    Returns:
      This instance of View
    """
    self.target = target_user or self.caller
    return self


  def get_master_context(self) -> dict[str, Any]:
    return super().get_master_context() | {
      "target_id": self.target.id,
      "target_mention": self.target.mention,
      "target_username": self.target.tag,
      "target_name": self.target.display_name,
      "target_avatar_url": self.target.avatar_url,
    }


def _subst[T](data: dict, target: Optional[T] = None) -> Optional[T]:
  if isinstance(target, str):
    return Template(target).safe_substitute(**data)
  elif target:
    return target
  return None


def _subst_component(component: ipy.BaseComponent, context: dict):
  result = deepcopy(component)

  match result:
    case ipy.ActionRow():
      result.components = [_subst_component(c, context) for c in result.components]

    case ipy.Button():
      result.label = _subst(context, result.label)
      result.url = _subst(context, result.url)

    case ipy.BaseSelectMenu():
      # ipy.(String|User|Role|Mentionable|Channel)SelectMenu
      result.placeholder = _subst(context, result.placeholder)

    case ipy.ContainerComponent():
      result.components = [_subst_component(c, context) for c in result.components]

    case ipy.TextDisplayComponent():
      result.content = _subst(context, result.content)

    case ipy.SectionComponent():
      # ThumbnailComponent is also handled here, as it can only exist inside a SectionComponent
      # If the thumbnail is an invalid url, this component would be rerendered as a text display
      if isinstance(result.accessory, ipy.ThumbnailComponent):
        if valid_media_url := _get_valid_url(_subst(result.accessory.media.url)):
          # Valid URL, render as SectionComponent
          result.accessory.media = ipy.UnfurledMediaItem(valid_media_url)
          result.components = [_subst_component(c, context) for c in result.components]
        else:
          # Invalid URL, render as TextDisplayComponent
          result = ipy.TextDisplayComponent(
            "\n".join([c.content for c in result.components])
          )
          result.content = _subst(context, result.content)
      else:
        # Button accessory, render as SectionComponent
        result.accessory = _subst_component(result.accessory, context)
        result.components = [_subst_component(c, context) for c in result.components]
    
    case _:
      # (ipy.SeparatorComponent, ipy.FileComponent, ...)
      pass

  return result


def _subst_embed(embed: ipy.Embed, context: dict):
  result = ipy.Embed()

  if embed.author:
    result.set_author(
      name=_subst(context, embed.author.name),
      url=_subst(context, embed.author.url),
      icon_url=_subst(context, embed.author.icon_url),
    )

  if embed.title:
    result.title = _subst(context, embed.title)

  if embed.description:
    result.description = _subst(context, embed.description)

  if embed.url:
    result.url = _get_valid_url(_subst(context, embed.url))

  if embed.thumbnail:
    if valid_url := _get_valid_url(_subst(context, embed.thumbnail.url)):
      result.set_thumbnail(valid_url)

  if embed.image:
    if valid_url := _get_valid_url(_subst(context, embed.image.url)):
      result.set_image(valid_url)

  if embed.footer:
    result.set_footer(
      text=_subst(embed.footer.text),
      icon_url=_get_valid_url(_subst(embed.footer.icon_url)),
    )

  if embed.color:
    result.color = _subst(context, embed.color)

  for field in embed.fields:
    result.add_field(
      name=_subst(field.name),
      value=_subst(field.value),
      inline=field.inline,
    )


def _get_valid_url(url: str) -> Optional[str]:
  parsed = urlparse(url)
  return (
    parsed.scheme in ("http", "https", "ftp", "ftps") and
    len(parsed.netloc) > 0
  )