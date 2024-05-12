# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from attrs import define, field
from typing import Optional, Union, List, Dict, Any, NamedTuple
from enum import Enum, StrEnum
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

from mitsuki import bot
from mitsuki.utils import escape_text, is_caller, process_text
from mitsuki.lib.commands import (
  AsDict,
  ReaderCommand,
  WriterCommand,
  TargetMixin,
  MultifieldMixin,
  AutocompleteMixin
)

from . import userdata
from .schema import UserCard, StatsCard, RosterCard
from .gachaman import gacha


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
    guild_name = self.target_user.guild.name if getattr(self.target_user, "guild", None) else "-"
    self.data  = self.Data(shards=shards, is_premium=is_premium, guild_name=guild_name)
    return await self.send("gacha_shards", template_kwargs=dict(escape_data_values=["guild_name"]))


class Daily(CurrencyMixin, WriterCommand):
  state: "Daily.States"
  data: "Daily.Data"

  class States(StrEnum):
    ALREADY_CLAIMED = "gacha_daily_already_claimed"
    CLAIMED         = "gacha_daily"
    CLAIMED_FIRST   = "gacha_daily_first"
    CLAIMED_PREMIUM = "gacha_daily_premium"

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
      self.set_state(self.States.ALREADY_CLAIMED)
      daily_shards = 0
    elif await is_gacha_first(user):
      self.set_state(self.States.CLAIMED_FIRST)
      daily_shards = gacha.first_time_shards or gacha.daily_shards
    elif is_gacha_premium(user):
      self.set_state(self.States.CLAIMED_PREMIUM)
      daily_shards = gacha.premium_daily_shards or gacha.daily_shards
    else:
      self.set_state(self.States.CLAIMED)
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

  class States(StrEnum):
    INSUFFICIENT = "gacha_insufficient_funds"
    NEW          = "gacha_get_new_card"
    DUPE         = "gacha_get_dupe_card"

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
      self.set_state(self.States.INSUFFICIENT)
      self.data  = self.Data.set(user_shards, 0)
      return False

    await self.defer(suppress_error=True)
    pity   = await userdata.pity_check(self.caller_id, gacha.pity)
    rolled = gacha.roll(min_rarity=pity)
    card   = await userdata.card_roster(rolled.id)

    if await userdata.card_has(self.caller_id, rolled.id):
      self.set_state(self.States.DUPE)
      self.data  = self.Data.set(user_shards, card.dupe_shards - roll_cost)
    else:
      self.set_state(self.States.NEW)
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


class Cards(TargetMixin, MultifieldMixin, ReaderCommand):
  state: "Cards.States"
  data: "Cards.Data"

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run(self, target: Optional[BaseUser] = None, sort: Optional[str] = None):
    self.set_target(target or self.caller_user)
    await self.defer(suppress_error=True)
    self.field_data = await userdata.cards_user(self.target_id, sort=sort or "date")
    self.data = self.Data(total_cards=len(self.field_data))

    if self.data.total_cards <= 0:
      self.set_state(self.States.NO_CARDS)
    else:
      self.set_state(self.States.CARDS)

    await self.send_multifield(template_kwargs=dict(escape_data_values=["name", "type", "series"]), timeout=45)


class Gallery(TargetMixin, MultifieldMixin, ReaderCommand):
  state: "Cards.States"
  data: "Cards.Data"

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards_deck"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run(self, target: Optional[BaseUser] = None, sort: Optional[str] = None):
    self.set_target(target or self.caller_user)
    await self.defer(suppress_error=True)
    self.field_data = await userdata.cards_user(self.target_id, sort=sort or "date")
    self.data = self.Data(total_cards=len(self.field_data))

    if self.data.total_cards <= 0:
      self.set_state(self.States.NO_CARDS)
    else:
      self.set_state(self.States.CARDS)

    await self.send_multipage(template_kwargs=dict(escape_data_values=["type", "series"]), timeout=45)


class View(TargetMixin, CurrencyMixin, MultifieldMixin, AutocompleteMixin, ReaderCommand):
  state: "View.States"
  data: "View.Data"
  card: StatsCard
  card_results: List[StatsCard] = []
  card_user: Optional[UserCard] = None
  user_mode: bool = False

  class States(StrEnum):
    SEARCH_RESULTS      = "gacha_view_search_results_2"   # gacha_view_gs_search_results
    NO_RESULTS          = "gacha_view_no_results_2"       # gacha_view_gs_no_results
    NO_INVENTORY        = "gacha_view_no_acquired"        # gacha_view_gs_no_acquired
    SEARCH_RESULTS_USER = "gacha_view_search_results"     # gacha_view_us_search_results
    NO_RESULTS_USER     = "gacha_view_no_results"         # gacha_view_us_no_results
    NO_INVENTORY_USER   = "gacha_view_no_cards"           # gacha_view_us_no_cards

    VIEW_OWNERS_UNACQ   = "gacha_view_card_2_unacquired"           # gacha_view_gs_owners_unacquired
    VIEW_1OWNER_UNACQ   = "gacha_view_card_2_unacquired_one_owner" # gacha_view_gs_1owner_unacquired
    VIEW_OWNERS_ACQ     = "gacha_view_card_2_acquired"             # gacha_view_gs_owners_acquired
    VIEW_1OWNER_ACQ     = "gacha_view_card_2_acquired_one_owner"   # gacha_view_gs_1owner_acquired
    VIEW_USER           = "gacha_view_card"                        # gacha_view_us_card

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
        self.set_state(self.States.NO_INVENTORY_USER if self.user_mode else self.States.NO_INVENTORY)
      else:
        self.set_state(self.States.NO_RESULTS_USER if self.user_mode else self.States.NO_RESULTS)
      await self.send()
      return
    elif len(results) == 1: # singular match
      await self.defer(suppress_error=True)
      self.card = results[0]
    elif len(results) > 1: # multiple matches
      await self.defer(suppress_error=True)
      self.set_state(self.States.SEARCH_RESULTS_USER if self.user_mode else self.States.SEARCH_RESULTS)
      card = await self.prompt()
      if not card:
        return
      self.card = card

    if self.user_mode:
      self.card_user = await userdata.card_user(self.target_id, self.card.id)
      self.set_state(self.States.VIEW_USER)
    else:
      self.card_user = await userdata.card_user(self.caller_id, self.card.id)
      if self.card_user:
        self.set_state(self.States.VIEW_1OWNER_ACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_ACQ)
      else:
        self.set_state(self.States.VIEW_1OWNER_UNACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_UNACQ)

    await self.send(
      other_data=self.card.asdict() | (self.card_user.asdict() if self.card_user else {}),
      template_kwargs=dict(escape_data_values=["search_key", "name", "type", "series"]),
      edit_origin=True,
      components=[]
    )


  async def search(self, search_key: str):
    if self.user_mode:
      total_cards = await userdata.cards_user_count(self.target_id)
    else:
      total_cards = await userdata.cards_roster_count(unobtained=False)

    self.data = self.Data(search_key=search_key, total_cards=total_cards)
    if total_cards <= 0:
      return []

    target_id = self.target_id if self.user_mode else None
    by_id = search_key[1:] if search_key.startswith("@") else None

    if by_id and target_id and await userdata.card_has(target_id, by_id):
      self.card_results = await userdata.cards_stats(card_ids=[by_id])
    elif by_id and target_id is None:
      self.card_results = await userdata.cards_stats(card_ids=[by_id])
    if len(self.card_results) <= 0:
      self.card_results = await userdata.cards_stats_search(
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
    _ = await self.send_multifield_single(
      page_index=0,
      template_kwargs=dict(escape_data_values=["search_key", "name", "type", "series"]),
      components=select_menu
    )

    # Initiate prompt
    try:
      selected = await bot.wait_for_component(components=select_menu, check=is_caller(self.ctx), timeout=45)
    except TimeoutError:
      if self.message:
        await self.message.edit(components=[])
      return None
    else:
      self.set_ctx(selected.ctx)
      await self.defer(edit_origin=True)
      return self.card_results[selection.index(self.ctx.values[0])]


  async def autocomplete(self, input_text: str):
    ellip = "..."
    card_info = lambda card: (
      f"{card.name if len(card.name) < 32 else card.name[:29] + ellip} • {card.type} • {card.series}"
    )
    if len(input_text) < 3:
      await self.send_autocomplete()
      return

    options = []
    if input_text.startswith("@"):
      card_by_id = await userdata.cards_roster(card_ids=[input_text[1:]])
      if len(card_by_id) > 0:
        options.append(self.option("@ " + card_info(card_by_id[0]), input_text))

    search_results = await userdata.cards_roster_search(input_text, cutoff=60, limit=9-len(options))
    options.extend([self.option(card_info(card), f"@{card.id}") for card in search_results])
    options.append(self.option(f"※ Search for '{input_text}'", input_text))
    await self.send_autocomplete(options)


class Give(TargetMixin, CurrencyMixin, WriterCommand):
  states: "Give.States"
  data: "Give.Data"

  class States(StrEnum):
    INSUFFICIENT      = "gacha_insufficient_funds"
    INVALID_VALUE     = "gacha_give_badvalue"
    INVALID_SELF      = "gacha_give_self"
    INVALID_BOT       = "gacha_give_bot"
    INVALID_NONMEMBER = "gacha_give_nonmember"
    SENT              = "gacha_give"
    NOTIFY            = "gacha_give_notification"

  @define(slots=False)
  class Data(AsDict):
    shards: int
    amount: int
    new_shards: int = field(init=False)
    cost: int = field(init=False) # used by gacha_insufficient_funds

    def __attrs_post_init__(self):
      self.cost = self.amount
      self.new_shards = self.shards if self.amount < 0 or self.shards < self.amount else self.shards - self.amount


  async def run(self, target: BaseUser, amount: int):
    self.set_target(target)
    user_shards = await userdata.shards(self.caller_id)

    valid = False
    if amount < 1:
      self.set_state(self.States.INVALID_VALUE)
    elif self.target_id == self.caller_id:
      self.set_state(self.States.INVALID_SELF)
    elif self.target_user.bot:
      self.set_state(self.States.INVALID_BOT)
    elif not isinstance(self.target_user, Member):
      self.set_state(self.States.INVALID_NONMEMBER)
    elif user_shards < amount:
      self.set_state(self.States.INSUFFICIENT)
    else:
      self.set_state(self.States.SENT)
      valid = True
    self.data = self.Data(shards=user_shards, amount=amount)

    if not valid:
      await self.send()
    else:
      await self.send_commit()
      self.set_state(self.States.NOTIFY)
      await self.send(template_kwargs=dict(escape_data_values=["username", "target_username"]))


  async def transaction(self, session: AsyncSession):
    await userdata.shards_exchange(session, self.caller_id, self.target_id, self.data.amount)


class GiveAdmin(TargetMixin, CurrencyMixin, WriterCommand):
  state: "GiveAdmin.States"
  data: "GiveAdmin.Data"

  class States(StrEnum):
    INVALID_VALUE = "gacha_give_admin_badvalue"
    SENT          = "gacha_give_admin"

  @define(slots=False)
  class Data(AsDict):
    shards: int
    amount: int
    new_shards: int = field(init=False)

    def __attrs_post_init__(self):
      self.new_shards = self.shards if self.amount <= 0 else self.shards + self.amount

  async def run(self, target: BaseUser, amount: int):
    await self.defer(ephemeral=True, suppress_error=True)
    self.set_target(target)

    target_shards = await userdata.shards(self.target_id)
    valid = False
    if amount < 1:
      self.set_state(self.States.INVALID_VALUE)
    else:
      self.set_state(self.States.SENT)
      valid = True
    self.data = self.Data(shards=target_shards, amount=amount)

    if not valid:
      await self.send()
    else:
      await self.send_commit()


  async def transaction(self, session: AsyncSession):
    await userdata.shards_give(session, self.target_id, self.data.amount)


class ViewAdmin(MultifieldMixin, ReaderCommand):
  states: "ViewAdmin.States"
  data: "ViewAdmin.Data"

  class States(StrEnum):
    NO_CARDS = "gacha_view_admin_no_cards"
    CARDS    = "gacha_view_admin"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run(self, sort: Optional[str] = None):
    await self.defer(ephemeral=True, suppress_error=True)
    self.field_data = await userdata.cards_stats(unobtained=True, sort=sort)
    self.data = self.Data(total_cards=len(self.field_data))

    if self.data.total_cards <= 0:
      self.set_state(self.States.NO_CARDS)
    else:
      self.set_state(self.States.CARDS)

    await self.send_multifield(template_kwargs=dict(escape_data_values=["name", "type", "series"]))


class ReloadAdmin(ReaderCommand):
  state: "ReloadAdmin.States"
  data: "ReloadAdmin.Data"

  class States(StrEnum):
    RELOAD = "gacha_reload"

  @define(slots=False)
  class Data(AsDict):
    cards: int


  async def run(self):
    global gacha
    await self.defer(ephemeral=True, suppress_error=True)

    gacha.reload()
    await gacha.sync_db()

    self.data = self.Data(cards=len(gacha.cards))
    self.set_state(self.States.RELOAD)
    await self.send()