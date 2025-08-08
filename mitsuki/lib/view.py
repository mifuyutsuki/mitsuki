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
import uuid
import re

import asyncio
import contextlib
from copy import deepcopy, copy
from urllib.parse import urlparse
from string import Template
from typing import Optional, Union, List, Any
from collections.abc import Callable, Awaitable

from mitsuki.logger import logger
from mitsuki.lib.emoji import AppEmoji, get_emoji

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
  Wrap a component callback to make it reset (refresh) its origin message's timeout when called.

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
  Wrap a component callback to make it clear (remove) its origin message's timeout when called.

  Args:
    callback: Component callback coroutine
  """
  async def _callback[T](self, ctx: ipy.ComponentContext) -> T:
    result = await callback(self, ctx=ctx)
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
    mention_users = mention_users or []

    if self.has_origin:
      send = self.ctx.edit_origin
    elif getattr(self.ctx, "editing_origin", False):
      send = self.ctx.edit_origin
    else:
      send = self.ctx.send

    message = await send(ephemeral=ephemeral, allowed_mentions=ipy.AllowedMentions(users=mention_users), **send_kwargs)
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

    new_components = _disable_components(old_components, hide=hide)
    if len(new_components) == 0 and self.is_components_v2:
      raise ValueError("Cannot disable View with hide=True resulting in an empty message")

    try:
      self._is_disabled = True
      await self.ctx.edit(components=new_components, allowed_mentions=ipy.AllowedMentions())
    except ipy.errors.HTTPException:
      self._is_disabled = False
      raise
    self._send_kwargs["components"] = new_components


  async def _post_send(self, *args, **kwargs):
    pass


  def _generate(self):
    context = self.get_master_context() | self.get_context()

    if content := self.content():
      content = Template(content).safe_substitute(**context)

    if embeds := self.embeds():
      for embed in embeds:
        embed = _subst_embed(embed)

    if components := self.components():
      components = _subst_components(components, context)

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


@attrs.define(slots=False)
class SectionPaginatorMixin:
  entries_data: list[dict[str, Any]] = attrs.field(kw_only=True, factory=list)
  entries_per_page: int = attrs.field(kw_only=True, default=5)
  page_index: int = attrs.field(kw_only=True, default=0)

  id: uuid.UUID = attrs.field(init=False)


  def __attrs_post_init__(self):
    super().__attrs_post_init__()
    self.id = uuid.uuid4()


  def components_on_empty(self) -> List[ipy.BaseComponent]:
    return self.components()


  def get_master_context(self) -> dict[str, Any]:
    return super().get_master_context() | {"uuid": self.id}


  def get_pages_context(self) -> list[dict[str, Any]]:
    return []


  def section(self) -> List[Union[ipy.SectionComponent, ipy.TextDisplayComponent]]:
    raise NotImplementedError("Section format is required to use this paginator")


  async def _post_send(self, timeout: Optional[float] = None, **kwargs):
    if timeout and timeout > 0:
      self.client.add_component_callback(
        ipy.ComponentCommand(
          name=f"Paginator:{self.id}",
          callback=self._nav_callback,
          listeners=[
            f"{self.id}|first",
            f"{self.id}|prev",
            f"{self.id}|next",
            f"{self.id}|last",
            f"{self.id}|pageno",
          ],
        )
      )


  async def _nav_callback(self, ctx: ipy.ComponentContext):
    match custom_id := ctx.custom_id.split("|")[-1]:
      case "first":
        self.page_index = 0
      case "prev":
        self.page_index = max(0, self.page_index - 1)
      case "next":
        self.page_index += 1
      case "last":
        self.page_index = -1
      case "selector":
        # TODO: "Go to page" modal
        pass
      case _:
        raise ValueError("Unexpected paginator custom id action: '{}'".format(custom_id))

    edit_kwargs = self._generate()
    message = await ctx.edit_origin(**edit_kwargs)
    await reset_timeout(message.id)
    self._send_kwargs = edit_kwargs
    self._message = message


  def _generate(self):
    if not self.is_components_v2:
      raise ValueError("Components v2 is required by this paginator")

    pages_context = self.get_pages_context()
    context = self.get_master_context() | self.get_context()

    if len(pages_context) == 0:
      components = _subst_components(self.components_on_empty(), context)
    else:
      pages = 1 + int((len(pages_context) - 1) / self.entries_per_page)

      # This pattern allows for _nav_callback() to set page_index = -1
      # without knowing len(pages_context)
      if not (0 <= self.page_index < len(pages_context)):
        self.page_index = pages - 1

      context |= {
        "page": self.page_index + 1,
        "pages": pages,
      }
      components = _subst_components(
        self.components(), context,
        pages_context=pages_context,
        page_index=self.page_index,
        per_page=self.entries_per_page,
        section=self.section()
      )

    # Stub components have been converted and context'd past this point
    return {"components": components, "files": self.files()}


class StubComponent:
  def subst(self, context: dict[str, Any], *args, **kwargs) -> List[ipy.BaseComponent]:
    raise NotImplementedError


class PaginatorContentStub(StubComponent):
  def subst(
    self,
    context: dict[str, Any],
    *,
    pages_context: list[dict[str, Any]],
    page_index: int,
    per_page: int,
    section: List[ipy.BaseComponent]
  ) -> List[ipy.BaseComponent]:
    results = []

    for page_context in pages_context[per_page * page_index : per_page * (page_index + 1)]:
      this_context = context | page_context
      for c in section:
        if isinstance(c, StubComponent):
          raise ValueError("Cannot nest a placeholder component inside another placeholder component")

        add_c = _subst_component(c, this_context)
        if isinstance(add_c, list):
          results.extend(add_c)
        elif add_c:
          results.append(add_c)
      results.append(ipy.SeparatorComponent(divider=True))

    return results


class PaginatorNavStub(StubComponent):
  def subst(self, context: dict[str, Any], **kwargs) -> List[ipy.BaseComponent]:
    id, page, pages = context["uuid"], int(context["page"]), int(context["pages"])

    return [ipy.ActionRow(
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_FIRST),
        custom_id="{}|first".format(id),
        disabled=page <= 1
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_PREVIOUS),
        custom_id="{}|prev".format(id),
        disabled=page <= 1
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        label="{}/{}".format(page, pages),
        custom_id="{}|selector".format(id),
        disabled=True # TODO: pages < 4
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_NEXT),
        custom_id="{}|next".format(id),
        disabled=page >= pages
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_LAST),
        custom_id="{}|last".format(id),
        disabled=page >= pages
      ),
    )]


def _disable_components(components: List[ipy.BaseComponent], hide: bool = False) -> List[ipy.BaseComponent]:
  new_components = []

  for c in components:
    if add_c := _disable_component(c, hide=hide):
      new_components.append(add_c)

  return new_components


def _disable_component(component: ipy.BaseComponent, hide: bool = False) -> Optional[ipy.BaseComponent]:
  result = component
  match result:
    case ipy.ActionRow():
      result.components = _disable_components(result.components, hide=hide)
      if len(result.components) == 0:
        result = None  

    case ipy.BaseSelectMenu():
      if hide:
        result = None
      else:
        result.disabled = True

    case ipy.Button():
      if result.style == ipy.ButtonStyle.LINK:
        pass
      elif hide:
        result = None
      else:
        result.disabled = True

    case ipy.ContainerComponent():
      result.components = _disable_components(result.components, hide=hide)

    case ipy.SectionComponent():
      if isinstance(result.accessory, ipy.Button):
        if hide:
          result = ipy.TextDisplayComponent("\n".join([c.content for c in result.components]))
        else:
          result.accessory.disabled = True

    case _:
      pass
  
  return result


def _subst[T](data: dict, target: Optional[T] = None) -> Optional[T]:
  if isinstance(target, str):
    return Template(target).safe_substitute(**data)
  elif target:
    return target
  return None


def _subst_components(components: list, context: dict[str, Any], **kwargs):
  results = []

  for c in components:
    add_c = _subst_component(c, context, **kwargs)

    if isinstance(add_c, list):
      results.extend(add_c)
    elif add_c:
      results.append(add_c)

  return results


def _subst_component(component, context: dict, **kwargs):
  try:
    result = copy(component)
  except Exception:
    result = component

  match result:
    case ipy.ActionRow():
      result.components = _subst_components(result.components, context, **kwargs)

    case ipy.Button():
      result.label = _subst(context, result.label)
      result.url = _subst(context, result.url)
      result.custom_id = _subst(context, result.custom_id)

    case ipy.BaseSelectMenu():
      # ipy.(String|User|Role|Mentionable|Channel)SelectMenu
      result.placeholder = _subst(context, result.placeholder)
      result.custom_id = _subst(context, result.custom_id)

    case ipy.ContainerComponent():
      result.components = _subst_components(result.components, context, **kwargs)

    case ipy.TextDisplayComponent():
      result.content = _subst(context, result.content)

    case ipy.MediaGalleryComponent():
      result.items = _subst_components(result.items, context, **kwargs)

    case ipy.MediaGalleryItem():
      if valid_media_item := _subst_component(result.media, context, **kwargs):
        result.media = valid_media_item
        result.description = _subst(context, result.description)
      else:
        result = None

    case ipy.ThumbnailComponent():
      if valid_media_item := _subst_component(result.media, context, **kwargs):
        result.media = valid_media_item
        result.description = _subst(context, result.description)
      else:
        result = None

    case ipy.UnfurledMediaItem():
      if valid_media_url := _get_valid_url(_subst(context, result.url)):
        result.url = valid_media_url
      else:
        result = None

    case ipy.SeparatorComponent():
      pass

    case ipy.FileComponent():
      pass

    case ipy.SectionComponent():
      if valid_accessory := _subst_component(result.accessory, context, **kwargs):
        result.components = _subst_components(result.components, context, **kwargs)
        result.accessory = valid_accessory
      else:
        result = ipy.TextDisplayComponent("\n".join([c.content for c in result.components]))

    case StubComponent():
      result = result.subst(context, **kwargs)

    case _:
      # (ipy.SeparatorComponent, ipy.FileComponent, ...)
      result = None

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


def _is_valid_url(url: str) -> bool:
  parsed = urlparse(url)
  return parsed.scheme in ("http", "https", "ftp", "ftps") and len(parsed.netloc) > 0


def _get_valid_url(url: str) -> Optional[str]:
  if _is_valid_url(url):
    return url