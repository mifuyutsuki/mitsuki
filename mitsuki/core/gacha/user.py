# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any, Union, Self
from datetime import timezone

import attrs
import interactions as ipy
import sqlalchemy as sa
from sqlalchemy import select, update, delete, literal
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki.utils import option
from mitsuki.lib.userdata import begin_session, AsDict, sa_insert as insert
from mitsuki.lib.commands import CustomID
from mitsuki.core.settings import get_setting, Settings

import mitsuki.models.gacha as models


@attrs.define(kw_only=True)
class GachaUser(AsDict):
  """A Mitsuki Gacha user."""

  user: ipy.Snowflake = attrs.field(converter=ipy.Snowflake)
  """Gacha user ID."""
  amount: int
  """Shards owned by this user."""
  last_daily: Optional[ipy.Timestamp] = attrs.field(default=None, converter=option(ipy.Timestamp.fromtimestamp))
  """Last time this user claimed their daily, in timestamp format."""
  first_daily: Optional[ipy.Timestamp] = attrs.field(default=None, converter=option(ipy.Timestamp.fromtimestamp))
  """First time this user claimed their daily, in timestamp format."""

  claimed_daily: bool = attrs.field(default=False)
  """Whether the user just claimed daily, only set if fetched using `daily()`."""
  claimed_first_daily: bool = attrs.field(default=False)
  """Whether the user just claimed first-time daily, only set if fetched using `daily()`."""

  pity_counters: dict[int, int] = attrs.field(factory=dict)
  """This user's pity counters in the format {rarity: count}, only set if fetched using `fetch_profile()`"""
  rolled_cards: dict[int, int] = attrs.field(factory=dict)
  """Total cards rolled by this user in the format {rarity: count}, only set if fetched using `fetch_profile()`."""
  obtained_cards: dict[int, int] = attrs.field(factory=dict)
  """Unique cards rolled by this user in the format {rarity: count}, only set if fetched using `fetch_profile()`."""


  @property
  def total_rolled(self):
    """Total cards rolled by this user, only set if fetched using `fetch_profile()`."""
    return sum(self.rolled_cards.values())


  @property
  def total_obtained(self):
    """Unique cards rolled by this user, only set if fetched using `fetch_profile()`."""
    return sum(self.obtained_cards.values())


  @classmethod
  async def create(
    cls, session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake], *, now: Optional[ipy.Timestamp] = None
  ) -> Self:
    """
    Create and register a new gacha user.

    This method gives the new user a first-time daily, and creates pity counters
    for the user for any rarity with pity > 1.

    Args:
      session: Current database session
      user: Snowflake or instance of the user

    Returns:
      Instance of gacha user, or `None` if not registered
    """
    _now = now or ipy.Timestamp.now(tz=timezone.utc)
    _now = _now.timestamp()
    if isinstance(user, ipy.BaseUser):
      user = user.id

    first_time_shards = await get_setting(Settings.FirstTimeShards)
    pity_query = (
      select(sa.literal(user), models.CardRarity.rarity, sa.literal(0))
      .where(models.CardRarity.pity > 1)
    )
    user_stmt = insert(models.GachaUser).values(user=user, amount=first_time_shards, last_daily=_now, first_daily=_now)
    user_pity_stmt = insert(models.UserPity).from_select(["user", "rarity", "count"], pity_query)

    await session.execute(user_stmt)
    await session.execute(user_pity_stmt)
    return cls(
      user=user, amount=first_time_shards, last_daily=_now, first_daily=_now,
      claimed_daily=True, claimed_first_daily=True
    )


  @classmethod
  async def fetch(cls, user: Union[ipy.BaseUser, ipy.Snowflake]) -> Optional[Self]:
    """
    Fetch a gacha user.

    Args:
      session: Current database session
      user: Snowflake or instance of the user

    Returns:
      Instance of gacha user, or `None` if not registered
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id

    query = (
      select(models.GachaUser)
      .where(models.GachaUser.user == user)
    )

    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  @staticmethod
  async def fetch_guarantee(user: Union[ipy.BaseUser, ipy.Snowflake]) -> Optional[int]:
    """
    Fetch the guaranteed rarity for this user, based on their pity counter.

    Args:
      user: Snowflake or instance of the gacha user

    Returns:
      Guaranteed rarity, or `None` if user not in pity or the user is registered
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id

    stmt = (
      select(models.UserPity.rarity, models.UserPity.count, models.CardRarity.pity)
      .join(models.GachaUser, models.GachaUser.user == models.UserPity.user)
      .join(models.CardRarity, models.CardRarity.rarity == models.UserPity.rarity)
      .where(models.CardRarity.pity > 1)
    )

    async with begin_session() as session:
      results = (await session.execute(stmt)).all()

    if len(results) > 0:
      results = sorted(results, key=lambda r: r.rarity, reverse=True)
      return next([r.rarity for r in results if r.count >= r.pity], None)


  @classmethod
  async def fetch_profile(cls, user: Union[ipy.BaseUser, ipy.Snowflake]) -> Optional[Self]:
    """
    Fetch a gacha user's profile, including its pity counters and roll counts.

    Args:
      session: Current database session
      user: Snowflake or instance of the user

    Returns:
      Instance of gacha user with additional fields set, or `None` if not registered
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id

    subquery = (
      select(
        models.GachaRoll.user,
        models.Card.rarity,
        sa.func.count(models.GachaRoll.card.distinct()).label("obtained"),
        sa.func.count(models.GachaRoll.card).label("rolled"),
      )
      .join(models.Card, models.Card.id == models.GachaRoll.card)
      .group_by(models.GachaRoll.user, models.Card.rarity)
      .subquery()
    )
    query = (
      select(
        models.GachaUser,
        subquery.c.rarity,
        sa.func.coalesce(subquery.c.obtained, 0).label("obtained"),
        sa.func.coalesce(subquery.c.rolled, 0).label("rolled"),
        models.UserPity.count.label("pity"),
      )
      .join(subquery, subquery.c.user == models.GachaUser.user, isouter=True)
      .join(models.UserPity,
        (models.UserPity.user == subquery.c.user) & (models.UserPity.rarity == subquery.c.rarity),
        isouter=True
      )
      .where(models.GachaUser.user == user)
    )

    async with begin_session() as session:
      results = (await session.execute(query)).all()

    if len(results) > 0:
      return cls(
        **results[0].GachaUser.asdict(),
        pity_counters={r.rarity: r.pity for r in results if r.pity is not None},
        obtained_cards={r.rarity: r.obtained for r in results},
        rolled_cards={r.rarity: r.rolled for r in results},
      )


  @classmethod
  async def daily(
    cls, session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake], *, now: Optional[ipy.Timestamp] = None
  ) -> Self:
    """
    Claim a gacha daily, and fetch the user instance.

    A gacha user can claim one daily once a day, claimable again on the next
    daily reset (setting `gacha.daily_reset_time`).

    This method also sets the flags `claimed_daily` and `claimed_first_daily`
    on the returned instance, depending on whether a daily is claimed. If the
    user is not registered in the database, creates the user and gives them
    first-time daily.

    Args:
      session: Current database session
      user: Snowflake or instance of the user claiming daily
      now: Reference time to determine ability to claim, or current time if unset

    Returns:
      Instance of gacha user
    """
    now = now or ipy.Timestamp.now()

    if isinstance(user, ipy.BaseUser):
      user = user.id

    gacha_user = await cls.fetch(user)
    if not gacha_user:
      return await cls.create(session, user, now=now)

    # -----

    daily_reset = await get_setting(Settings.DailyResetTime)
    daily_reset_h, daily_reset_m = daily_reset.split(":")

    last_reset = now.replace(hour=int(daily_reset_h), minute=int(daily_reset_m), second=0, microsecond=0)

    if gacha_user.last_daily and last_reset < gacha_user.last_daily:
      return gacha_user

    # -----

    gacha_user.claimed_daily = True
    if gacha_user.first_daily:
      daily_shards = await get_setting(Settings.DailyShards)
    else:
      gacha_user.claimed_first_daily = True
      daily_shards = await get_setting(Settings.FirstTimeShards)

    stmt = (
      update(models.GachaUser)
      .values(amount=models.GachaUser.__table__.c.amount + daily_shards, last_daily=now.timestamp())
      .returning(models.GachaUser.amount)
    )
    gacha_user.amount = await session.scalar(stmt)
    return gacha_user


  def has_shards(self, amount: int) -> bool:
    """
    Check if this user has at least this amount of shards.

    Args:
      amount: Amount of shards to check

    Returns:
      `True` if there are at least said amount, `False` otherwise
    """
    return self.amount >= amount


  async def give_shards(self, session: AsyncSession, amount: int) -> bool:
    """
    Give gacha shards to this user.

    This method's return value indicates whether the exchange has occured. Give
    may fail if the user with this user ID does not exist.

    Args:
      session: Current database session
      amount: Amount of shards to give to this user
    
    Returns:
      True if the operation succeeded, or False otherwise
    """
    stmt = (
      update(models.GachaUser)
      .where(models.GachaUser.user == self.user)
      .values(amount=models.GachaUser.__table__.c.amount + amount)
      .returning(models.GachaUser.amount)
    )

    if new_amount := await session.scalar(stmt):
      self.amount = new_amount
    return new_amount is not None


  async def take_shards(self, session: AsyncSession, amount: int) -> bool:
    """
    Take gacha shards from this user.

    This method's return value indicates whether the exchange has occured. Take
    may fail if the user with this ID does not exist, or if this user does not
    have enough shards.

    Args:
      session: Current database session
      amount: Amount of shards to take from this user
    
    Returns:
      True if the operation succeeded, or False otherwise
    """
    stmt = (
      update(models.GachaUser)
      .where(models.GachaUser.user == self.user)
      .where(models.GachaUser.amount >= amount)
      .values(amount=models.GachaUser.__table__.c.amount - amount)
      .returning(models.GachaUser.amount)
    )

    if new_amount := await session.scalar(stmt):
      self.amount = new_amount
    return new_amount is not None


  @staticmethod
  async def increment_pity(session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake], rarity: int) -> None:
    """
    Increment a gacha user's pity counter.

    The pity counter matching the given rarity is set to 0 if pity is setup for
    the rarity, whereas counters for other rarities are incremented by 1.

    Args:
      session: Current database session
      user: Snowflake or instance of the user
      rarity: Obtained card rarity whose pity counter is to be reset
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id

    increment_stmt = (
      update(models.UserPity)
      .where(models.UserPity.user == user)
      .values(count=models.UserPity.__table__.c.count + 1)
    )
    reset_stmt = (
      update(models.UserPity)
      .where(models.UserPity.user == user)
      .where(models.UserPity.rarity == rarity)
      .values(count=0)
    )

    await session.execute(increment_stmt)
    await session.execute(reset_stmt)