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
from typing import Optional, Union, List, Dict, Any, NamedTuple
from enum import Enum
from interactions import (
  Snowflake,
  BaseUser,
  Member,
  InteractionContext,
  Message,
  Timestamp,
)
from sqlalchemy.ext.asyncio import AsyncSession


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


class State(NamedTuple):
  enum: int
  template: str


class StateEnum(State, Enum):
  pass


class Command:
  ctx: InteractionContext
  caller_data: "Caller"
  caller_user: BaseUser
  data: Optional["AsDict"] = None
  message: Optional[Message] = None
  state: Optional["StateEnum"] = None

  @classmethod
  def create(cls, ctx: InteractionContext):
    o = cls()
    o.set_ctx(ctx)
    return o

  def set_ctx(self, ctx: InteractionContext):
    self.ctx = ctx
    self.caller_user = ctx.author
    self.caller_data = Caller.set(ctx.author)

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
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state.template
      else:
        raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    self.message = await self.ctx.send(
      **self.message_template(template, other_data, **template_kwargs).to_dict(), **kwargs
    )
    return self.message

  async def run(self, *args, **kwargs):
    raise NotImplementedError

  def asdict(self):
    return (self.data.asdict() if self.data else {}) | self.caller_data.asdict()


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
    if isinstance(self.field_data[0], AsDict):
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
    **kwargs
  ):
    if self.state:
      template = self.state.template
    else:
      raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    self.message = await self.ctx.send(
      **self.message_multifield(template, other_data, **template_kwargs).to_dict(), **kwargs
    )
    return self.message

  async def send_multipage(
    self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    **kwargs
  ):
    if self.state:
      template = self.state.template
    else:
      raise RuntimeError("Unspecified message template or state")
    template_kwargs = template_kwargs or {}

    self.message = await self.ctx.send(
      **self.message_multipage(template, other_data, **template_kwargs).to_dict(), **kwargs
    )
    return self.message


class ReaderCommand(Command):
  pass


class WriterCommand(Command):
  async def send_commit(self,
    template: Optional[str] = None,
    *,
    other_data: Optional[dict] = None,
    template_kwargs: Optional[dict] = None,
    **kwargs
  ):
    async with new_session() as session:
      try:
        await self.transaction(session)
        self.message = await self.send(template, other_data=other_data, template_kwargs=template_kwargs, **kwargs)
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()
    return self.message

  async def transaction(self, session: AsyncSession):
    raise NotImplementedError


# =============================================================================
# Gacha data

@define(slots=False)
class Currency(AsDict):
  currency: str = field(default=gacha.currency)
  currency_name: str = field(default=gacha.currency_name)
  currency_icon: str = field(default=gacha.currency_icon)

class CurrencyMixin:
  currency_data: "Currency" = Currency()

  def asdict(self):
    return super().asdict() | self.currency_data.asdict()


def is_gacha_premium(user: BaseUser):
  if not isinstance(user, Member):
    return False
  return bool(
    gacha.premium_guilds
    and gacha.premium_daily_shards
    and gacha.premium_daily_shards > 0
    and user.premium
    and (user.guild.id in gacha.premium_guilds)
  )


async def is_gacha_first(user: BaseUser):
  return bool(
    gacha.first_time_shards
    and gacha.first_time_shards > 0
    and await userdata.daily_first_check(user.id)
  )


# =============================================================================
# Gacha commands

class Shards(TargetMixin, CurrencyMixin, ReaderCommand):
  data: "Shards.Data"

  @define(slots=False)
  class Data(AsDict):
    shards: int
    is_premium: bool
    guild_name: Optional[str]

  async def run(self, target: Optional[BaseUser] = None):
    self.set_target(target or self.caller_user)
    shards     = await userdata.shards(self.target_id)
    is_premium = is_gacha_premium(self.target_user)
    guild_name = self.target_user.guild.name if isinstance(self.target_user, Member) else None
    self.data  = self.Data(shards=shards, is_premium=is_premium, guild_name=guild_name)
    return await self.send("gacha_shards", escape_data_values=["guild_name"])


class Daily(CurrencyMixin, WriterCommand):
  state: "Daily.States"
  data: "Daily.Data"

  class States(StateEnum):
    ALREADY_CLAIMED = State(0, "gacha_daily_already_claimed")
    CLAIMED         = State(1, "gacha_daily")
    CLAIMED_FIRST   = State(2, "gacha_daily_first")
    CLAIMED_PREMIUM = State(3, "gacha_daily_premium")

  @define(slots=False)
  class Data(AsDict):
    available: bool
    shards: int
    new_shards: int
    raw_timestamp: float
    guild_name: str
    timestamp: int = field(init=False)
    timestamp_r: str = field(init=False)
    timestamp_f: str = field(init=False)

    def __attrs_post_init__(self):
      self.timestamp   = int(self.raw_timestamp)
      self.timestamp_r = Timestamp.fromtimestamp(self.timestamp).format("R")
      self.timestamp_f = Timestamp.fromtimestamp(self.timestamp).format("f")

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
    next_daily     = userdata.daily_next()
    guild_name     = user.guild.name if getattr(user, "guild", None) else "-"

    if not available:
      self.state   = self.States.ALREADY_CLAIMED
      daily_shards = 0
    elif await is_gacha_first(user):
      self.state   = self.States.CLAIMED_FIRST
      daily_shards = gacha.first_time_shards or gacha.daily_shards
    elif is_gacha_premium(user):
      self.state   = self.States.CLAIMED_PREMIUM
      daily_shards = gacha.premium_daily_shards or gacha.daily_shards
    else:
      self.state   = self.States.CLAIMED
      daily_shards = gacha.daily_shards

    self.data = self.Data(
      available=available,
      shards=daily_shards,
      new_shards=current_shards + daily_shards,
      raw_timestamp=next_daily,
      guild_name=guild_name
    )

    if available and daily_shards > 0:
      return await self.send_commit(escape_data_values=["guild_name"])
    else:
      return await self.send(escape_data_values=["guild_name"])

  async def transaction(self, session: AsyncSession):
    await userdata.daily_give(session, self.caller_id, self.amount)


class View(CurrencyMixin, ReaderCommand):
  state: "View.States"
  data: "View.Data"

  class States(Enum):
    SEARCH_RESULTS = State(0, "gacha_view_gs_search_results")
    VIEW           = State(1, "gacha_view_gs")
    NO_RESULTS     = State(2, "gacha_view_gs_no_results")
    NO_INVENTORY   = State(3, "gacha_view_gs_no_acquired")

  class Data(AsDict):
    pass