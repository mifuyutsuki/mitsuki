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


# ===================================================================
# Gachaman functions
# ===================================================================


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