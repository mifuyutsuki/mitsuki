# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

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
from typing import Optional, Union, List, Dict, Any
from enum import StrEnum
from asyncio import iscoroutinefunction
from interactions import (
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
  spread_to_rows
)
from sqlalchemy.ext.asyncio import AsyncSession
import re

__all__ = (
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


def _bot_data():
  return {
    "bot_userid": bot.user.id,
    "bot_user": bot.user.mention,
    "bot_username": bot.user.display_name,
    "bot_usericon": bot.user.avatar_url
  }


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


class Command:
  ctx: InteractionContext
  caller_data: "Caller"
  caller_user: Union[Member, User]
  data: Optional["AsDict"] = None
  message: Optional[Message] = None
  state: Optional[StrEnum] = None
  edit_origin: bool = False

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

  def set_state(self, state: StrEnum):
    self.state = state

  @property
  def has_origin(self):
    return hasattr(self.ctx, "edit_origin") and iscoroutinefunction(self.ctx.edit_origin)

  @property
  def caller_id(self):
    return self.caller_data.userid

  def message_template(self, template: str, other_data: Optional[dict] = None, **kwargs):
    return messages.load_message(template, data=self.asdict() | (other_data or {}), **kwargs)

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
    else:
      send = self.ctx.send
    
    if lines_data:
      message_template = self.message_template_multiline(template, lines_data, other_data, **template_kwargs)
    else:
      message_template = self.message_template(template, other_data, **template_kwargs)

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
    return (self.data.asdict() if self.data else {}) | _bot_data() | self.caller_data.asdict()


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

    async with new_session() as session:
      try:
        await self.transaction(session)
        self.message = await self.send(
          template, other_data=other_data, template_kwargs=template_kwargs, edit_origin=edit_origin, **kwargs
        )
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()
    return self.message


  async def transaction(self, session: AsyncSession):
    raise NotImplementedError


class TargetMixin:
  target_data: "Target"
  target_user: Union[Member, User]

  @property
  def target_id(self):
    return self.target_user.id

  def set_target(self, target: Union[Member, User]):
    self.target_user = target
    self.target_data = Target.set(target)

  def asdict(self):
    return super().asdict() | self.target_data.asdict()


class MultifieldMixin:
  data: "AsDict"
  field_data: Union[List["AsDict"], List[Dict[str, Any]]]

  @property
  def base_data(self):
    return self.data

  @property
  def field_dict(self):
    if isinstance(self.field_data[0], AsDict) or hasattr(self.field_data[0], "asdict"):
      return [page.asdict() for page in self.field_data]
    else:
      return self.field_data

  def message_multifield(self, template: str, other_data: Optional[dict] = None, **kwargs):
    return messages.load_multifield(
      template, self.field_dict, base_data=self.asdict() | (other_data or {}), **kwargs
    )

  def message_multipage(self, template: str, other_data: Optional[dict] = None, **kwargs):
    return messages.load_multipage(
      template, self.field_dict, base_data=self.asdict() | (other_data or {}), **kwargs
    )


  async def send_multifield(
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

    message = self.message_multifield(template, other_data, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    self.message = await paginator.send(self.ctx, content=message.content, **kwargs)
    return self.message


  async def send_multifield_single(
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

    message = self.message_multifield(template, other_data, **template_kwargs)
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

    self.message = await paginator.send(self.ctx, content=message.content, **kwargs)
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

    message = self.message_multifield(template, other_data, **template_kwargs)
    paginator = SelectionPaginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    if extra_components and len(extra_components) > 0:
      paginator.extra_components = spread_to_rows(*extra_components)

    # paginator.show_select_menu = True
    paginator.selection_values = self.selection_values
    paginator.selection_callback = self.selection_callback
    paginator.selection_per_page = self.selection_per_page
    if self.selection_placeholder:
      paginator.selection_placeholder = self.selection_placeholder

    self.message = await paginator.send(self.ctx, content=message.content, **kwargs)
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