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
# Frontend functions (shards)
# ===================================================================
  

async def get_shards(user_id: Snowflake):
  statement = (
    select(Currency.amount)
    .where(Currency.user == user_id)
  )
  async with new_session() as session:
    shards = await session.scalar(statement)
  
  return shards if shards else 0
  

async def set_shards(
  session: AsyncSession,
  user_id: Snowflake,
  amount: int,
  daily: bool = False
):
  if amount < 0:
    raise ValueError(f"Invalid set amount of '{amount}' shards")

  current_time = time()
  assign_last_daily = dict(last_daily=current_time) if daily else {}
  
  statement = (
    insert(Currency)
    .values(user=user_id, amount=amount, **assign_last_daily)
    .on_conflict_do_update(
      index_elements=['user'],
      set_=dict(amount=amount, **assign_last_daily)
    )
  )
  await session.execute(statement)


async def is_enough_shards(user_id: Snowflake, amount: int):
  current_amount = await get_shards(user_id)
  new_amount     = current_amount - amount

  return new_amount >= 0


async def modify_shards(session: AsyncSession, user_id: Snowflake, amount: int, daily: bool = False):
  current_amount = await get_shards(user_id)
  
  if current_amount is None:
    new_amount = amount
  else:
    new_amount = current_amount + amount

  await set_shards(session, user_id, new_amount, daily=daily)


# def take_shards(session: AsyncSession, user: int, amount: int):
#   current_amount = get_shards(user)
  
#   new_amount = current_amount - amount
#   if new_amount < 0:
#     raise ValueError(
#       f"User '{user}' has not enough shards "
#       f"(has {current_amount}, requested {amount})"
#     )
  
#   set_shards(session, user, new_amount)
  

async def get_last_daily(user_id: Snowflake):
  statement = (
    select(Currency.last_daily)
    .where(Currency.user == user_id)
  )
  async with new_session() as session:
    return await session.scalar(statement)
  
  
async def is_daily_available(user_id: Snowflake, tz: int = 0):
  last_daily_data = await get_last_daily(user_id)
  if last_daily_data is None:
    return True
  
  daily_tz   = timezone(timedelta(hours=tz))
  
  last_daily = datetime.fromtimestamp(last_daily_data, tz=timezone.utc)
  curr_time  = datetime.now(tz=daily_tz)

  return curr_time.date() > last_daily.astimezone(daily_tz).date()
  

# ===================================================================
# Card functions
# ===================================================================


async def user_has_card(user_id: Snowflake, card: SourceCard):
  return await get_card_count(user_id, card) is not None


async def get_card_count(user_id: Snowflake, card: SourceCard):
  statement = (
    select(Inventory.count)
    .where(Inventory.user == user_id)
    .where(Inventory.card == card.id)
    .limit(1)
  )
  async with new_session() as session:
    return await session.scalar(statement)
  

async def list_cards(user_id: Snowflake):
  statement = (
    select(Inventory)
    .where(Inventory.user == user_id)
    .order_by(Inventory.rarity.desc())
    .order_by(Inventory.first_acquired.desc())
  )

  async with new_session() as session:
    data = (await session.scalars(statement)).all()
  
  result = {}
  for row in data:
    result[row.card] = row
  
  return result


async def give_card(session: AsyncSession, user_id: Snowflake, card: SourceCard):
  current_count = await get_card_count(user_id, card)
  new_card      = current_count is None
  new_count     = 1 if new_card else current_count + 1
  current_time  = time()

  if new_card: 
    set_statement_inventory = (
      insert(Inventory)
      .values(
        user=user_id,
        rarity=card.rarity,
        card=card.id,
        count=new_count,
        first_acquired=current_time
      )
    )
  else:
    set_statement_inventory = (
      update(Inventory)
      .where(Inventory.user == user_id)
      .where(Inventory.card == card.id)
      .values(count=new_count)
    )
  
  set_statement_rolls = (
    insert(Rolls)
    .values(
      user=user_id,
      rarity=card.rarity,
      card=card.id,
      time=current_time
    )
  )

  await session.execute(set_statement_inventory)
  await session.execute(set_statement_rolls)

  return new_card


async def get_user_pity(user_id: Snowflake):
  statement = (
    select(Pity)
    .where(Pity.user == user_id)
  )
  async with new_session() as session:
    user_pity = await session.scalar(statement)
  
  if user_pity is None:
    return None
  else:
    return {
      1: user_pity.counter1,
      2: user_pity.counter2,
      3: user_pity.counter3,
      4: user_pity.counter4,
      5: user_pity.counter5,
      6: user_pity.counter6,
      7: user_pity.counter7,
      8: user_pity.counter8,
      9: user_pity.counter9,
    }


async def check_user_pity(pity_settings: Dict[int, int], user_id: Snowflake):
  user_pity = await get_user_pity(user_id)
  if user_pity is None:
    return None
  
  pity_rarity = None
  for rarity in user_pity.keys():
    if rarity not in pity_settings.keys():
      continue
    if pity_settings[rarity] <= 1:
      continue

    if (user_pity[rarity] + 1) >= pity_settings[rarity]:
      pity_rarity = rarity
  
  return pity_rarity


async def update_user_pity(
  session: AsyncSession,
  pity_settings: Dict[int, int],
  user_id: Snowflake,
  rolled_rarity: int
):
  has_pity      = pity_settings.keys()
  user_pity     = await get_user_pity(user_id)
  if user_pity is None:
    new_user_pity = {rarity+1: 0 for rarity in range(9)}
  else:
    new_user_pity = user_pity.copy()

  for rarity in has_pity:
    if rarity == rolled_rarity:
      new_user_pity[rarity]  = 0
    elif rarity > rolled_rarity:
      new_user_pity[rarity] += 1
  
  kwargs = dict(
    counter1=new_user_pity[1],
    counter2=new_user_pity[2],
    counter3=new_user_pity[3],
    counter4=new_user_pity[4],
    counter5=new_user_pity[5],
    counter6=new_user_pity[6],
    counter7=new_user_pity[7],
    counter8=new_user_pity[8],
    counter9=new_user_pity[9]
  )
  
  statement = (
    insert(Pity)
    .values(user=user_id, **kwargs)
    .on_conflict_do_update(
      index_elements=["user"],
      set_=kwargs
    )
  )

  await session.execute(statement)


# =================================================================================================
# NEW


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
  # The steps are awkward because Inventory currently lacks composite primary keys

  count = await card_count(user_id, card)
  current_time = time()

  # Using phony non-Card rarity columns pending removal
  inventory_statement = (
    insert(Inventory)
      .values(user=user_id, card=card.id, rarity=0, first_acquired=current_time, count=1)
    if count == 0 else
    update(Inventory)
      .where(Inventory.user == user_id)
      .where(Inventory.card == card.id)
      .values(count=count + 1)
  )
  rolls_statement = (
    insert(Rolls)
    .values(user=user_id, card=card.id, rarity=0, time=current_time)
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
  if len(await pity_get(user_id)) == 0:
    gen_statement = lambda ra: insert(Pity2).values(user=user_id, rarity=ra)
    gen_count = lambda rb: 0 if rb == rolled_rarity else 1
  else:
    gen_statement = lambda ra: update(Pity2).where(Pity2.user == user_id).where(Pity2.rarity == ra)
    gen_count = lambda rb: 0 if rb == rolled_rarity else Pity2.__table__.c.count + 1

  rarities  = sorted(pity_settings.keys())
  for rarity in rarities:
    if pity_settings[rarity] <= 1:
      continue
    
    await session.execute(gen_statement(rarity).values(count=gen_count(rarity)))


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