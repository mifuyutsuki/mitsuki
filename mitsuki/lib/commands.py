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
Mitsuki commands framework. Eases creation of stateful commands with the
Mitsuki messages library (mitsuki.lib.messages).
"""

from mitsuki import bot
from mitsuki.lib import messages
from mitsuki.lib.paginators import Paginator, SelectionPaginator
from mitsuki.lib.userdata import new_session

from attrs import define, asdict as _asdict
from typing import Optional, Union, List, Dict, Any, Callable, ParamSpec, TypeVar
from collections.abc import Awaitable
from enum import StrEnum
from asyncio import iscoroutinefunction, Lock

from interactions import (
  Client,
  Snowflake,
  User,
  Member,
  InteractionContext,
  ComponentContext,
  AutocompleteContext,
  Message,
  StringSelectOption,
  ActionRow,
  BaseComponent,
  spread_to_rows,
  MessageFlags,
)
from sqlalchemy.ext.asyncio import AsyncSession
import re

__all__ = (
  "userlock",
  "is_userlocked",
  "CustomID",
  "AsDict",
  "Caller",
  "Target",
  "Command",
  "ReaderCommand",
  "WriterCommand",
  "TargetMixin",
  "MultifieldMixin",
  "AutocompleteMixin",
)


P = ParamSpec("P")
R = TypeVar("R")


_user_locks: Dict[str, Lock] = {}


def userlock(
  bucket: Optional[str] = None,
  pre_defer: bool = False,
  **defer_kwargs
):
  global _user_locks
  bucket = bucket or "_"

  def _userlock(g: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    async def wrapper(self: "Command", *args: P.args, **kwargs: P.kwargs):
      bucket_name = f"{bucket}|{self.caller_id}"
      if bucket_name not in _user_locks:
        _user_locks[bucket_name] = Lock()

      if pre_defer and _user_locks[bucket_name].locked():
        await self.defer(**defer_kwargs)

      async with _user_locks[bucket_name]:
        return await g(self, *args, **kwargs)

    return wrapper

  return _userlock


def is_userlocked(id: Snowflake, bucket: Optional[str] = None):
  global _user_locks
  bucket_name = f"{bucket or '_'}|{id}"

  if bucket_name not in _user_locks:
    return False
  return _user_locks[bucket_name].locked()


class CustomID(str):
  def __add__(self, other):
    return CustomID(str(self) + str(other))

  def prompt(self):
    return self + "|prompt"

  def response(self):
    return self + "|response"

  def select(self):
    return self + "|select"

  def confirm(self):
    return self + "|confirm"

  def action(self, action: str):
    return self + f"|{action}"

  def id(self, value: Any):
    return self + f":{value}"

  def numeric_id_pattern(self):
    return re.compile(re.escape(self) + r":[0-9]+$")

  def string_id_pattern(self):
    return re.compile(re.escape(self) + r":.+$")

  def get_id(self):
    return self.split(":")[-1]

  def get_ids(self):
    return self.split(":")[1:]

  @classmethod
  def get_id_from(cls, ctx: ComponentContext):
    return cls(ctx.custom_id).get_id()

  @classmethod
  def get_ids_from(cls, ctx: ComponentContext):
    return cls(ctx.custom_id).get_ids()

  @classmethod
  def get_int_from(cls, ctx: ComponentContext):
    return int(cls(ctx.custom_id).get_id())

  @classmethod
  def get_snowflake_from(cls, ctx: ComponentContext):
    return Snowflake(cls(ctx.custom_id).get_id())


class AsDict:
  def asdict(self):
    return _asdict(self)


@define(slots=False)
class Caller(AsDict):
  userid: int
  user: str
  username: str
  usericon: str

  @classmethod
  def set(cls, user: Union[Member, User]):
    return cls(
      userid=user.id,
      user=user.mention,
      username=user.tag,
      usericon=user.avatar_url
    )

  @classmethod
  def raw_set(cls, id: Snowflake, username: str, usericon: str):
    return cls(userid=id, user=f"<@{id}>", username=username, usericon=usericon)


@define(slots=False)
class Target(AsDict):
  target_userid: int
  target_user: str
  target_username: str
  target_usericon: str

  @classmethod
  def set(cls, user: Union[Member, User]):
    return cls(
      target_userid=user.id,
      target_user=user.mention,
      target_username=user.tag,
      target_usericon=user.avatar_url,
    )

  @classmethod
  def raw_set(cls, id: Snowflake, username: str, usericon: str):
    return cls(target_userid=id, target_user=f"<@{id}>", target_username=username, target_usericon=usericon)


@define(slots=False)
class Guild(AsDict):
  guild_id: int
  guild_name: str
  guild_icon: str

  @classmethod
  def set(cls, ctx: InteractionContext, default_to_avatar: bool = True):
    return cls(
      guild_id=ctx.guild.id,
      guild_name=ctx.guild.name,
      guild_icon=ctx.guild.icon.url if ctx.guild.icon else ctx.author.avatar_url if default_to_avatar else ""
    )


class Command:
  ctx: InteractionContext
  caller_data: "Caller"
  caller_user: Union[Member, User]
  guild_data: Optional["Guild"]
  data: Optional["AsDict"] = None
  message: Optional[Message] = None
  state: Optional[StrEnum] = None
  edit_origin: bool = False

  @property
  def bot(self):
    return self.ctx.bot

  def bot_data(self):
    return {
      "bot_userid": self.bot.user.id,
      "bot_user": self.bot.user.mention,
      "bot_username": self.bot.user.display_name,
      "bot_usericon": self.bot.user.avatar_url
    }

  @classmethod
  def create(cls, ctx: InteractionContext):
    o = cls()
    o.set_ctx(ctx)
    return o

  @classmethod
  def from_other(cls, other_command: "Command"):
    return cls.create(other_command.ctx)

  def set_ctx(self, ctx: InteractionContext):
    self.ctx = ctx
    self.caller_user = ctx.author
    self.caller_data = Caller.set(ctx.author)
    self.guild_data  = Guild.set(ctx) if ctx.guild else None

  def set_state(self, state: StrEnum):
    self.state = state

  @property
  def is_ephemeral(self):
    if not self.ctx.message:
      return False
    return MessageFlags.EPHEMERAL in self.ctx.message.flags

  @property
  def has_origin(self):
    return hasattr(self.ctx, "edit_origin") and iscoroutinefunction(self.ctx.edit_origin)

  @property
  def caller_id(self):
    return self.caller_data.userid

  def message_template(
    self,
    template: str,
    other_data: Optional[dict] = None,
    lines_data: Optional[dict] = None,
    **kwargs
  ):
    return messages.load_message(template, data=self.asdict() | (other_data or {}), lines_data=lines_data, **kwargs)

  def message_template_multiline(
    self,
    template: str,
    lines_data: List[Dict[str, Any]],
    other_data: Optional[dict] = None,
    **kwargs
  ):
    return messages.load_multiline(
      template,
      lines_data=lines_data,
      base_data=self.asdict() | (other_data or {}),
      **kwargs
    )

  async def send(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    edit_origin: bool = False,
    lines_data: Optional[List[Dict[str, Any]]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    if (edit_origin or self.edit_origin) and self.has_origin:
      send = self.ctx.edit_origin
    elif getattr(self.ctx, "editing_origin", False):
      send = self.ctx.edit_origin
    else:
      send = self.ctx.send

    message_template = self.message_template(template, other_data, lines_data=lines_data, **template_kwargs)

    self.message = await send(**message_template.to_dict(), **kwargs)
    return self.message

  async def defer(self, ephemeral: bool = False, edit_origin: bool = False, suppress_error: bool = False):
    if self.has_origin:
      return await self.ctx.defer(
        ephemeral=ephemeral and not (edit_origin or self.edit_origin),
        edit_origin=edit_origin or self.edit_origin,
        suppress_error=suppress_error
      )
    else:
      return await self.ctx.defer(ephemeral=ephemeral, suppress_error=suppress_error)

  async def run(self):
    raise NotImplementedError

  def asdict(self):
    return (
      (self.data.asdict() if self.data else {})
      | self.bot_data()
      | self.caller_data.asdict()
      | (self.guild_data.asdict() if self.guild_data else {})
    )


class ReaderCommand(Command):
  pass


class WriterCommand(Command):
  async def send_commit(self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    edit_origin: bool = False,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")

    async with new_session.begin() as session:
      await self.transaction(session)
      self.message = await self.send(
        template, other_data=other_data, template_kwargs=template_kwargs, edit_origin=edit_origin, **kwargs
      )

    return self.message


  async def transaction(self, session: AsyncSession):
    raise NotImplementedError


class TargetMixin:
  bot: "Client"
  target_data: "Target"
  target_user: Union[Member, User]

  @property
  def target_id(self):
    return self.target_user.id

  def set_target(self, target: Union[Member, User]):
    self.target_user = target
    self.target_data = Target.set(target)

  async def fetch_target(self, target: Union[Member, User, Snowflake]):
    if isinstance(target, Snowflake):
      target = await self.bot.fetch_user(target)
    return self.set_target(target)

  def asdict(self):
    return super().asdict() | self.target_data.asdict()


class MultifieldMixin:
  data: "AsDict"
  field_data: Union[List["AsDict"], List[Dict[str, Any]]]
  _paginator: Paginator

  @property
  def base_data(self):
    return self.data

  @property
  def field_dict(self):
    if isinstance(self.field_data[0], AsDict) or hasattr(self.field_data[0], "asdict"):
      return [page.asdict() for page in self.field_data]
    else:
      return self.field_data

  def message_multifield(
    self, template: str, other_data: Optional[dict] = None, per_page: Optional[int] = None, **kwargs
  ):
    per_page = per_page or 6
    return messages.load_multifield(
      template, self.field_dict, base_data=self.asdict() | (other_data or {}), fields_per_page=per_page, **kwargs
    )

  def message_multipage(
    self, template: str, other_data: Optional[dict] = None, **kwargs
  ):
    return messages.load_multipage(
      template, self.field_dict, base_data=self.asdict() | (other_data or {}), **kwargs
    )

  def message_multiline(
    self, template: str, other_data: Optional[dict] = None, per_page: Optional[int] = None, **kwargs
  ):
    per_page = per_page or 10
    return messages.load_multiline(
      template, self.field_dict, base_data=self.asdict() | (other_data or {}), lines_per_page=per_page, **kwargs
    )

  def clear_timeout(self):
    if hasattr(self, "_paginator") and self._paginator.timeout_interval > 1 and self._paginator._timeout_task.run:
      self._paginator._timeout_task.run = False
      self._paginator._timeout_task.ping.set()

  async def send_multifield(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    timeout: int = 0,
    per_page: int = 6,
    extra_components: Optional[List[BaseComponent]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multifield(template, other_data, per_page, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    self._paginator = paginator
    self.message = await self._paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


  async def send_multifield_single(
    self,
    template: Optional[str] = None,
    page_index: int = 0,
    *,
    other_data: Optional[dict] = None,
    per_page: int = 6,
    template_kwargs: Optional[dict] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multifield(template, other_data, per_page, **template_kwargs)
    self.message = await self.ctx.send(
      content=message.content, embed=message.embeds[page_index] if message.embeds else None, **kwargs
    )
    return self.message


  async def send_multipage(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    timeout: int = 0,
    extra_components: Optional[List[BaseComponent]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multipage(template, other_data, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    self._paginator = paginator
    self.message = await self._paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


  async def send_multipage_single(
    self,
    template: Optional[str] = None,
    page_index: int = 0,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multipage(template, other_data, **template_kwargs)
    self.message = await self.ctx.send(
      content=message.content, embed=message.embed[page_index] if message.embed else None, **kwargs
    )
    return self.message


  async def send_multiline(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    per_page: int = 6,
    template_kwargs: Optional[dict] = None,
    timeout: int = 0,
    extra_components: Optional[List[BaseComponent]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multiline(template, other_data, per_page, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    self._paginator = paginator
    self.message = await self._paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


  async def send_multiline_single(
    self,
    template: Optional[str] = None,
    page_index: int = 0,
    *,
    other_data: Optional[dict] = None,
    per_page: int = 6,
    template_kwargs: Optional[dict] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multiline(template, other_data, per_page, **template_kwargs)
    self.message = await self.ctx.send(
      content=message.content, embed=message.embed[page_index] if message.embed else None, **kwargs
    )
    return self.message


class SelectionMixin(MultifieldMixin):
  selection_values: List[Union[StringSelectOption, str]]
  selection_per_page: int = 6
  selection_placeholder: Optional[str] = None


  async def selection_callback(self, ctx: ComponentContext):
    raise NotImplementedError


  async def send_selection(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    timeout: int = 0,
    extra_components: Optional[List[BaseComponent]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multifield(template, other_data, per_page=self.selection_per_page, **template_kwargs)
    paginator = SelectionPaginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    # paginator.show_select_menu = True
    paginator.selection_values = self.selection_values
    paginator.selection_callback = self.selection_callback
    paginator.selection_per_page = self.selection_per_page
    if self.selection_placeholder:
      paginator.selection_placeholder = self.selection_placeholder

    self._paginator = paginator
    self.message = await self._paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


  async def send_selection_multiline(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    timeout: int = 0,
    extra_components: Optional[List[BaseComponent]] = None,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multiline(template, other_data, per_page=self.selection_per_page, **template_kwargs)
    paginator = SelectionPaginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    # paginator.show_select_menu = True
    paginator.selection_values = self.selection_values
    paginator.selection_callback = self.selection_callback
    paginator.selection_per_page = self.selection_per_page
    if self.selection_placeholder:
      paginator.selection_placeholder = self.selection_placeholder

    self._paginator = paginator
    self.message = await self._paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


class AutocompleteMixin:
  input_text: str

  @staticmethod
  def option(name: str, value: str):
    return {
      "name": name,
      "value": value
    }

  async def autocomplete(self, input_text: str):
    raise NotImplementedError

  async def send_autocomplete(self, options: Optional[List[Dict[str, str]]] = None):
    options = options or []
    if isinstance(self.ctx, AutocompleteContext):
      await self.ctx.send(options)