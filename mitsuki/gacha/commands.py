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

from mitsuki import settings, messages
from mitsuki.userdata import new_session
from . import userdata
from .gachaman import gacha
# from .schema import UserCard, StatsCard, RosterCard

from attrs import define, frozen, field, asdict as _asdict
from typing import Optional, Union, List, Dict, Any
from enum import Enum
from interactions import Snowflake, BaseUser, Member, InteractionContext, Message
from sqlalchemy.ext.asyncio import AsyncSession


def is_gacha_premium(user: BaseUser):
  if not isinstance(user, Member):
    return False
  return bool(
    gacha.premium_guilds
    and gacha.premium_daily_shards
    and user.premium
    and (user.guild.id in gacha.premium_guilds)
  )

# =============================================================================
# Base MitsukiCommand classes. Defined here as experimental

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
      usericon=user.display_avatar.url
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
      target_usericon=user.display_avatar.url,
    )

  @classmethod
  def raw_set(cls, id: Snowflake, username: str, usericon: str):
    return cls(target_userid=id, target_user=f"<@{id}>", target_username=username, target_usericon=usericon)


class Command:
  caller_data: "Caller"
  caller_user: BaseUser
  target_data: Optional["Target"] = None
  target_user: Optional[BaseUser] = None
  data: Optional["AsDict"] = None
  message: Optional[Message] = None

  @classmethod
  async def create(cls, caller: BaseUser):
    o = cls()
    o.caller_user = caller
    o.caller_data = Caller.set(caller)
    return o

  @property
  def caller_id(self):
    return self.caller_data.userid

  @property
  def target_id(self):
    return self.target_data.target_userid if self.target_data else None

  def set_target(self, target: BaseUser):
    self.target_user = target
    self.target_data = Target.set(target)

  def message(self, template: str, other_data: dict, **kwargs):
    return messages.load_message(template, data=self.data.asdict() | other_data, **kwargs)

  async def send(self, ctx: InteractionContext, **send_kwargs):
    self.message = await ctx.send(**send_kwargs)
    return self

  async def run(self, *args, **kwargs):
    raise NotImplementedError

  async def asdict(self):
    return (
      self.data.asdict() if self.data else {}
      | self.caller_data.asdict()
      | self.target_data.asdict() if self.target_data else {}
    )


class StatefulMixin:
  state: Enum


class PaginatorMixin:
  data: "AsDict"
  page_data: Union[List["AsDict"], List[Dict[str, Any]]]

  @property
  def base_data(self):
    return self.data

  @property
  def page_dict(self):
    if isinstance(self.page_data[0], AsDict):
      return [page.asdict() for page in self.page_data]
    else:
      return self.page_data

  def message_multifield(self, template: str, other_data: Optional[dict] = None, **kwargs):
    return messages.load_multifield(
      template, self.page_dict, base_data=self.data.asdict() | (other_data or {}), **kwargs
    )

  def message_multipage(self, template: str, other_data: dict, **kwargs):
    return messages.load_multipage(
      template, self.page_dict, base_data=self.data.asdict() | (other_data or {}), **kwargs
    )


class ReaderCommand(Command):
  pass


class WriterCommand(Command):
  async def send_commit(self, ctx: InteractionContext, **send_kwargs):
    async with new_session() as session:
      try:
        await self.transaction(session)
        self.message = await self.send(ctx, **send_kwargs)
      except Exception:
        await session.rollback()
      else:
        await session.commit()
    return self

  async def transaction(self, session: AsyncSession):
    raise NotImplementedError


# =============================================================================
# Gacha data

@define(slots=False)
class Currency:
  currency: str = field(default=gacha.currency)
  currency_name: str = field(default=gacha.currency_name)
  currency_icon: str = field(default=gacha.currency_icon)

class HasCurrency:
  currency: "Currency"


# =============================================================================
# Gacha commands

class Shards(ReaderCommand, HasCurrency):
  data: "Shards.Data"

  @define(slots=False)
  class Data(AsDict):
    shards: int
    is_premium: bool
    guild_name: Optional[str]

  async def run(self, target: Optional[BaseUser] = None):
    self.set_target(target := target or self.caller_user)
    shards     = await userdata.shards(self.target_id)
    is_premium = is_gacha_premium(self.target_user)
    guild_name = self.target_user.guild.name if isinstance(self.target_user, Member) else None
    self.data  = self.Data(shards=shards, is_premium=is_premium, guild_name=guild_name)


class Daily(WriterCommand, HasCurrency):
  data: "Daily.Data"

  @define(slots=False)
  class Data(AsDict):
    available: bool
    shards: int
    new_shards: int
    timestamp: int
    timestamp_r: str
    timestamp_f: str

    @classmethod
    async def set(cls, user: BaseUser):
      available      = await userdata.daily_check(user.id)
      current_shards = await userdata.shards(user.id)
      daily_shards   = gacha.daily_shards
      next_daily     = int(userdata.daily_next())

      return cls(available=available, shards=daily_shards, new_shards=current_shards + daily_shards,
                 timestamp_r=f"<t:{next_daily}:r>", timestamp_f=f"<t:{next_daily}:f>")

  @property
  def available(self):
    return self.data.available

  @property
  def amount(self):
    return self.data.shards

  async def run(self):
    user = self.caller_user
    available      = await userdata.daily_check(user.id)
    current_shards = await userdata.shards(user.id)
    daily_shards   = gacha.daily_shards
    next_daily     = int(userdata.daily_next())

    self.data = self.Data(available=available, shards=daily_shards, new_shards=current_shards + daily_shards)

  async def transaction(self, session: AsyncSession):
    await userdata.daily_give(session, self.caller_id, self.amount)


class View(ReaderCommand, HasCurrency, StatefulMixin):
  data: "View.Data"
  state: "View.States"

  class Data(AsDict):
    pass

  class States(Enum):
    SELECT = 0
    VIEW = 1