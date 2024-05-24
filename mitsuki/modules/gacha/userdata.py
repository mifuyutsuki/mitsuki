# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Dict, List, Callable, Any, Union
from time import time
from datetime import datetime, timedelta
from interactions import Snowflake
from sqlalchemy import select
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import case
from sqlalchemy.dialects.sqlite import insert as slinsert
from sqlalchemy.dialects.postgresql import insert as pginsert
from sqlalchemy.ext.asyncio import AsyncSession
from rapidfuzz import fuzz

from mitsuki import settings
from mitsuki.lib.userdata import engine, new_session

from .schema import *

insert = pginsert if "postgresql" in engine.url.drivername else slinsert


# ===================================================================
# Shards functions


async def shards(user_id: Snowflake):
  return await _shards_get(user_id)


async def shards_update(session: AsyncSession, user_id: Snowflake, amount: int):
  await _shards_add(session, user_id, amount)


async def shards_give(session: AsyncSession, user_id: Snowflake, amount: int):
  await _shards_add(session, user_id, amount)


async def shards_take(session: AsyncSession, user_id: Snowflake, amount: int):
  await _shards_sub(session, user_id, amount)


async def shards_exchange(
  session: AsyncSession,
  source_user_id: Snowflake,
  target_user_id: Snowflake,
  amount: int
):
  await _shards_sub(session, source_user_id, amount)
  await _shards_add(session, target_user_id, amount)


async def shards_check(user_id: Snowflake, amount: int):
  return (await _shards_get(user_id)) >= amount


# ===================================================================
# Daily functions


async def daily_give(session: AsyncSession, user_id: Snowflake, amount: int):
  await _daily_add(session, user_id, amount)


async def daily_check(user_id: Snowflake, reset_time: Optional[str] = None):
  reset_time = reset_time or settings.mitsuki.daily_reset
  last_daily_data = await daily_last(user_id)
  if last_daily_data is None:
    return True

  return datetime.now().timestamp() > _daily_next(last_daily_data, reset_time)


async def daily_last(user_id: Snowflake):
  statement = select(Currency.last_daily).where(Currency.user == user_id)

  async with new_session() as session:
    return await session.scalar(statement)


async def daily_first_check(user_id: Snowflake):
  statement = select(Currency.first_daily).where(Currency.user == user_id)

  async with new_session() as session:
    result = await session.scalar(statement)

  return not bool(result)


def daily_next(from_time: Optional[float] = None, reset_time: Optional[str] = None):
  reset_time = reset_time or settings.mitsuki.daily_reset
  from_time = from_time or datetime.now().timestamp()
  dt = datetime.strptime(reset_time, "%H:%M%z")

  reset_tz = dt.tzinfo
  last_daily_dt = datetime.fromtimestamp(from_time, tz=reset_tz)
  next_daily_dt = last_daily_dt.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
  if last_daily_dt > next_daily_dt:
    next_daily_dt = next_daily_dt + timedelta(days=1)

  return next_daily_dt.timestamp()


# ===================================================================
# Cards functions


async def card_has(user_id: int, card_id: str):
  return (await card_count(user_id, card_id)) > 0


async def card_count(user_id: int, card_id: str):
  statement = (
    select(Inventory.count)
    .where(Inventory.user == user_id)
    .where(Inventory.card == card_id)
  )
  async with new_session() as session:
    count = await session.scalar(statement)

  return count or 0


async def card_roster(card_id: str):
  statement = (
    select(Card, Settings)
    .join(Settings, Card.rarity == Settings.rarity)
    .where(Card.id == card_id)
  )

  async with new_session() as session:
    result = (await session.execute(statement)).first()

  if not result:
    raise ValueError(f"Card with ID '{card_id}' not found in roster")
  else:
    return RosterCard.from_db(result)


async def card_user(user_id: int, card_id: str):
  statement = (
    select(Inventory, Card, Settings)
    .join(Card, Inventory.card == Card.id)
    .join(Settings, Card.rarity == Settings.rarity)
    # Sneaky letter case!
    .where(Inventory.card == card_id)
    .where(Inventory.user == user_id)
  )

  async with new_session() as session:
    result = (await session.execute(statement)).first()

  return UserCard.create(result) if result else None


async def cards_user(
  user_id: Snowflake,
  card_ids: Optional[List[str]] = None,
  sort: Optional[str] = None,
  limit: Optional[int] = None,
  offset: Optional[int] = None,
):
  statement = (
    select(Inventory, Card, Settings)
    .join(Card, Inventory.card == Card.id)
    .join(Settings, Card.rarity == Settings.rarity)
    .where(Inventory.user == user_id)
  )
  if card_ids:
    statement = statement.where(Inventory.card.in_(card_ids))

  sort = sort or "date"
  match sort.lower():
    case "rarity":
      statement = statement.order_by(Card.rarity.desc()).order_by(Inventory.first_acquired.desc())
    case "alpha":
      statement = statement.order_by(func.lower(Card.name))
    case "date":
      statement = statement.order_by(Inventory.first_acquired.desc())
    case "series":
      statement = statement.order_by(Card.type).order_by(Card.series).order_by(Card.rarity).order_by(Card.id)
    case "count":
      statement = statement.order_by(Inventory.count.desc()).order_by(Inventory.first_acquired.desc())
    case "id":
      statement = statement.order_by(Card.id)
    case "match":
      if card_ids is None:
        raise ValueError("Cannot use 'match' sort with no card_ids")
      statement = statement.order_by(_insertion_order(Card.id, card_ids))
    case _:
      raise ValueError(f"Invalid sort setting '{sort}'")

  if limit:
    statement = statement.limit(limit)
    if offset:
      statement = statement.offset(offset)

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return UserCard.create_many(results)


async def cards_user_count(user_id: Optional[Snowflake]):
  statement = select(func.count(Inventory.card)).where(Inventory.user == user_id)

  async with new_session() as session:
    result = (await session.scalar(statement))

  return result or 0


async def cards_roster(
  card_ids: Optional[List[str]] = None,
  sort: Optional[str] = None,
  limit: Optional[int] = None,
  offset: Optional[int] = None,
):
  sort = sort or "rarity"

  statement = select(Card, Settings).join(Settings, Card.rarity == Settings.rarity)
  if card_ids:
    statement = statement.where(Card.id.in_(card_ids))

  match sort.lower():
    case "rarity":
      statement = statement.order_by(Card.rarity.desc()).order_by(func.lower(Card.name))
    case "alpha":
      statement = statement.order_by(func.lower(Card.name))
    case "name":
      statement = statement.order_by(func.lower(Card.name))
    case "series":
      statement = statement.order_by(Card.type).order_by(Card.series).order_by(Card.rarity).order_by(Card.id)
    case "id":
      statement = statement.order_by(Card.id)
    case "match":
      if card_ids is None:
        raise ValueError("Cannot use 'match' sort with no card_ids")
      statement = statement.order_by(_insertion_order(Card.id, card_ids))
    case _:
      raise ValueError(f"Invalid sort setting '{sort}'")

  if limit:
    statement = statement.limit(limit)
    if offset:
      statement = statement.offset(offset)

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return RosterCard.from_db_many(results)


async def cards_roster_count(unobtained: bool = False):
  if not unobtained:
    obtained = select(Inventory.card.distinct().label("card")).subquery()
    statement = select(func.count(obtained.c.card))
  else:
    statement = select(func.count(Card.id))

  async with new_session() as session:
    result = (await session.scalar(statement))

  return result or 0


async def cards_stats(
  card_ids: Optional[List[str]] = None,
  unobtained: bool = False,
  sort: Optional[str] = None,
  limit: Optional[int] = None,
  offset: Optional[int] = None,
):
  sort = sort or "rarity"

  subq_counts = (
    select(
      Inventory.card.label("card"),
      func.count(Inventory.count).label("users"),
      func.sum(Inventory.count).label("rolled")
    )
    .group_by(Inventory.card)
    .subquery()
  )
  subq_history = (
    select(
      Rolls.card.label("card"),
      func.min(Rolls.time).label("first_user_acquired"),
      func.max(Rolls.time).label("last_user_acquired")
    )
    .group_by(Rolls.card)
    .subquery()
  )
  subq_first = (
    select(subq_history, Rolls.user.label("first_user"))
    .where(subq_history.c.first_user_acquired == Rolls.time)
    .subquery()
  )
  subq_last = (
    select(subq_history, Rolls.user.label("last_user"))
    .where(subq_history.c.last_user_acquired == Rolls.time)
    .subquery()
  )
  subq_cards = (
    select(
      Card,
      Settings,
      func.coalesce(subq_counts.c.users, 0).label("users"),
      func.coalesce(subq_counts.c.rolled, 0).label("rolled"),
      subq_first.c.first_user_acquired.label("first_user_acquired"),
      subq_first.c.first_user.label("first_user"),
      subq_last.c.last_user_acquired.label("last_user_acquired"),
      subq_last.c.last_user.label("last_user"),
    )
    .join(subq_counts, Card.id == subq_counts.c.card, isouter=unobtained)
    .join(subq_first, Card.id == subq_first.c.card, isouter=unobtained)
    .join(subq_last, Card.id == subq_last.c.card, isouter=unobtained)
    .join(Settings, Card.rarity == Settings.rarity)
    .subquery()
  )
  statement = select(subq_cards)
  card = subq_cards.c
  if card_ids:
    statement = statement.where(card.id.in_(card_ids))

  match sort.lower():
    case "rarity":
      statement = statement.order_by(card.rarity.desc()).order_by(func.lower(card.name))
    case "alpha":
      statement = statement.order_by(func.lower(card.name))
    case "name":
      statement = statement.order_by(func.lower(card.name))
    case "series":
      statement = statement.order_by(card.type).order_by(card.series, card.rarity, card.id)
    case "id":
      statement = statement.order_by(card.id)
    case "match":
      if not card_ids:
        raise ValueError("Cannot use 'match' sort with no card_ids")
      statement = statement.order_by(_insertion_order(card.id, card_ids))
    case _:
      raise ValueError(f"Invalid sort setting '{sort}'")

  if limit:
    statement = statement.limit(limit)
    if offset:
      statement = statement.offset(offset)

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return StatsCard.from_db_many(results)


async def cards_roster_search(
  search_key: str,
  user_id: Optional[Snowflake] = None,
  *,
  search_by: Optional[str] = None,
  ratio: Optional[Callable[[str, str], str]] = None,
  processor: Optional[Callable[[str], str]] = None,
  unobtained: bool = False,
  sort: Optional[str] = None,
  limit: Optional[int] = None,
  offset: Optional[int] = None,
  cutoff: Union[int, float] = 60,
  strong_cutoff: Optional[Union[int, float]] = None,
) -> List[RosterCard]:
  search_by = search_by or "name"
  sort      = sort or "match"

  cards = await card_key_search(
    search_key,
    user_id,
    unobtained=unobtained,
    search_by=search_by,
    cutoff=cutoff,
    ratio=ratio,
    processor=processor
  )

  # SearchCard is already sorted by match so just check the first two

  if len(cards) <= 0:
    return []
  if len(cards) >= 2 and strong_cutoff:
    if cards[0].score >= strong_cutoff > cards[1].score:   # Only 1 is over strong_cutoff
      card_ids = [cards[0].id]
    elif cards[0].score > cards[1].score >= strong_cutoff: # 2+ are over strong_cutoff
      card_ids = [cards[0].id]
    else:
      card_ids = [c.id for c in cards]
  else:
    card_ids = [c.id for c in cards]

  return await cards_roster(card_ids=card_ids, sort=sort, limit=limit, offset=offset)


async def cards_stats_search(
  search_key: str,
  user_id: Optional[Snowflake] = None,
  *,
  search_by: Optional[str] = None,
  ratio: Optional[Callable[[str, str], str]] = None,
  processor: Optional[Callable[[str], str]] = None,
  unobtained: bool = False,
  sort: Optional[str] = None,
  limit: Optional[int] = None,
  offset: Optional[int] = None,
  cutoff: Union[int, float] = 60,
  strong_cutoff: Optional[Union[int, float]] = None,
) -> List[StatsCard]:
  search_by = search_by or "name"
  sort      = sort or "match"

  cards = await card_key_search(
    search_key,
    user_id,
    unobtained=unobtained,
    search_by=search_by,
    cutoff=cutoff,
    ratio=ratio,
    processor=processor
  )

  # SearchCard is already sorted by match so just check the first two

  if len(cards) <= 0:
    return []
  if len(cards) >= 2 and strong_cutoff:
    if cards[0].score >= strong_cutoff > cards[1].score:   # Only 1 is over strong_cutoff
      card_ids = [cards[0].id]
    elif cards[0].score > cards[1].score >= strong_cutoff: # 2+ are over strong_cutoff
      card_ids = [cards[0].id]
    else:
      card_ids = [c.id for c in cards]
  else:
    card_ids = [c.id for c in cards]

  return await cards_stats(card_ids=card_ids, unobtained=unobtained, sort=sort, limit=limit, offset=offset)


async def card_key_search(
  search_key: str,
  user_id: Optional[Snowflake] = None,
  *,
  unobtained: bool = False,
  search_by: str = "name",
  cutoff: float = 60.0,
  ratio: Optional[Callable[[str, str], str]] = None,
  processor: Optional[Callable[[str], str]] = None,
):
  ratio     = ratio or fuzz.WRatio
  processor = processor or (lambda s: s)

  match search_by.lower():
    case "name":
      search_column = Card.name
    case "type":
      search_column = Card.type
    case "series":
      search_column = Card.series
    case _:
      raise ValueError(f"Invalid search-by setting '{search_by}'")

  search_column = search_column.label("search")

  if user_id:
    subq_filter = select(Inventory.card.label("card")).where(Inventory.user == user_id).subquery()
  elif not unobtained:
    subq_filter = select(Inventory.card.distinct().label("card")).subquery()
  else:
    subq_filter = select(Card.id.label("card")).subquery()

  search_statement = (
    select(Card.id, search_column, subq_filter)
    .join(subq_filter, Card.id == subq_filter.c.card)
    .order_by(func.lower(search_column))
  )

  async with new_session() as session:
    card_names = (await session.execute(search_statement)).all()

  return SearchCard.from_db_many(card_names, search_key, cutoff=cutoff, ratio=ratio, processor=processor)


async def card_give(session: AsyncSession, user_id: Snowflake, card_id: str):
  count = await card_count(user_id, card_id)
  current_time = time()

  inventory_statement = (
    insert(Inventory)
      .values(user=user_id, card=card_id, first_acquired=current_time, count=1)
      .on_conflict_do_update(
        index_elements=["user", "card"],
        set_=dict(count=Inventory.__table__.c.count + 1)
      )
  )
  rolls_statement = (
    insert(Rolls)
    .values(user=user_id, card=card_id, time=current_time)
  )

  await session.execute(inventory_statement)
  await session.execute(rolls_statement)

  return count == 0 # New card 


# ===================================================================
# Pity functions


async def pity_get(user_id: Snowflake):
  statement = (
    select(Pity2)
    .where(Pity2.user == user_id)
  )

  async with new_session() as session:
    results = (await session.scalars(statement)).all()

  # Standard pity output is a Dict[int, int]
  get: Dict[int, int] = {}
  for result in results:
    get[result.rarity] = result.count

  return get


async def pity_check(user_id: Snowflake, pity_settings: Dict[int, int]):
  user_pity = await pity_get(user_id)
  if len(user_pity) == 0:
    return None

  pity_rarity = None
  for rarity, pity in pity_settings.items():
    if pity > 1 and user_pity.get(rarity, 0) >= pity - 1:
      pity_rarity = max(rarity, pity_rarity or 0)

  return pity_rarity


async def pity_update(
  session: AsyncSession,
  user_id: Snowflake,
  rolled_rarity: int,
  pity_settings: Dict[int, int]
):
  rarities = sorted(pity_settings.keys())
  for rarity in rarities:
    if pity_settings[rarity] <= 1:
      continue

    statement = (
      insert(Pity2)
      .values(user=user_id, rarity=rarity, count=1)
      .on_conflict_do_update(
        index_elements=["user", "rarity"],
        set_=dict(count=0 if rarity == rolled_rarity else Pity2.__table__.c.count + 1)
      )
    )
    await session.execute(statement)


# =================================================================================================

# ===================================================================
# Shards helper functions


async def _shards_get(user_id: Snowflake):
  statement = select(Currency.amount).where(Currency.user == user_id)
  async with new_session() as session:
    amount = await session.scalar(statement)

  return amount or 0


async def _shards_set(
  session: AsyncSession,
  user_id: Snowflake,
  amount: int,
  daily: bool = False,
  first: bool = False
):
  if amount < 0:
    raise ValueError(f"Invalid set amount of '{amount}' shards")

  current_time = time()
  assign_last_daily = {"last_daily": current_time} if daily else {}
  assign_first_daily = {"first_daily": current_time} if first else {}

  statement = (
    insert(Currency)
    .values(user=user_id, amount=amount, **assign_last_daily, **assign_first_daily)
    .on_conflict_do_update(
      index_elements=['user'],
      set_=dict(amount=amount, **assign_last_daily, **assign_first_daily)
    )
  )
  await session.execute(statement)


async def _shards_add(session: AsyncSession, user_id: Snowflake, amount: int):
  current_amount = await _shards_get(user_id)
  new_amount = current_amount + amount

  await _shards_set(session, user_id, new_amount, daily=False)


async def _shards_sub(session: AsyncSession, user_id: Snowflake, amount: int):
  current_amount = await _shards_get(user_id)
  new_amount = max(0, current_amount - amount)

  await _shards_set(session, user_id, new_amount, daily=False)


async def _daily_add(session: AsyncSession, user_id: Snowflake, amount: int):
  current_amount = await _shards_get(user_id)
  new_amount = current_amount + amount
  first = await daily_first_check(user_id)

  await _shards_set(session, user_id, new_amount, daily=True, first=first)


async def _daily_last(user_id: Snowflake):
  statement = select(Currency.last_daily).where(Currency.user == user_id)

  async with new_session() as session:
    return await session.scalar(statement)


def _daily_next(last_daily: float, reset_time: str):
  dt = datetime.strptime(reset_time, "%H:%M%z")

  reset_tz = dt.tzinfo
  last_daily_dt = datetime.fromtimestamp(last_daily, tz=reset_tz)
  next_daily_dt = last_daily_dt.replace(
    hour=dt.hour, minute=dt.minute, second=0, microsecond=0
  )

  if last_daily_dt > next_daily_dt:
    next_daily_dt = next_daily_dt + timedelta(days=1)

  return next_daily_dt.timestamp()


# ===================================================================
# Query helper functions


def _insertion_order(column, items: List[Any]):
  return case(
    {item: idx for idx, item in enumerate(items)},
    value=column
  )


# ===================================================================
# Gachaman functions


async def add_card(session: AsyncSession, card: SourceCard):
  statement = (
    insert(Card)
    .values(
      id=card.id,
      name=card.name,
      rarity=card.rarity,
      type=card.type,
      series=card.series,
      image=card.image
    )
    .on_conflict_do_update(
      index_elements=['id'],
      set_=dict(
        name=card.name,
        rarity=card.rarity,
        type=card.type,
        series=card.series,
        image=card.image
      )
    )
  )

  await session.execute(statement)


async def add_cards(cards: List[SourceCard]):
  async with new_session() as session:
    for card in cards:
      await add_card(session, card)

    await session.commit()


async def add_setting(session: AsyncSession, setting: SourceSettings):
  statement = (
    insert(Settings)
    .values(
      rarity=setting.rarity,
      rate=setting.rate,
      pity=setting.pity,
      dupe_shards=setting.dupe_shards,
      color=setting.color,
      stars=setting.stars
    )
    .on_conflict_do_update(
      index_elements=['rarity'],
      set_=dict(
        rate=setting.rate,
        pity=setting.pity,
        dupe_shards=setting.dupe_shards,
        color=setting.color,
        stars=setting.stars
      )
    )
  )

  await session.execute(statement)  


async def add_settings(settings: List[SourceSettings]):
  async with new_session() as session:
    for setting in settings:
      await add_setting(session, setting)

    await session.commit()