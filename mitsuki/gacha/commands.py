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

from mitsuki import settings, messages, bot
from mitsuki.userdata import new_session
from mitsuki.utils import escape_text, is_caller, process_text, suppressed_defer
from . import userdata
from .schema import UserCard, StatsCard, RosterCard
from .gachaman import gacha

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
  Button,
  ButtonStyle,
  StringSelectMenu,
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
    edit_origin: bool = False,
    **kwargs
  ):
    if not template:
      if self.state:
        template = self.state.template
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
class BaseCard(AsDict):
  id: str
  name: str
  rarity: int
  type: str
  series: str

  color: int
  stars: str
  dupe_shards: int
  image: Optional[str] = field(default=None)

  linked_name: str = field(init=False)

  def __attrs_post_init__(self):
    self.linked_name = f"[{escape_text(self.name)}]({self.image})" if self.image else self.name


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
    return await self.send("gacha_shards", template_kwargs=dict(escape_data_values=["guild_name"]))


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
      return await self.send_commit(template_kwargs=dict(escape_data_values=["guild_name"]))
    else:
      return await self.send(template_kwargs=dict(escape_data_values=["guild_name"]))

  async def transaction(self, session: AsyncSession):
    await userdata.daily_give(session, self.caller_id, self.amount)


class Roll(CurrencyMixin, WriterCommand):
  state: "Roll.States"
  data: "Roll.Data"
  card: Optional[BaseCard] = None
  again: bool = True

  class States(StateEnum):
    INSUFFICIENT = State(0, "gacha_insufficient_funds")
    NEW          = State(1, "gacha_get_new_card")
    DUPE         = State(2, "gacha_get_dupe_card")

  @define(slots=False)
  class Data(AsDict):
    shards: int
    update_shards: int
    cost: int = field(default=gacha.cost)
    new_shards: int = field(init=False)

    @classmethod
    def set(cls, user_shards: int, update_shards: int):
      return cls(shards=user_shards, update_shards=update_shards)

    def __attrs_post_init__(self):
      self.new_shards = self.shards + self.update_shards

  async def roll(self):
    user_shards = await userdata.shards(self.caller_id)
    roll_cost   = gacha.cost

    if user_shards < roll_cost:
      self.state = self.States.INSUFFICIENT
      self.data  = self.Data.set(user_shards, 0)
      return False

    await suppressed_defer(self.ctx)
    pity   = await userdata.pity_check(self.caller_id, gacha.pity)
    rolled = gacha.roll(min_rarity=pity)
    card   = await userdata.card_get_roster(rolled.id)

    if await userdata.card_has(self.caller_id, rolled.id):
      self.state = self.States.DUPE
      self.data  = self.Data.set(user_shards, card.dupe_shards - roll_cost)
    else:
      self.state = self.States.NEW
      self.data  = self.Data.set(user_shards, -roll_cost)
    self.again = self.data.new_shards >= self.data.cost
    self.card  = card
    return True


  async def run(self):
    again_response = None
    while self.again:
      if not await self.roll():
        await self.send()
        return

      again_btn = Button(style=ButtonStyle.BLURPLE, label="Roll again", disabled=not self.again)
      message   = await self.send_commit(
        other_data=self.card.asdict(), 
        template_kwargs=dict(escape_data_values=["name", "type", "series"]),
        components=again_btn
      )

      try:
        again_response = await bot.wait_for_component(components=again_btn, check=is_caller(self.ctx), timeout=15)
      except TimeoutError:
        return
      else:
        self.set_ctx(again_response.ctx)
      finally:
        if message:       
          await message.edit(components=[])


  async def transaction(self, session: AsyncSession):
    await userdata.shards_update(session, self.caller_id, self.data.update_shards)
    await userdata.card_give(session, self.caller_id, self.card.id)
    await userdata.pity_update(session, self.caller_id, self.card.rarity, gacha.pity)


class View(TargetMixin, CurrencyMixin, MultifieldMixin, ReaderCommand):
  state: "View.States"
  data: "View.Data"
  card: StatsCard
  card_results: List[StatsCard]
  card_user: Optional[UserCard] = None
  user_mode: bool = False

  class States(StateEnum):
    SEARCH_RESULTS      = State(0, "gacha_view_search_results_2")   # gacha_view_gs_search_results
    NO_RESULTS          = State(1, "gacha_view_no_results_2")       # gacha_view_gs_no_results
    NO_INVENTORY        = State(2, "gacha_view_no_acquired")        # gacha_view_gs_no_acquired
    SEARCH_RESULTS_USER = State(3, "gacha_view_search_results")     # gacha_view_us_search_results
    NO_RESULTS_USER     = State(4, "gacha_view_no_results")         # gacha_view_us_no_results
    NO_INVENTORY_USER   = State(5, "gacha_view_no_cards")           # gacha_view_us_no_cards

    VIEW_OWNERS_UNACQ   = State(11, "gacha_view_card_2_unacquired")           # gacha_view_gs_owners_unacquired
    VIEW_1OWNER_UNACQ   = State(12, "gacha_view_card_2_unacquired_one_owner") # gacha_view_gs_1owner_unacquired
    VIEW_OWNERS_ACQ     = State(13, "gacha_view_card_2_acquired")             # gacha_view_gs_owners_acquired
    VIEW_1OWNER_ACQ     = State(14, "gacha_view_card_2_acquired_one_owner")   # gacha_view_gs_1owner_acquired
    VIEW_USER           = State(15, "gacha_view_card")                        # gacha_view_us_card

  @define(slots=False)
  class Data(AsDict):
    search_key: str
    total_cards: int
    # total_results: int [FUTURE]

  @property
  def search_key(self):
    return self.data.search_key

  @property
  def total_cards(self):
    return self.data.total_cards


  async def run(self, search_key: str, target: Optional[BaseUser] = None):
    self.set_target(target or self.caller_user)
    self.user_mode = target is not None

    results: List[StatsCard] = await self.search(search_key)
    if len(results) <= 0: # no results
      if self.total_cards <= 0:
        self.state = self.States.NO_INVENTORY_USER if self.user_mode else self.States.NO_INVENTORY
      else:
        self.state = self.States.NO_RESULTS_USER if self.user_mode else self.States.NO_RESULTS
      await self.send()
      return
    elif len(results) == 1: # singular match
      await suppressed_defer(self.ctx)
      self.card = results[0]
    elif len(results) > 1: # multiple matches
      await suppressed_defer(self.ctx)
      self.state = self.States.SEARCH_RESULTS_USER if self.user_mode else self.States.SEARCH_RESULTS
      card = await self.prompt()
      if not card:
        return
      self.card = card

    if self.user_mode:
      self.card_user = await userdata.card_get_user(self.target_id, self.card.id)
      self.state = self.States.VIEW_USER
    else:
      self.card_user = await userdata.card_get_user(self.caller_id, self.card.id)
      if self.card_user:
        self.state = self.States.VIEW_1OWNER_ACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_ACQ
      else:
        self.state = self.States.VIEW_1OWNER_UNACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_UNACQ

    await self.send(
      other_data=self.card.asdict() | (self.card_user.asdict() if self.card_user else {}),
      template_kwargs=dict(escape_data_values=["search_key", "name", "type", "series"]),
      edit_origin=True,
      components=[]
    )


  async def search(self, search_key: str):
    total_cards = await userdata.card_list_count(target_id := self.target_id if self.user_mode else None)
    self.data = self.Data(search_key=search_key, total_cards=total_cards)
    if total_cards <= 0:
      return []

    self.card_results = await userdata.card_search(
      search_key, user_id=target_id, limit=6, cutoff=60, strong_cutoff=90, processor=process_text
    )
    return self.card_results


  async def prompt(self):
    # Handle cards with the same names
    self.field_data = self.card_results
    selection: List[str] = []
    for card in self.card_results:
      selection_name = card.name
      repeat_no = 1
      while selection_name in selection:
        selection_name = f"{card.name} ({repeat_no})"
        repeat_no += 1
      selection.append(selection_name)
    
    # Create prompt
    select_menu = StringSelectMenu(*selection, placeholder="Card to view from search results")
    message = self.message_multifield(
      self.state.template, escape_data_values=["search_key", "name", "type", "series"]
    )
    self.message = await self.ctx.send(content=message.content, embed=message.embeds[0], components=select_menu)

    # Initiate prompt
    try:
      selected = await bot.wait_for_component(components=select_menu, check=is_caller(self.ctx), timeout=45)
    except TimeoutError:
      if self.message:
        await self.message.edit(components=[])
      return None
    else:
      self.set_ctx(selected.ctx)
      await self.ctx.defer(edit_origin=True)
      return self.card_results[selection.index(self.ctx.values[0])]