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
from yaml import safe_load, YAMLError
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
  Attachment,
  Modal,
  ShortText,
  ActionRow,
)
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp

from mitsuki import bot
from mitsuki.utils import escape_text, process_text, truncate, get_member_color_value, ratio
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
from mitsuki.lib.checks import is_caller, assert_user_permissions, assert_bot_owner

from . import userdata, api
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

  BANNER = CustomID("gacha_banner")
  """Manage banners. (modal)"""

  BANNER_CONFIGURE = CustomID("gacha_banner_configure")
  """Configure a banner. (id: Banner ID)"""


class Errors(CurrencyMixin, ReaderCommand):
  async def insufficient_funds(self, shards: int, cost: int):
    return await self.send("gacha_insufficient_funds", other_data={"shards": shards, "cost": cost})

  async def card_not_found(self, card_key: str):
    return await self.send("gacha_card_not_found", other_data={"card_key": card_key})


class Info(CurrencyMixin, ReaderCommand):
  data: "Info.Data"

  class States(StrEnum):
    INFO = "gacha_info"

  class Strings(StrEnum):
    FIRST_TIME_INFO = "gacha_info_first_time_info"

  @define(slots=False)
  class Data(AsDict):
    cost: int
    daily: int
    daily_reset_s: str
    daily_reset_r: str
    daily_first_time: int = 0


  async def run(self):
    string_templates = []

    reset_datetime = Timestamp.fromdatetime(daily_reset_time())

    cost  = gacha.cost
    daily = gacha.daily_shards
    daily_reset_s = reset_datetime.strftime("%H:%M UTC%z")
    daily_reset_r = reset_datetime.format("R")

    daily_first_time = 0
    if gacha.first_time_shards and gacha.first_time_shards > 0:
      daily_first_time = gacha.first_time_shards
      string_templates.append(self.Strings.FIRST_TIME_INFO)

    lines_data = {
      "m_rates": [],
      "m_dupes": [],
      "m_pity": []
    }
    for rarity in sorted(gacha.rarities):
      rate = gacha.rates[rarity] * 100.0
      pity = gacha.pity.get(rarity, 0)
      dupe = gacha.dupe_shards.get(rarity, 0)
      star = gacha.stars.get(rarity) or f"{rarity}"

      lines_data["m_rates"].append({"star": star, "rate": f"{rate:.5}"})
      if dupe > 0:
        lines_data["m_dupes"].append({"star": star, "dupe": dupe})
      if pity > 0:
        lines_data["m_pity"].append({"star": star, "pity": pity})

    self.data = self.Data(
      cost=cost,
      daily=daily,
      daily_reset_s=daily_reset_s,
      daily_reset_r=daily_reset_r,
      daily_first_time=daily_first_time,
    )
    return await self.send(
      "gacha_info",
      lines_data=lines_data,
      template_kwargs={
        "use_string_templates": string_templates
      }
    )


class Profile(TargetMixin, CurrencyMixin, ReaderCommand):
  data: "Profile.Data"

  @define(slots=False)
  class Data(AsDict):
    user_shards: int
    total_cards: int
    total_rolled: int

  async def run(self, target: Optional[BaseUser] = None):
    # Arona API TODO:
    # - UserStats.fetch(user)

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
          custom_id=CustomIDs.VIEW.id(last_card_id),
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
    # Arona API TODO:
    #   Instead of separate calls to daily_check() and shards(),
    #   simply fetch the gacha user, and use GachaUser methods.
    #   
    #   Daily time can be taken from call time, ctx.id.created_at, as ctx.id is a snowflake containing its time.
    #   
    #   - GachaUser.fetch(user.id)
    #   - GachaUser.is_daily(call_time)
    #   - GachaUser.give(session, arona.daily_shards, daily_time=call_time)

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
    # Arona API TODO:
    #   User is still fetched for sufficient shards using GachaUser.fetch().
    #   
    #   Instead of separate calls to pity_get() and roll(),
    #   the new arona.roll() takes in user id, which allows Arona to use the user's pity counters.
    #   
    #   Roll time can be taken from call time, ctx.id.created_at, as ctx.id is a snowflake containing its time.
    #   
    #   Reads:
    #   - GachaUser.has_shards(arona.daily_shards)
    #   - Arona.roll(time=call_time, user=user)
    #   - UserInventory.has_card(user, card)
    #   
    #   Writes:
    #   - GachaUser.give(session, self.dupe_shards - arona.daily_shards)
    #   - Roll.add(session, card, call_time)
    #   - UserInventory.give(session, card)
    #   - UserPity.increment(session, user, card.rarity)

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

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards"


  async def run_from_button(self):
    return await self.run(Snowflake(CustomID.get_id_from(self.ctx)))


  async def run(self, target: Optional[Union[BaseUser, Snowflake]] = None, sort: Optional[str] = None):
    await self.fetch_target(target or self.caller_user)
    await self.defer(suppress_error=True)

    cards = await api.UserCard.fetch_all(self.target_id, sort=sort)

    if len(cards) <= 0:
      return await self.send(self.States.NO_CARDS, other_data={"total_cards": 0})

    self.field_data = cards
    self.selection_values = [
      StringSelectOption(
        label=truncate(card.name, 100),
        value=card.id,
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
      other_data={"total_cards": len(self.field_data)},
      template_kwargs=dict(escape_data_values=["name", "type", "series"]),
      timeout=45
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await View.create(ctx).view_from_select(edit_origin=False)


class Gallery(TargetMixin, MultifieldMixin, ReaderCommand):
  state: "Cards.States"

  class States(StrEnum):
    NO_CARDS = "gacha_cards_no_cards"
    CARDS    = "gacha_cards_deck"


  async def run_from_button(self):
    return await self.run(Snowflake(CustomID.get_id_from(self.ctx)))


  async def run(self, target: Optional[Union[BaseUser, Snowflake]] = None, sort: Optional[str] = None):
    await self.fetch_target(target or self.caller_user)
    await self.defer(suppress_error=True)

    self.field_data = await api.UserCard.fetch_all(self.target_id, sort=sort)

    if len(self.field_data) <= 0:
      return await self.send(self.States.NO_CARDS, other_data={"total_cards": 0})

    await self.send_multipage(
      self.States.CARDS,
      other_data={"total_cards": len(self.field_data)},
      template_kwargs=dict(escape_data_values=["type", "series"]),
      timeout=45
    )


# Backend remake of /gacha view
class View(CurrencyMixin, SelectionMixin, AutocompleteMixin, ReaderCommand):
  data: "View.Data"

  class States(StrEnum):
    SEARCH_RESULTS      = "gacha_view_search_results"
    NO_RESULTS          = "gacha_view_no_results"
    NO_ACQUIRED         = "gacha_view_no_acquired"

    VIEW_UNACQUIRED     = "gacha_view_unacquired"
    VIEW_ACQUIRED       = "gacha_view_acquired"

  class Strings(StrEnum):
    MULTIPLE_OWNERS     = "gacha_view_multiple_owners"

  @define(slots=False)
  class Data(AsDict):
    search_key: str = field(converter=escape_text)
    total_cards: int
    total_results: int

  @staticmethod
  async def card_search(search_key: str, limit: Optional[int] = None):
    return await userdata.cards_stats_search(
      search_key,
      cutoff=45,
      ratio=ratio,
      processor=process_text,
      limit=limit
    )

  @staticmethod
  async def card_count():
    return await userdata.cards_roster_count(unobtained=False)

  @staticmethod
  async def card_fetch(card_id: str):
    cards = await userdata.cards_stats([card_id], unobtained=False)
    if len(cards) > 0:
      return cards[0]
    return None


  async def autocomplete(self, input_text: str):
    # Short circuit on empty length
    if len(input_text) < 1:
      return await self.send_autocomplete()

    # Input text for prompt
    options = [self.option(input_text, input_text)]

    # ID search
    if input_text.startswith("@"):
      if card_by_id := await self.card_fetch(input_text[1:]):
        options.append(self.option(truncate(f"@ {card_by_id.name}"), input_text))

    # Everything else, but input text must be length >= 3
    if len(input_text) < 3:
      return await self.send_autocomplete(options)

    options.extend([
      self.option(
        truncate(
          (("★" * card.rarity) if card.rarity <= 6 else f"{card.rarity}★") + f" {card.name}"
        ),
        f"@{card.card}"
      )
      for card in await self.card_search(input_text, 9-len(options))
    ])
    await self.send_autocomplete(options)


  async def run(self, search_key: str):
    card_by_id = None
    if search_key.startswith("@"):
      card_by_id = await self.card_fetch(search_key[1:])

    if not card_by_id:
      return await self.search(search_key)
    return await self.view(card_by_id)


  async def search(self, search_key: str):
    await self.defer(suppress_error=True)

    search_results = await self.card_search(search_key)
    total_cards    = await self.card_count()
    total_results  = len(search_results)

    self.data = self.Data(search_key, total_cards, total_results)
    if total_cards <= 0:
      return await self.send(self.States.NO_ACQUIRED)
    if total_results <= 0:
      return await self.send(self.States.NO_RESULTS)

    escapes = ["search_key", "name", "type", "series"]
    self.field_data = search_results
    self.selection_values = [
      StringSelectOption(
        label=truncate(card.name),
        value=card.card,
        description=truncate(
          (("★" * card.rarity) if card.rarity <= 6 else f"{card.rarity}★")
          + f" • {card.type} • {card.series}"
        )
      )
      for card in search_results
    ]
    self.selection_placeholder = "Select a card to view"
    return await self.send_selection(
      self.States.SEARCH_RESULTS, template_kwargs={"escape_data_values": escapes}, timeout=45
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.create(ctx).view_from_select()


  async def view_from_select(self, edit_origin: bool = True):
    return await self.view(self.ctx.values[0], edit_origin=edit_origin)


  async def view_from_button(self):
    return await self.view(CustomID.get_id_from(self.ctx), edit_origin=False)


  async def view(self, card: Union[StatsCard, str], edit_origin: bool = True):
    if edit_origin and self.has_origin:
      await self.defer(edit_origin=True, suppress_error=True)
    else:
      await self.defer(suppress_error=True)

    if isinstance(card, str):
      if fetched_card := await self.card_fetch(card):
        card = fetched_card
      else:
        return await Errors.create(self.ctx).card_not_found(card)

    escapes = ["search_key", "name", "type", "series"]

    user_card = await userdata.card_user(self.caller_id, card.card)
    if user_card:
      return await self.send(
        self.States.VIEW_ACQUIRED,
        other_data=card.asdict() | user_card.asdict(),
        template_kwargs={
          "escape_data_values": escapes,
          "use_string_templates": [self.Strings.MULTIPLE_OWNERS] if card.users > 1 else []
        },
        components=[]
      )
    else:
      return await self.send(
        self.States.VIEW_UNACQUIRED,
        other_data=card.asdict(),
        template_kwargs={
          "escape_data_values": escapes,
          "use_string_templates": [self.Strings.MULTIPLE_OWNERS] if card.users > 1 else []
        },
        components=[]
      )


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
    CARDS    = "gacha_view_admin_cards"

  @define(slots=False)
  class Data(AsDict):
    total_cards: int


  async def run(self, sort: Optional[str] = None):
    await assert_bot_owner(self.ctx)
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
    await assert_bot_owner(self.ctx)
    await self.defer(ephemeral=True, suppress_error=True)

    gacha.reload()
    await gacha.sync_db()

    self.data = self.Data(cards=len(gacha.cards))
    await self.send(self.States.RELOAD)


class UploadAdmin(WriterCommand):
  state: "UploadAdmin.States"

  class States(StrEnum):
    ERROR_DOWNLOAD = "gacha_admin_upload_error_download"
    ERROR_PARSE = "gacha_admin_upload_error_parse"
    PROMPT = "gacha_admin_upload_prompt"
    SUCCESS = "gacha_admin_upload_success"


  async def run(self, file: Attachment):
    await assert_bot_owner(self.ctx)
    await self.defer(ephemeral=True, suppress_error=True)

    async with aiohttp.ClientSession() as session:
      async with session.get(file.url) as response:
        try:
          response.raise_for_status()
        except Exception as e:
          await self.send(
            self.States.ERROR_DOWNLOAD,
            other_data={"message": str(e)}
          )
          return
        try:
          data = safe_load(await response.text())
        except YAMLError as e:
          await self.send(
            self.States.ERROR_PARSE,
            other_data={"message": str(e)}
          )
          return

    new_cards = api.Card.parse_all(data, ignore_error=True)

    # TODO: Diff cards
    count_old = await api.Card.count(unlisted=True, unobtained=True)
    count_added = 0
    count_changed = 0
    count_unchanged = 0

    for new_card in new_cards:
      old_card = await api.Card.fetch(new_card.id)
      if old_card is None:
        count_add += 1
      elif new_card == old_card:
        count_unchanged += 1
      else:
        count_changed += 1
    count_removed = count_old - count_changed - count_unchanged

    await self.send(
      self.States.PROMPT,
      other_data={
        "count": len(new_cards),
        "count_added": count_added,
        "count_removed": count_removed,
        "count_changed": count_changed,
        "count_unchanged": count_unchanged,
      }
    )


class BannerAdmin(SelectionMixin, ReaderCommand):
  class States(StrEnum):
    LIST = "gacha_admin_banner_list"
    LIST_EMPTY = "gacha_admin_banner_list"

    VIEW = "gacha_admin_banner_view"

    CREATE_ERROR = "gacha_admin_banner_create_error"
    CREATE_SUCCESS = "gacha_admin_banner_create_success"


  async def list(self):
    banners = await api.Banner.fetch_all()
    current = await api.Banner.count(current_on=self.ctx.id.created_at)
    components = [
      ActionRow(
        Button(
          style=ButtonStyle.GREEN,
          label="Add...",
          custom_id=CustomIDs.BANNER.prompt()
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Refresh",
          custom_id=CustomIDs.BANNER
        )
      )
    ]

    if len(banners) <= 0:
      await self.send(self.States.LIST_EMPTY, components=components)
      return

    self.field_data = banners
    self.selection_values = [
      StringSelectOption(
        label=banner.name,
        value=banner.id,
      )
      for banner in banners
    ]
    self.selection_placeholder = "Banner to configure..."

    await self.send_selection(
      self.States.LIST,
      other_data={
        "count": len(banners),
        "count_active": len([banner for banner in banners if banner.active]),
        "count_current": current
      },
      extra_components=components
    )


  async def prompt(self):
    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Banner Name",
          custom_id="name",
          placeholder="e.g. \"Summer\"",
          required=True,
        ),
        ShortText(
          label="Start Time (UTC+0)",
          custom_id="start_time_s",
          placeholder="e.g. 2024-06-01 00:00:00",
          required=True,
        ),
        ShortText(
          label="End Time (UTC+0)",
          custom_id="end_time_s",
          placeholder="e.g. 2024-09-30 00:00:00",
          required=True,
        ),
        title="Create Banner",
        custom_id=CustomIDs.BANNER.response()
      )
    )