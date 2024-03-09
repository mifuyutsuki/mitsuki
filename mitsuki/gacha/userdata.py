# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Dict, List
from time import time
from datetime import datetime, timezone, timedelta
from interactions import Snowflake
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as slinsert
from sqlalchemy.dialects.postgresql import insert as pginsert
from sqlalchemy.ext.asyncio import AsyncSession

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


async def daily_give(session: AsyncSession, user_id: Snowflake, amount: int):
  await _daily_add(session, user_id, amount)


async def daily_check(user_id: Snowflake, reset_time: str = "00:00+0000"):
  last_daily_data = await daily_last(user_id)
  if last_daily_data is None:
    return True
   
  return datetime.now().timestamp() > _daily_next(last_daily_data, reset_time)


async def daily_last(user_id: Snowflake):
  statement = select(Currency.last_daily).where(Currency.user == user_id)

  async with new_session() as session:
    return await session.scalar(statement)
  

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


async def card_has(user_id: int, card: SourceCard):
  return (await card_count(user_id, card)) > 0


async def card_count(user_id: int, card: SourceCard):
  statement = (
    select(Inventory.count)
    .where(Inventory.user == user_id)
    .where(Inventory.card == card.id)
  )
  async with new_session() as session:
    count = await session.scalar(statement)
  
  return count or 0


async def card_list(user_id: Snowflake, sort: str = "rarity-date"):
  statement = (
    select(Inventory, Card, Settings)
    .join(Card, Inventory.card_ref)
    .join(Settings, Card.rarity_ref)
    .where(Inventory.card == Card.id)
    .where(Inventory.user == user_id)
  )

  sort = sort.lower()
  if sort == "rarity":
    statement = statement.order_by(Card.rarity.desc()).order_by(Inventory.first_acquired.desc())
  elif sort == "rarity-date":
    statement = statement.order_by(Card.rarity.desc()).order_by(Inventory.first_acquired.desc())
  elif sort == "rarity-alpha":
    statement = statement.order_by(Card.rarity.desc()).order_by(Card.name)
  elif sort == "alpha":
    statement = statement.order_by(Card.name)
  elif sort == "date":
    statement = statement.order_by(Inventory.first_acquired.desc())
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")
  
  async with new_session() as session:
    results = (await session.execute(statement)).all()
  
  return UserCard.create_many(results)


async def card_list_all(sort: str = "rarity-alpha"):
  statement = select(Card, Settings).join(Settings, Card.rarity_ref)
  
  sort = sort.lower()
  if sort == "rarity-alpha":
    statement = statement.order_by(Card.rarity.desc()).order_by(Card.name)
  elif sort == "alpha":
    statement = statement.order_by(Card.name)
  elif sort == "type-series":
    statement = statement.order_by(Card.type).order_by(Card.series)
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return RosterCard.from_db_many(results)


async def card_list_all_obtained(sort: str = "rarity-alpha"):
  statement = (
    select(Card)
    .join(Inventory, Card.id == Inventory.card)
  )
  
  sort = sort.lower()
  if sort == "rarity-alpha":
    statement = statement.order_by(Card.rarity.desc()).order_by(Card.name)
  elif sort == "alpha":
    statement = statement.order_by(Card.name)
  elif sort == "type-series":
    statement = statement.order_by(Card.type).order_by(Card.series)
  else:
    raise ValueError(f"Invalid sort setting '{sort}'")

  async with new_session() as session:
    results = (await session.execute(statement)).all()

  return RosterCard.from_db_many(results)


async def card_give(session: AsyncSession, user_id: Snowflake, card: SourceCard):
  count = await card_count(user_id, card)
  current_time = time()

  inventory_statement = (
    insert(Inventory)
      .values(user=user_id, card=card.id, first_acquired=current_time, count=1)
      .on_conflict_do_update(
        index_elements=["user", "card"],
        set_=dict(count=Inventory.__table__.c.count + 1)
      )
  )
  rolls_statement = (
    insert(Rolls)
    .values(user=user_id, card=card.id, time=current_time)
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
  daily: bool = False
):
  if amount < 0:
    raise ValueError(f"Invalid set amount of '{amount}' shards")

  assign_last_daily = {"last_daily": time()} if daily else {}
  
  statement = (
    insert(Currency)
    .values(user=user_id, amount=amount, **assign_last_daily)
    .on_conflict_do_update(
      index_elements=['user'],
      set_=dict(amount=amount, **assign_last_daily)
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

  await _shards_set(session, user_id, new_amount, daily=True)


async def _daily_last(user_id: Snowflake):
  statement = select(Currency.last_daily).where(Currency.user == user_id)

  async with new_session() as session:
    return await session.scalar(statement)


async def _daily_check(user_id: Snowflake, reset_time: str = "00:00+0000"):
  last_daily_data = await _daily_last(user_id)
  if last_daily_data is None:
    return True
   
  return datetime.now().timestamp() > _daily_next(last_daily_data, reset_time)


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