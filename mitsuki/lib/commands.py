# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# [EXPERIMENTAL] Commands framework. Eases creation of stateful commands.

from mitsuki import bot
from mitsuki.lib import messages
from mitsuki.lib.paginators import Paginator
from mitsuki.lib.userdata import new_session

from attrs import define, asdict as _asdict
from typing import Optional, Union, List, Dict, Any
from enum import StrEnum
from interactions import (
  Snowflake,
  BaseUser,
  InteractionContext,
  Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = (
  "AsDict",
  "Caller",
  "Target",
  "Command",
  "ReaderCommand",
  "WriterCommand",
  "TargetMixin",
  "MultifieldMixin",
)


def _bot_data():
  return {
    "bot_userid": bot.user.id,
    "bot_user": bot.user.mention,
    "bot_username": bot.user.display_name,
    "bot_usericon": bot.user.avatar_url
  }


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
  def set(cls, user: BaseUser):
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
  def set(cls, user: BaseUser):
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
  caller_user: BaseUser
  data: Optional["AsDict"] = None
  message: Optional[Message] = None
  state: Optional[StrEnum] = None

  @classmethod
  def create(cls, ctx: InteractionContext):
    o = cls()
    o.set_ctx(ctx)
    return o

  def set_ctx(self, ctx: InteractionContext):
    self.ctx = ctx
    self.caller_user = ctx.author
    self.caller_data = Caller.set(ctx.author)

  def set_state(self, state: StrEnum):
    self.state = state

  @property
  def caller_id(self):
    return self.caller_data.userid

  def message_template(self, template: str, other_data: Optional[dict] = None, **kwargs):
    return messages.load_message(template, data=self.asdict() | (other_data or {}), **kwargs)

  async def send(
    self,
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
    template_kwargs = template_kwargs or {}

    if edit_origin and hasattr(self.ctx, "edit_origin"):
      send = self.ctx.edit_origin
    else:
      send = self.ctx.send
    self.message = await send(
      **self.message_template(template, other_data, **template_kwargs).to_dict(), **kwargs
    )
    return self.message

  async def defer(self, ephemeral: bool = False, edit_origin: bool = False, suppress_error: bool = False):
    if hasattr(self.ctx, "edit_origin"):
      return await self.ctx.defer(ephemeral=ephemeral, edit_origin=edit_origin, suppress_error=suppress_error)
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
  target_user: BaseUser

  @property
  def target_id(self):
    return self.target_user.id

  def set_target(self, target: BaseUser):
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
    **kwargs
  ):
    if self.state:
      template = self.state
    else:
      raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multifield(template, other_data, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
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
    **kwargs
  ):
    if self.state:
      template = self.state
    else:
      raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    message = self.message_multipage(template, other_data, **template_kwargs)
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=timeout)
    paginator.show_select_menu = True
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