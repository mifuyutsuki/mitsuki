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
from datetime import datetime, timezone, timedelta
from interactions import Snowflake
from sqlalchemy import select, update
from sqlalchemy.orm import load_only
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import case
from sqlalchemy.dialects.sqlite import insert as slinsert
from sqlalchemy.dialects.postgresql import insert as pginsert
from sqlalchemy.ext.asyncio import AsyncSession
from rapidfuzz import fuzz

from mitsuki.userdata import engine, new_session
from mitsuki.gacha.schema import *

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


async def daily_give(session: AsyncSession, user_id: Snowflake, amount: int, first: bool = False):
  await _daily_add(session, user_id, amount, first=first)


async def daily_check(user_id: Snowflake, reset_time: str = "00:00+0000"):
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
  

def daily_next(from_time: Optional[float] = None, reset_time: str = "00:00+0000"):
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


async def card_get_user(user_id: int, card_id: str):
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


async def card_list(user_id: Snowflake, sort: str = "rarity"):
  statement = (
    select(Inventory, Card, Settings)
    .join(Card, Inventory.card == Card.id)
    .join(Settings, Card.rarity == Settings.rarity)
    .where(Inventory.card == Card.id)
    .where(Inventory.user == user_id)
  )

  sort = sort.lower()
  if sort == "rarity":
    statement = statement.order_by(Card.rarity.desc()).order_by(Inventory.first_acquired.desc())
  elif sort == "alpha":
    statement = statement.order_by(func.lower(Card.name))
  elif sort == "date":
    statement = statement.order_by(Inventory.first_acquired.desc())
  elif sort == "series":
    statement = statement.order_by(Card.type).order_by(Card.series).order_by(Card.rarity).order_by(Card.id)
  elif sort == "count":
    statement = statement.order_by(Inventory.count.desc()).order_by(Inventory.first_acquired.desc())
  elif sort == "id":
    statement = statement.order_by(Card.id)
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")
  
  async with new_session() as session:
    results = (await session.execute(statement)).all()
  
  return UserCard.create_many(results)


async def card_list_count(user_id: Optional[Snowflake] = None, unobtained: bool = False):
  if user_id:
    statement = select(func.count(Inventory.card)).where(Inventory.user == user_id)
  elif not unobtained:
    obtained = select(Inventory.card.distinct().label("card")).subquery()
    statement = select(func.count(obtained.c.card))
  else:
    statement = select(func.count(Card.id))
  
  async with new_session() as session:
    result = (await session.scalar(statement))

  return result or 0


async def card_list_all(sort: str = "id"):
  statement = select(Card, Settings).join(Settings, Card.rarity == Settings.rarity)
  
  sort = sort.lower()
  if sort == "rarity":
    statement = statement.order_by(Card.rarity.desc()).order_by(func.lower(Card.name))
  elif sort == "alpha":
    statement = statement.order_by(func.lower(Card.name))
  elif sort == "series":
    statement = statement.order_by(Card.type).order_by(Card.series).order_by(Card.rarity).order_by(Card.id)
  elif sort == "id":
    statement = statement.order_by(Card.id)
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return RosterCard.from_db_many(results)


async def card_list_all_obtained(sort: str = "rarity"):
  # To prevent bare columns, the statement is this long
  subq_counts = (
    select(
      Inventory.card.label("card"),
      func.count(Inventory.count).label("users"),
      func.sum(Inventory.count).label("rolled"),
      func.min(Inventory.first_acquired).label("first_user_acquired")
    )
    .group_by(Inventory.card)
    .subquery()
  )
  subq_info = (
    select(subq_counts, Card, Settings)
    .join(Card, subq_counts.c.card == Card.id)
    .join(Settings, Card.rarity == Settings.rarity)
    .subquery()
  )
  card = subq_info.c
  statement = (
    select(
      subq_info,
      Inventory.user.label("first_user")
    )
    .join(Inventory, Inventory.first_acquired == card.first_user_acquired)
  )
  
  sort = sort.lower()
  if sort == "rarity":
    statement = statement.order_by(card.rarity.desc()).order_by(func.lower(card.name))
  elif sort == "alpha":
    statement = statement.order_by(func.lower(card.name))
  elif sort == "series":
    statement = statement.order_by(card.type).order_by(card.series).order_by(card.rarity).order_by(card.id)
  elif sort == "id":
    statement = statement.order_by(card.id)
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return StatsCard.from_db_many(results)


async def card_search(
  search_key: str,
  user_id: Optional[Snowflake] = None,
  *,
  unobtained: bool = False,
  search_by: str = "name",
  sort: str = "match",
  limit: Optional[int] = None,
  cutoff: float = 60.0,
  strong_cutoff: Optional[float] = None,
  ratio: Callable[[str, str], str] = fuzz.WRatio,
  processor: Optional[Callable[[str], str]] = None,
) -> List[StatsCard]:
  cards = await card_key_search(
    search_key,
    user_id,
    unobtained=unobtained,
    search_by=search_by,
    cutoff=cutoff,
    ratio=ratio,
    processor=processor
  )

  # If strong_cutoff is set, card_ids will only have one result if only one result has score >= strong_cutoff
  # SearchCard is already sorted by match so just check the first two

  if len(cards) <= 0:
    return []
  elif len(cards) >= 2 and strong_cutoff:
    if cards[0].score >= strong_cutoff > cards[1].score:
      card_ids = [cards[0].id]
    else:
      card_ids = [c.id for c in cards]
  else:
    card_ids = [c.id for c in cards]

  # -----

  # To prevent bare columns, the statement is this long
  subq_counts = (
    select(
      Inventory.card.label("card"),
      func.count(Inventory.count).label("users"),
      func.sum(Inventory.count).label("rolled"),
      func.min(Inventory.first_acquired).label("first_user_acquired")
    )
    .group_by(Inventory.card)
    .subquery()
  )
  subq_info = (
    select(
      Card,
      Settings,
      func.coalesce(subq_counts.c.users, 0).label("users"),
      func.coalesce(subq_counts.c.rolled, 0).label("rolled"),
      subq_counts.c.first_user_acquired.label("first_user_acquired")
    )
    .join(subq_counts, Card.id == subq_counts.c.card, isouter=unobtained)
    .join(Settings, Card.rarity == Settings.rarity)
    .subquery()
  )
  card = subq_info.c
  result_statement = (
    select(subq_info, Inventory.user.label("first_user"))
    .join(Inventory, Inventory.first_acquired == card.first_user_acquired, isouter=unobtained)
    .where(card.id.in_(card_ids))
  )
  
  if len(card_ids) > 1:
    match sort.lower():
      case "match":
        result_statement = result_statement.order_by(_insertion_order(card.id, card_ids))
      case "rarity":
        result_statement = result_statement.order_by(card.rarity.desc()).order_by(func.lower(card.name))
      case "alpha":
        result_statement = result_statement.order_by(func.lower(card.name))
      case "name":
        result_statement = result_statement.order_by(func.lower(card.name))
      case "series":
        result_statement = result_statement.order_by(card.type).order_by(card.series).order_by(card.rarity).order_by(card.id)
      case "id":
        result_statement = result_statement.order_by(card.id)
      case _:
        raise ValueError(f"Invalid sort setting '{sort}'")

    result_statement = result_statement.limit(limit)

  async with new_session() as session:
    results = (await session.execute(result_statement)).all()

  return StatsCard.from_db_many(results)


async def card_key_search(
  search_key: str,
  user_id: Optional[Snowflake] = None,
  *,
  unobtained: bool = False,
  search_by: str = "name",
  cutoff: float = 60.0,
  ratio: Callable[[str, str], str] = fuzz.token_ratio,
  processor: Optional[Callable[[str], str]] = None,
):
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

  pity_rarities = sorted(pity_settings.keys(), reverse=True)
  for pity_rarity in pity_rarities:
    if pity_settings[pity_rarity] <= 1:
      continue
    if pity_rarity not in user_pity.keys():
      continue
    if user_pity[pity_rarity] + 1 >= pity_settings[pity_rarity]:
      return pity_rarity
  
  return pity_rarities[-1]


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


async def _daily_add(session: AsyncSession, user_id: Snowflake, amount: int, first: bool = False):
  current_amount = await _shards_get(user_id)
  new_amount = current_amount + amount

  await _shards_set(session, user_id, new_amount, daily=True, first=first)


async def _daily_last(user_id: Snowflake):
  statement = select(Currency.last_daily).where(Currency.user == user_id)

  async with new_session() as session:
    return await session.scalar(statement)


def _daily_next(last_daily: float, reset_time: str = "00:00+0000"):
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