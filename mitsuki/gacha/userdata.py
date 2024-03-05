# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Dict, Optional
from time import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from interactions import BaseUser

from mitsuki.userdata import Base, engine
from mitsuki.gacha.gachaman import Card


# ===================================================================


class Rolls(Base):
  __tablename__ = "gacha_rolls"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  user: Mapped[int]
  rarity: Mapped[int]
  card: Mapped[str]
  time: Mapped[float]

  def __repr__(self):
    return (
      f"Rolls(id={self.id!r}, user={self.user!r}, "
      f"time={self.time!r}, card={self.card!r}, rarity={self.rarity!r})"
    )
  

class Currency(Base):
  __tablename__ = "gacha_currency"

  user: Mapped[int] = mapped_column(primary_key=True)
  amount: Mapped[int]
  last_daily: Mapped[Optional[float]]
  
  def __repr__(self):
    return (
      f"Currency(user={self.user!r}, amount{self.amount!r}, "
      f"last_daily={self.last_daily!r})"
    )


class Inventory(Base):
  __tablename__ = "gacha_inventory"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  user: Mapped[int]
  rarity: Mapped[int]
  card: Mapped[str]
  count: Mapped[int]
  first_acquired: Mapped[Optional[float]]

  def __repr__(self):
    return (
      f"Inventory(id={self.id!r}, user={self.user!r}, "
      f"rarity={self.rarity!r}, card={self.card!r}, count={self.count!r}, "
      f"first_acquired={self.first_acquired!r})"
    )


class Pity(Base):
  __tablename__ = "gacha_pity"

  user: Mapped[int] = mapped_column(primary_key=True)
  counter1: Mapped[int]
  counter2: Mapped[int]
  counter3: Mapped[int]
  counter4: Mapped[int]
  counter5: Mapped[int]
  counter6: Mapped[int]
  counter7: Mapped[int]
  counter8: Mapped[int]
  counter9: Mapped[int]

  def __repr__(self):
    return (
      f"Pity(user={self.user!r}, "
      f"counter1={self.counter1!r}, "
      f"counter2={self.counter2!r}, "
      f"counter3={self.counter3!r}, "
      f"counter4={self.counter4!r}, "
      f"counter5={self.counter5!r}, "
      f"counter6={self.counter6!r}, "
      f"counter7={self.counter7!r}, "
      f"counter8={self.counter8!r}, "
      f"counter9={self.counter9!r})"
    )


# ===================================================================
# Frontend functions (shards)
# ===================================================================
  

async def get_shards(user: BaseUser):
  statement = (
    select(Currency.amount)
    .where(Currency.user == user.id)
  )
  async with AsyncSession(engine) as session:
    shards = await session.scalar(statement)
  
  return shards if shards else 0
  

async def set_shards(
  session: AsyncSession,
  user: BaseUser,
  amount: int,
  daily: bool = False
):
  if amount < 0:
    raise ValueError(f"Invalid set amount of '{amount}' shards")
  
  if daily:
    current_time = time()
    statement = (
      insert(Currency)
      .values(user=user.id, amount=amount, last_daily=current_time)
      .on_conflict_do_update(
        index_elements=['user'],
        set_=dict(amount=amount, last_daily=current_time)
      )
    )
  else:
    statement = (
      insert(Currency)
      .values(user=user.id, amount=amount)
      .on_conflict_do_update(
        index_elements=['user'],
        set_=dict(amount=amount)
      )
    )
  
  await session.execute(statement)


async def is_enough_shards(user: BaseUser, amount: int):
  current_amount = await get_shards(user)
  new_amount     = current_amount - amount

  return new_amount >= 0


async def modify_shards(session: AsyncSession, user: BaseUser, amount: int, daily: bool = False):
  current_amount = await get_shards(user)
  
  if current_amount is None:
    new_amount = amount
  else:
    new_amount = current_amount + amount

  await set_shards(session, user, new_amount, daily=daily)


# def take_shards(session: AsyncSession, user: int, amount: int):
#   current_amount = get_shards(user)
  
#   new_amount = current_amount - amount
#   if new_amount < 0:
#     raise ValueError(
#       f"User '{user}' has not enough shards "
#       f"(has {current_amount}, requested {amount})"
#     )
  
#   set_shards(session, user, new_amount)
  

async def get_last_daily(user: BaseUser):
  statement = (
    select(Currency.last_daily)
    .where(Currency.user == user.id)
  )
  async with AsyncSession(engine) as session:
    return await session.scalar(statement)
  
  
async def is_daily_available(user: BaseUser, tz: int = 0):
  last_daily_data = await get_last_daily(user)
  if last_daily_data is None:
    return True
  
  daily_tz   = timezone(timedelta(hours=tz))
  
  last_daily = datetime.fromtimestamp(last_daily_data, tz=timezone.utc)
  curr_time  = datetime.now(tz=daily_tz)

  return curr_time.date() > last_daily.astimezone(daily_tz).date()
  

# ===================================================================
# Card functions
# ===================================================================


async def user_has_card(user: BaseUser, card: Card):
  return await get_card_count(user, card) is not None


async def get_card_count(user: BaseUser, card: Card):
  statement = (
    select(Inventory.count)
    .where(Inventory.user == user.id)
    .where(Inventory.card == card.id)
    .limit(1)
  )
  async with AsyncSession(engine) as session:
    return await session.scalar(statement)
  

async def list_cards(user: BaseUser):
  statement = (
    select(Inventory)
    .where(Inventory.user == user.id)
    .order_by(Inventory.rarity.desc())
    .order_by(Inventory.first_acquired.desc())
  )

  async with AsyncSession(engine) as session:
    data = (await session.scalars(statement)).all()
  
  result = {}
  for row in data:
    result[row.card] = row
  
  return result


async def give_card(session: AsyncSession, user: BaseUser, card: Card):
  current_count = await get_card_count(user, card)
  new_card      = current_count is None
  new_count     = 1 if new_card else current_count + 1
  current_time  = time()

  if new_card: 
    set_statement_inventory = (
      insert(Inventory)
      .values(
        user=user.id,
        rarity=card.rarity,
        card=card.id,
        count=new_count,
        first_acquired=current_time
      )
    )
  else:
    set_statement_inventory = (
      update(Inventory)
      .where(Inventory.user == user.id)
      .where(Inventory.card == card.id)
      .values(count=new_count)
    )
  
  set_statement_rolls = (
    insert(Rolls)
    .values(
      user=user.id,
      rarity=card.rarity,
      card=card.id,
      time=current_time
    )
  )

  await session.execute(set_statement_inventory)
  await session.execute(set_statement_rolls)

  return new_card


async def get_user_pity(user: BaseUser):
  statement = (
    select(Pity)
    .where(Pity.user == user.id)
  )
  async with AsyncSession(engine) as session:
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


async def check_user_pity(pity_settings: Dict[int, int], user: BaseUser):
  user_pity = await get_user_pity(user)
  if user_pity is None:
    return None
  
  pity_rarity = None
  for rarity in user_pity.keys():
    if rarity not in pity_settings.keys():
      continue

    if (user_pity[rarity] + 1) >= pity_settings[rarity]:
      pity_rarity = rarity
  
  return pity_rarity


async def update_user_pity(
  session: AsyncSession,
  pity_settings: Dict[int, int],
  user: BaseUser,
  rolled_rarity: int
):
  has_pity      = pity_settings.keys()
  user_pity     = await get_user_pity(user)
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
    .values(user=user.id, **kwargs)
    .on_conflict_do_update(
      index_elements=["user"],
      set_=kwargs
    )
  )

  await session.execute(statement)
  