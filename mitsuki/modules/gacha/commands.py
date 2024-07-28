# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import re
from attrs import define, field
from typing import Optional, Union, List, Dict, Any, NamedTuple
from enum import Enum, StrEnum
from interactions import (
  ComponentContext,
  Snowflake,
  BaseUser,
  Member,
  InteractionContext,
  Message,
  Timestamp,
  Button,
  ButtonStyle,
  StringSelectMenu,
  StringSelectOption,
  Permissions,
)
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki import bot
from mitsuki.utils import escape_text, process_text, truncate, get_member_color_value
from mitsuki.lib.commands import (
  AsDict,
  CustomID,
  ReaderCommand,
  WriterCommand,
  TargetMixin,
  MultifieldMixin,
  AutocompleteMixin,
  SelectionMixin,
)
from mitsuki.lib.checks import is_caller, assert_user_permissions

from . import userdata
from .schema import UserCard, StatsCard, RosterCard
from .gachaman import gacha, daily_reset_time


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


class CustomIDs:
  VIEW = CustomID("gacha_view")
  """View a card. (id: Card ID; select)"""

  CARDS = CustomID("gacha_cards")
  """View a user's card collection in list view. (id: Target User)"""

  GALLERY = CustomID("gacha_gallery")
  """View a user's card collection in deck view. (id: Target User)"""

  PROFILE = CustomID("gacha_profile")
  """View a user's gacha profile. (id: Target User)"""

  ROLL = CustomID("gacha_roll")
  """Roll a card. Caller must be the same as the user in ID. (id: User)"""

  CARDS_ADMIN = CustomID("gacha_cards_admin")
  """View all cards in deck as admin. (no args)"""

  VIEW_ADMIN = CustomID("gacha_view_admin")
  """View a card as admin. (id: Card ID)"""

  RELOAD = CustomID("gacha_reload")
  """Reload the current roster. (no args; confirm)"""


class Errors(CurrencyMixin, ReaderCommand):
  async def insufficient_funds(self, shards: int, cost: int):
    await self.send("gacha_insufficient_funds", other_data={"shards": shards, "cost": cost})


class Details(CurrencyMixin, ReaderCommand):
  data: "Details.Data"

  @define(slots=False)
  class Data(AsDict):
    daily_info: str
    cost_info: str
    rarities_info: str
    cost: int
    daily: int
    reset_str: str
    reset_dyn: str
    first_time_shards: int = 0


  async def run(self):
    currency_icon = gacha.currency_icon
    currency_name = gacha.currency_name
    string_templates = []

    # Cost info
    cost = gacha.cost
    cost_info = f"{currency_icon} **{cost}** {currency_name}"

    # Daily info
    daily = gacha.daily_shards

    reset_dt = Timestamp.fromdatetime(daily_reset_time())
    reset_str = reset_dt.strftime("%H:%M UTC%z")
    reset_dyn = reset_dt.format("R")

    first_time_shards = 0
    daily_info = f"{currency_icon} **{daily}** {currency_name}\n※ Resets on {reset_str} {reset_dyn}"
    if gacha.first_time_shards and gacha.first_time_shards > 0:
      first_time_shards = gacha.first_time_shards
      string_templates.append("gacha_details_first_time_info")
      daily_info = daily_info + f"\n※ First time daily bonus: {currency_icon} {first_time_shards}"

    # Rarities info
    rarities = sorted(gacha.rarities)
    rarities_info_list = []
    for rarity in rarities:
      rate = gacha.rates[rarity] * 100.0
      pity = gacha.pity.get(rarity, 0)
      dupe = gacha.dupe_shards.get(rarity, 0)
      star = gacha.stars.get(rarity) or f"{rarity}"

      rarity_info = f"{star} **{rate:.5}%**"
      if dupe > 0:
        rarity_info = rarity_info + f" • {currency_icon} **{dupe}**"
      if pity > 0:
        rarity_info = rarity_info + f" • one guaranteed in **{pity}** rolls"
      rarities_info_list.append(rarity_info.strip())
    rarities_info = "\n".join(rarities_info_list)

    self.data = self.Data(
      daily_info=daily_info,
      cost_info=cost_info,
      rarities_info=rarities_info,
      cost=cost,
      daily=daily,
      reset_str=reset_str,
      reset_dyn=reset_dyn,
      first_time_shards=first_time_shards,
    )
    return await self.send("gacha_details", template_kwargs=dict(use_string_templates=string_templates))


class Profile(TargetMixin, CurrencyMixin, ReaderCommand):
  data: "Profile.Data"

  @define(slots=False)
  class Data(AsDict):
    user_shards: int
    total_cards: int
    total_rolled: int

  async def run(self, target: Optional[BaseUser] = None):
    self.set_target(target or self.caller_user)
    await self.defer(suppress_error=True)

    user_shards = await userdata.shards(self.target_id)
    user_stats = await userdata.stats_user(self.target_id)

    m_pity_counter = []
    m_cards = []
    m_rolled = []
    total_cards = 0
    total_rolled = 0
    last_time_max = 0.0
    last_card = None
    last_card_id = None

    for user_stat in user_stats:
      if user_stat.last_time_float and user_stat.last_time_float > last_time_max:
        last_time_max = user_stat.last_time_float
        last_card  = {k: v for k, v in user_stat.asdict().items() if k.startswith("last_")}
        last_card |= {"last_stars": user_stat.stars}
        last_card_id = user_stat.last_id
      if user_stat.set_pity and user_stat.set_pity > 0:
        m_pity_counter.append({
          "pity_stars": user_stat.stars,
          "pity_count": user_stat.user_pity or 0,
          "pity_value": user_stat.set_pity,
        })
      if user_stat.cards > 0:
        m_cards.append({
          "cards_stars": user_stat.stars,
          "cards_count": user_stat.cards,
        })
      if user_stat.rolled > 0:
        m_rolled.append({
          "rolled_stars": user_stat.stars,
          "rolled_count": user_stat.rolled,
        })
      total_cards += user_stat.cards
      total_rolled += user_stat.rolled

    lines_data = {}
    other_data = {}
    string_templates = []

    if last_card:
      string_templates.append("gacha_profile_last_card")
      other_data |= last_card

    if not await userdata.daily_first_check(self.target_id) and await userdata.daily_check(self.target_id):
      string_templates.append("gacha_profile_daily_available")

    lines_data |= {
      "m_pity_counter": m_pity_counter,
      "m_cards": m_cards,
      "m_rolled": m_rolled,
    }
    color = get_member_color_value(self.target_user)

    nav_btns = []
    if total_cards > 1:
      nav_btns.extend([
        Button(
          style=ButtonStyle.BLURPLE,
          label="Cards",
          custom_id=CustomIDs.CARDS.id(self.target_id),
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Gallery",
          custom_id=CustomIDs.GALLERY.id(self.target_id),
        ),
      ])

    if last_card_id:
      nav_btns.extend([
        Button(
          style=ButtonStyle.BLURPLE,
          label="View last rolled",
          custom_id=CustomIDs.VIEW.id(f"@{last_card_id}"),
        ),
      ])

    self.data = self.Data(user_shards=user_shards, total_cards=total_cards, total_rolled=total_rolled)
    message = await self.send(
      "gacha_profile",
      lines_data=lines_data,
      other_data=other_data,
      template_kwargs=dict(use_string_templates=string_templates, color=color),
      components=nav_btns,
    )
    active = len(nav_btns) > 0
    while active:
      try:
        _ = await bot.wait_for_component(message, nav_btns, timeout=180)
      except TimeoutError:
        active = False
      finally:
        if message and not active:
          await message.edit(components=[])


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

    string_templates = []    
    if not await userdata.daily_first_check(self.target_id) and await userdata.daily_check(self.target_id):
      string_templates.append("gacha_shards_daily_available")

    return await self.send(
      "gacha_shards",
      template_kwargs=dict(
        use_string_templates=string_templates,
        escape_data_values=["guild_name"])
    )


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
    next_daily     = daily_reset_time().timestamp()
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
      self.data = self.Data.set(user_shards, 0)
      return False

    await self.defer(suppress_error=True)
    user_pity = await userdata.pity_get(self.caller_id)
    rolled    = gacha.roll(user_pity=user_pity)
    card      = await userdata.card_roster(rolled.id)

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
        # Roll fails due to insufficient shards
        return await Errors.from_other(self).insufficient_funds(self.data.shards, gacha.cost)

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


class Cards(TargetMixin, SelectionMixin, ReaderCommand):
  state: "Cards.States"
  data: "Cards.Data"

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run_from_button(self):
    return await self.run(Snowflake(CustomID.get_id_from(self.ctx)))


  async def run(self, target: Optional[Union[BaseUser, Snowflake]] = None, sort: Optional[str] = None):
    await self.fetch_target(target or self.caller_user)
    await self.defer(suppress_error=True)

    cards = await userdata.cards_user(self.target_id, sort=sort or "date")
    self.data = self.Data(total_cards=len(cards))

    if len(cards) <= 0:
      return await self.send(self.States.NO_CARDS)

    self.field_data = cards
    self.selection_values = [
      StringSelectOption(
        label=truncate(card.name, 100),
        value=f"@{card.card}",
        description=truncate(
          (("★" * card.rarity) if card.rarity <= 6 else f"{card.rarity}★")
          + f" • {card.type} • {card.series}",
          length=100
        )
      )
      for card in cards
    ]
    self.selection_placeholder = "Select a card in page to view..."
    return await self.send_selection(
      self.States.CARDS,
      template_kwargs=dict(escape_data_values=["name", "type", "series"]),
      timeout=45
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await View.create(ctx).run_from_select()


class Gallery(TargetMixin, MultifieldMixin, ReaderCommand):
  state: "Cards.States"
  data: "Cards.Data"

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards_deck"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run_from_button(self):
    return await self.run(Snowflake(CustomID.get_id_from(self.ctx)))


  async def run(self, target: Optional[Union[BaseUser, Snowflake]] = None, sort: Optional[str] = None):
    await self.fetch_target(target or self.caller_user)
    await self.defer(suppress_error=True)

    self.field_data = await userdata.cards_user(self.target_id, sort=sort or "date")
    self.data = self.Data(total_cards=len(self.field_data))

    if self.data.total_cards <= 0:
      return await self.send(self.States.NO_CARDS)

    await self.send_multipage(
      self.States.CARDS,
      template_kwargs=dict(escape_data_values=["type", "series"]),
      timeout=45
    )


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

    VIEW_OWNERS_UNACQ   = "gacha_view_card_2_unacquired"           # gacha_view_global_unacquired
    VIEW_1OWNER_UNACQ   = "gacha_view_card_2_unacquired_one_owner" # gacha_view_global_unacquired
    VIEW_OWNERS_ACQ     = "gacha_view_card_2_acquired"             # gacha_view_global_acquired
    VIEW_1OWNER_ACQ     = "gacha_view_card_2_acquired_one_owner"   # gacha_view_global_acquired
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


  async def run_from_select(self):
    return await self.run(self.ctx.values[0])


  async def run_from_button(self):
    return await self.run(CustomID.get_id_from(self.ctx))


  async def run(self, search_key: str, target: Optional[Union[BaseUser, Snowflake]] = None):
    await self.fetch_target(target or self.caller_user)
    self.user_mode = target is not None

    results: List[StatsCard] = await self.search(search_key)
    prompted_card = None
    if len(results) <= 0: # no results
      if self.total_cards <= 0:
        return await self.send(self.States.NO_INVENTORY_USER if self.user_mode else self.States.NO_INVENTORY)
      else:
        return await self.send(self.States.NO_RESULTS_USER if self.user_mode else self.States.NO_RESULTS)

    elif len(results) == 1: # singular match
      await self.defer(suppress_error=True)
      self.card = results[0]

    elif len(results) > 1: # multiple matches
      await self.defer(suppress_error=True)
      self.set_state(self.States.SEARCH_RESULTS_USER if self.user_mode else self.States.SEARCH_RESULTS)
      prompted_card = await self.prompt()
      if not prompted_card:
        return
      self.card = prompted_card

    string_templates = []
    if self.user_mode:
      self.card_user = await userdata.card_user(self.target_id, self.card.id)
      self.set_state(self.States.VIEW_USER)
    else:
      self.card_user = await userdata.card_user(self.caller_id, self.card.id)
      if self.card.users > 1:
        string_templates.append("gacha_view_multiple_owners")
      if self.card_user:
        self.set_state(self.States.VIEW_1OWNER_ACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_ACQ)
      else:
        self.set_state(self.States.VIEW_1OWNER_UNACQ if self.card.users <= 1 else self.States.VIEW_OWNERS_UNACQ)

    await self.send(
      other_data=self.card.asdict() | (self.card_user.asdict() if self.card_user else {}),
      template_kwargs=dict(
        escape_data_values=["search_key", "name", "type", "series"],
        use_string_templates=string_templates,
      ),
      edit_origin=bool(prompted_card),
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
      f"{card.name if len(card.name) < 100 else card.name[:97] + ellip}"
    )
    if len(input_text) < 3:
      await self.send_autocomplete()
      return

    options = []
    if input_text.startswith("@"):
      card_by_id = await userdata.cards_stats(card_ids=[input_text[1:]])
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

    if amount < 1:
      return await self.send(self.States.INVALID_VALUE)
    if self.target_id == self.caller_id:
      return await self.send(self.States.INVALID_SELF)
    if self.target_user.bot:
      return await self.send(self.States.INVALID_BOT)
    if not isinstance(self.target_user, Member):
      return await self.send(self.States.INVALID_NONMEMBER)

    self.data = self.Data(shards=user_shards, amount=amount)
    if user_shards < amount:
      return await Errors.create(self.ctx).insufficient_funds(user_shards, amount)

    await self.send_commit(self.States.SENT)
    await self.send(self.States.NOTIFY, template_kwargs=dict(escape_data_values=["username", "target_username"]))


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
    await assert_user_permissions(self.ctx, Permissions.ADMINISTRATOR, "Server admin")
    await self.defer(ephemeral=True, suppress_error=True)
    self.set_target(target)

    target_shards = await userdata.shards(self.target_id)
    self.data = self.Data(shards=target_shards, amount=amount)

    if amount < 1:
      await self.send(self.States.INVALID_VALUE)
    else:
      await self.send_commit(self.States.SENT)


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
    await assert_user_permissions(self.ctx, Permissions.ADMINISTRATOR, "Server admin")
    await self.defer(ephemeral=True, suppress_error=True)

    self.field_data = await userdata.cards_stats(unobtained=True, sort=sort)
    self.data = self.Data(total_cards=len(self.field_data))

    if self.data.total_cards <= 0:
      return await self.send(self.States.NO_CARDS)
    return await self.send_multifield(self.States.CARDS, template_kwargs=dict(escape_data_values=["name", "type", "series"]))


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
    await assert_user_permissions(self.ctx, Permissions.ADMINISTRATOR, "Server admin")
    await self.defer(ephemeral=True, suppress_error=True)

    gacha.reload()
    await gacha.sync_db()

    self.data = self.Data(cards=len(gacha.cards))
    await self.send(self.States.RELOAD)