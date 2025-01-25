# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""Mitsuki v5.0 Gacha API."""

from sqlalchemy import select, insert, update, delete, Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import case, literal_column, or_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from interactions import (
  Snowflake,
  BaseUser,
  Timestamp,
)

from yaml import safe_load
from attrs import define, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Union, Optional, Any, Tuple
from enum import IntEnum
from random import SystemRandom
import asyncio

from mitsuki import settings
from mitsuki.utils import process_text, ratio, escape_text
from mitsuki.lib.userdata import new_session, AsDict, engine
from . import schema2 as schema

insert = postgres_insert if "postgresql" in engine.url.drivername else sqlite_insert


@define(kw_only=True)
class Search:
  id: str
  result: str
  score: float

  @classmethod
  def process(cls, results: List[Tuple[str, str]], key: str, cutoff: float = 0.0, limit: Optional[int] = None):
    li = [
      cls(id=id, result=result, score=ratio(key, result, processor=process_text))
      for id, result in results
    ]
    li.sort(key=lambda s: s.score, reverse=True)
    li = [i for i in li if i.score >= cutoff]
    if limit:
      return li[:limit]
    return li


# =================================================================================================
# Base objects
# =================================================================================================


@define(kw_only=True, slots=False)
class BaseRarity(AsDict):
  rarity: int
  rate: float = field(converter=float)
  dupe_shards: int = field(default=0)
  color: int = field(converter=int)
  stars: str = field(converter=lambda s: s.strip())
  pity: Optional[int] = field(default=None)


@define(kw_only=True, slots=False)
class BasePity(AsDict):
  user: Snowflake
  rarity: int
  count: int


@define(kw_only=True, slots=False)
class BaseInventory(AsDict):
  user: Snowflake
  card: str
  count: int
  first_acquired: float


@define(kw_only=True, slots=False)
class BaseCard(AsDict):
  id: str
  name: str
  rarity: int
  type: str
  series: str
  group: str

  image: Optional[str] = field(default=None)
  tags: Optional[str] = field(default=None)

  limited: bool = field(default=False)
  locked: bool = field(default=False)
  unlisted: bool = field(default=False)


@define(kw_only=True, slots=False)
class BaseRoll(AsDict):
  user: Snowflake
  card: str
  time: float


@define(kw_only=True, slots=False)
class BaseBanner(AsDict):
  id: str
  name: str
  active: bool = field(default=False)
  start_time: Optional[float] = field(default=None)
  end_time: Optional[float] = field(default=None)
  rate: float = field(default=0.0)
  min_rarity: Optional[int] = field(default=None)
  max_rarity: Optional[int] = field(default=None)


@define(kw_only=True, slots=False)
class BaseGachaUser(AsDict):
  user: Snowflake
  amount: int
  last_daily: Optional[float] = field(default=None)
  first_daily: Optional[float] = field(default=None)


# =================================================================================================
# Non-base objects
# =================================================================================================


@define(kw_only=True, slots=False)
class Rarity(BaseRarity):
  """Gacha options for a given rarity."""

  @classmethod
  def parse(cls, rarities: List[Dict[str, Any]]):
    rarity_objects: Dict[int, Rarity] = {}

    # Read each rarity setting
    # Skip ones with unreadable required fields (value, rate)
    for rarity_data in rarities:
      try:
        rarity = int(rarity_data["value"])
        rarity_objects[rarity] = cls(
          rarity=rarity,
          rate=rarity_data["rate"],
          dupe_shards=rarity_data.get("dupe_shards", 0),
          color=rarity_data.get("color", 0x0000ff),
          stars=rarity_data.get("stars", "★" * rarity),
          pity=rarity_data.get("pity", 0),
        )
      except (KeyError, TypeError, ValueError):
        continue

    # Reweight rates based on their totals
    # TODO: Remove this process with the new weighted rolling algorithm
    total_rate = sum((r.rate for r in rarity_objects.values()))
    for rarity in rarity_objects.keys():
      rarity_objects[rarity].rate /= total_rate

    return rarity_objects


@define(kw_only=True, slots=False)
class Pity(BaseGachaUser, BasePity, Rarity):
  """Gacha user's pity counter for a given rarity."""

  @classmethod
  async def fetch(cls, user: Union[BaseUser, Snowflake]) -> List["Pity"]:
    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    statement = (
      select(schema.Pity, schema.Settings, schema.Currency)
      .join(schema.Settings, schema.Settings.rarity == schema.Pity.rarity)
      .join(schema.Currency, schema.Currency.user == schema.Pity.user)
      .where(schema.Pity.user == user)
    )

    async with new_session() as session:
      results = (await session.execute(statement)).all()
    return [
      cls(**(result.Pity.asdict() | result.Settings.asdict() | result.Currency.asdict()))
      for result in results
    ]


  @staticmethod
  async def new(session: AsyncSession, user: Union[BaseUser, Snowflake]) -> None:
    """
    Create a new gacha user pity counter.

    Args:
      user: User object or user ID
      init_shards: Amount of initial shards to give to user
    """

    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    # 1. Obtain rarities
    statement = (
      select(schema.Settings.rarity)
    )
    async with new_session() as read_session:
      rarities = (await read_session.scalars(statement)).all()

    # 2. Write initial pity counter
    for rarity in rarities:
      statement = (
        insert(schema.Pity)
        .values(user=user, rarity=rarity, count=0)
      )
      await session.execute(statement)


  @staticmethod
  async def increment(session: AsyncSession, user: Union[BaseUser, Snowflake], rarity_get: int) -> None:
    """
    Increment the pity counter for a given user, 

    Args:
      user: User object or user ID
      init_shards: Amount of initial shards to give to user
    """

    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")
    
    # 1. Obtain rarities with non-null, non-zero pity setting
    statement = (
      select(schema.Settings.rarity)
      .where(schema.Settings.pity > 0)
    )
    async with new_session() as read_session:
      rarities = (await read_session.scalars(statement)).all()
  
    for rarity in rarities:
      statement = (
        insert(schema.Pity)
        .values(user=user, rarity=rarity, count=1)
        .on_conflict_do_update(
          index_elements=["user", "rarity"],
          set_={
            "count": 0 if rarity == rarity_get else schema.Pity.__table__.c.count + 1
          },
        )
      )
      await session.execute(statement)


@define(kw_only=True, slots=False)
class Roll(BaseRoll, BaseCard, BaseRarity):
  """Gacha rolls from a given user."""

  id: str

  @classmethod
  async def fetch(cls, *,
    user: Optional[Union[BaseUser, Snowflake]] = None,
    card: Optional[Union["Card", str]] = None,
    before: Optional[Union[Timestamp, datetime, int, float]] = None,
    after: Optional[Union[Timestamp, datetime, int, float]] = None,
    rarity: Optional[int] = None,
    rarity_min: Optional[int] = None,
    rarity_max: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    oldest: bool = False,
    unlisted: bool = False
  ):
    statement = (
      select(schema.Roll, schema.Card, schema.Settings)
      .join(schema.Card, schema.Card.id == schema.Roll.card)
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
    )

    if not unlisted:
      statement = statement.where(schema.Card.unlisted == False)

    if user:
      if isinstance(user, BaseUser):
        user = user.id
      elif not isinstance(user, int):
        # Snowflake is an instance of int
        raise TypeError("Cannot read user object of unsupported type")
      statement = statement.where(schema.Roll.user == user)

    if card:
      if isinstance(card, Card):
        card = card.id
      elif not isinstance(card, str):
        # UserCard, CardStats are instances of Card
        raise TypeError("Cannot read card object of unsupported type")
      statement = statement.where(schema.Roll.card == card)

    if before:
      if isinstance(before, datetime):
        # Timestamp is an instance of datetime
        before = before.timestamp()
      elif isinstance(before, int):
        before = float(before)
      elif not isinstance(before, float):
        raise TypeError("Cannot read time of unsupported type")
      statement = statement.where(schema.Roll.time <= before)

    if after:
      if isinstance(after, datetime):
        # Timestamp is an instance of datetime
        after = after.timestamp()
      elif isinstance(after, int):
        after = float(after)
      elif not isinstance(after, float):
        raise TypeError("Cannot read time of unsupported type")
      statement = statement.where(schema.Roll.time >= after)

    if rarity is not None:
      statement = statement.where(schema.Card.rarity == rarity)
    else:
      if rarity_min is not None:
        statement = statement.where(schema.Card.rarity >= rarity_min)
      if rarity_max is not None:
        statement = statement.where(schema.Card.rarity <= rarity_max)

    statement = statement.order_by(schema.Roll.time if oldest else schema.Roll.time.desc())
    if limit:
      statement = statement.limit(limit)
      if offset:
        statement = statement.offset(offset)

    async with new_session() as session:
      results = (await session.execute(statement)).all()

    return [
      cls(
        user=result.Roll.user, card=result.Roll.card, time=result.Roll.time,
        **(result.Card.asdict() | result.Settings.asdict())
      )
      for result in results
    ]


@define(kw_only=True, slots=False)
class Card(BaseCard, BaseRarity):
  """Mitsuki gacha card."""

  roll_pity_counter: Optional[int] = field(default=None)
  roll_pity_at: Optional[int] = field(default=None)
  roll_banner: Optional["Banner"] = field(default=None)


  def __eq__(self, value: object) -> bool:
    if not isinstance(value, Card):
      raise TypeError(f"'=' not supported between instances of Card and '{type(value)}'")
    return (
      self.id == value.id
      and self.name == value.name
      and self.rarity == value.rarity
      and self.type == value.type
      and self.series == value.series
      and self.group == value.group
      and self.image == value.image
      and self.tags == value.tags
      and self.limited == value.limited
      and self.locked == value.locked
      and self.unlisted == value.unlisted
    )


  @classmethod
  def create(
    cls,
    id: str,
    name: str,
    rarity: int,
    type: str,
    series: str,
    group: str,
    image: Optional[str] = None,
    tags: Optional[str] = None,
    limited: bool = False,
    locked: bool = False,
    unlisted: bool = False,
  ):
    return cls(
      id=id,
      name=name,
      rarity=rarity,
      type=type,
      series=series,
      group=group,
      image=image,
      tags=tags,
      limited=limited,
      locked=locked,
      unlisted=unlisted,
      # Stub values
      rate=0.0,
      color=0,
      stars="",
    )


  @classmethod
  def parse_all(
    cls,
    data: Dict[str, Dict[str, Any]],
    *,
    rarities: Optional[List[int]] = None,
    ignore_error: bool = False,
  ) -> List["Card"]:
    li = []
    for id, card_data in data.items():
      try:
        card = cls.create(
          id=id,
          name=card_data["name"],
          rarity=int(card_data["rarity"]),
          type=card_data["type"],
          series=card_data["series"],
          group=card_data.get("group", card_data["type"]),
          image=card_data.get("image"),
          limited=bool(card_data.get("limited")),
          locked=bool(card_data.get("locked")),
          unlisted=bool(card_data.get("unlisted")),
          tags=card_data.get("tags"),
        )
      except (KeyError, ValueError):
        if ignore_error:
          continue
        else:
          raise

      if rarities and card.rarity not in rarities:
        if ignore_error:
          continue
        else:
          raise ValueError(f"Unexpected rarity '{card.rarity}' while parsing '{card.id}'")
      
      li.append(card)

    return li


  @classmethod
  async def fetch(cls, id: str) -> Optional["Card"]:
    """
    Fetch a card by its ID.

    Args:
      id: Card ID
    """

    statement = (
      select(schema.Card, schema.Settings)
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
      .where(schema.Card.id == id)
    )
    async with new_session() as session:
      result = (await session.execute(statement)).first()

    if not result:
      return None
    return cls(**(result.Card.asdict() | result.Settings.asdict()))


  @classmethod
  async def fetch_all(cls, *,
    rarity: Optional[int] = None,
    banner: Optional[str] = None,
    rollable_only: bool = False,
    unlisted: bool = False,
    unobtained: bool = True,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
  ) -> List["Card"]:
    """
    Fetch card IDs of a given rarity and banner, if provided.

    "Rollable" excludes unlisted, locked, and off-banner limited cards.

    Args:
      rarity: Card rarity
      banner: ID of gacha banner
      rollable_only: Whether to only include rollable cards, implies `unlisted = False`
      unlisted: Whether to include unlisted cards
    """

    statement = (
      select(schema.Card, schema.Settings)
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
    )

    if not unobtained:
      subq_roll = select(schema.Roll.card.distinct().label("card")).subquery("subq_roll")
      statement = statement.join(subq_roll, subq_roll.c.card == schema.Card.id)

    if banner:
      statement = (
        statement
        .join(schema.BannerCard, schema.BannerCard.card == schema.Card.id)
        .join(schema.Banner, schema.Banner.id == schema.BannerCard.banner)
        .where(schema.Banner.id == banner)
      )
    elif rollable_only: # and not banner
      statement = statement.where(schema.Card.limited == False)

    if rollable_only:
      statement = (
        statement
        .where(schema.Card.locked == False)
        .where(schema.Card.unlisted == False)
      )
    elif not unlisted:
      statement = (
        statement
        .where(schema.Card.unlisted == False)
      )

    if rarity:
      statement = statement.where(schema.Card.rarity == rarity)

    if limit:
      statement = statement.limit(limit)
      if offset:
        statement = statement.offset(offset)

    async with new_session() as session:
      results = (await session.execute(statement)).all()
    return [cls(**(result.Card.asdict() | result.Settings.asdict())) for result in results]


  @staticmethod
  async def count(
    *,
    rarity: Optional[int] = None,
    banner: Optional[str] = None,
    rollable_only: bool = False,
    unlisted: bool = False,
    unobtained: bool = False,
  ):
    statement = (
      select(func.count(schema.Card.id.distinct()))
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
    )

    if not unobtained:
      subq_roll = select(schema.Roll.card.distinct().label("card")).subquery("subq_roll")
      statement = statement.join(subq_roll, subq_roll.c.card == schema.Card.id)

    if banner:
      statement = (
        statement
        .join(schema.BannerCard, schema.BannerCard.card == schema.Card.id)
        .join(schema.Banner, schema.Banner.id == schema.BannerCard.banner)
        .where(schema.Banner.id == banner)
      )
    elif rollable_only: # and not banner
      statement = statement.where(schema.Card.limited == False)

    if rollable_only:
      statement = (
        statement
        .where(schema.Card.locked == False)
        .where(schema.Card.unlisted == False)
      )
    elif not unlisted:
      statement = (
        statement
        .where(schema.Card.unlisted == False)
      )

    if rarity:
      statement = statement.where(schema.Card.rarity == rarity)

    async with new_session() as session:
      return await session.scalar(statement) or 0


  async def submit_roll(
    self,
    session: AsyncSession,
    user: Union[BaseUser, Snowflake],
    time: Union[Timestamp, datetime, int, float]
  ):
    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    if isinstance(time, datetime):
      # Timestamp is an instance of datetime
      time = time.timestamp()
    elif isinstance(time, int):
      time = float(time)
    elif not isinstance(time, float):
      raise TypeError("Cannot read time of unsupported type")

    statement = (
      insert(schema.Roll)
      .values(user=user, card=self.id, time=time)
    )
    await session.execute(statement)


  async def add(self, session: AsyncSession):
    statement = (
      insert(schema.Card)
      .values(
        id=self.id,
        name=self.name,
        rarity=self.rarity,
        type=self.type,
        series=self.series,
        group=self.group,
        image=self.image,
        tags=self.tags,
        limited=self.limited,
        locked=self.locked,
        unlisted=self.unlisted,
      )
      .on_conflict_do_update(
        index_elements=['id'],
        set_=dict(
          name=self.name,
          rarity=self.rarity,
          type=self.type,
          series=self.series,
          group=self.group,
          image=self.image,
          tags=self.tags,
          limited=self.limited,
          locked=self.locked,
          unlisted=self.unlisted,
        )
      )
    )
    await session.execute(statement)
  
  
  async def unlist(self, session: AsyncSession):
    statement = update(schema.Card).values(unlisted=True)
    await session.execute(statement)


@define(kw_only=True, slots=False)
class GachaUser(BaseGachaUser):
  """Gacha player, including their shards and daily records."""

  last_daily_f: str = field(init=False)
  last_daily_d: str = field(init=False)
  first_daily_f: str = field(init=False)
  first_daily_d: str = field(init=False)

  def __attrs_post_init__(self):
    self.last_daily_f = self.last_daily_dt.format("f") if self.last_daily else "-"
    self.last_daily_d = self.last_daily_dt.format("D") if self.last_daily else "-"
    self.first_daily_f = self.first_daily_dt.format("f") if self.first_daily else "-"
    self.first_daily_d = self.first_daily_dt.format("D") if self.first_daily else "-"


  @property
  def last_daily_dt(self):
    if not self.last_daily:
      return None
    return Timestamp.fromtimestamp(self.last_daily, tz=timezone.utc)


  @property
  def first_daily_dt(self):
    if not self.first_daily:
      return None
    return Timestamp.fromtimestamp(self.first_daily, tz=timezone.utc)


  @classmethod
  async def fetch(cls, user: Union[BaseUser, Snowflake]):
    """
    Fetch gacha data for a given user, including shards count, last daily time, and first daily time.

    Args:
      user: User object or user ID
    """

    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")
    
    statement = (
      select(schema.Currency)
      .where(schema.Currency.user == user)
    )

    async with new_session() as session:
      result = await session.scalar(statement)

    if not result:
      return None
    return cls(**result.asdict())


  @staticmethod
  async def exists(user: Union[BaseUser, Snowflake]):
    """
    Check if a gacha user exists by checking the Currency data.

    Args:
      user: User object or user ID
    """

    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")
    
    statement = select(schema.Currency.user).where(schema.Currency.user == user)
    async with new_session() as session:
      return await session.scalar(statement) is not None


  @classmethod
  async def new(cls, session: AsyncSession, user: Union[BaseUser, Snowflake], init_shards: Optional[int] = None):
    """
    Create a new gacha user.

    Args:
      user: User object or user ID
      init_shards: Amount of initial shards to give to user
    """

    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    # 1. Currency
    statement = (
      insert(schema.Currency)
      .values(user=user, amount=init_shards or 0)
    )
    await session.execute(statement)

    # 2. Pity counter
    await Pity.new(session, user)

    return cls(user=user, amount=init_shards or 0)


  @staticmethod
  def next_daily(
    from_time: Optional[Union[Timestamp, datetime, float]] = None,
    reset_time: Optional[datetime] = None
  ):
    from_time = from_time or datetime.now(tz=timezone.utc).timestamp()
    if isinstance(from_time, float):
      from_time = datetime.fromtimestamp(from_time, tz=timezone.utc)
    elif not isinstance(from_time, datetime):
      # Timestamp is an instance of datetime
      raise TypeError("Cannot read roll time of unsupported type")

    reset_time = reset_time or settings.mitsuki.daily_reset_dt
    next_daily = from_time.replace(
      hour=reset_time.hour, minute=reset_time.minute, second=0, microsecond=0
    )
    if from_time > next_daily:
      next_daily = next_daily + timedelta(days=1)
    return next_daily


  def is_daily(
    self,
    time: Optional[Union[Timestamp, datetime, float]] = None,
    reset_time: Optional[datetime] = None
  ):
    if self.last_daily is None:
      return True

    time = time or datetime.now(tz=timezone.utc).timestamp()
    if isinstance(time, float):
      time = datetime.fromtimestamp(time, tz=timezone.utc)
    elif not isinstance(time, datetime):
      # Timestamp is an instance of datetime
      raise TypeError("Cannot read roll time of unsupported type")

    return time >= self.next_daily(self.last_daily, reset_time)


  def is_first_daily(self):
    return self.first_daily is None


  async def exchange(self, session: AsyncSession, target_user: Union[BaseUser, Snowflake], shards: int):
    """
    Exchange a given amount of shards from this user to a target user.

    This should be executed from a gacha user obtained using fetch().

    Args:
      session: Database write session
      target_user: Target user object or user ID
      shards: Amount of shards to give to target user
    """

    if isinstance(target_user, BaseUser):
      target_user = target_user.id
    elif not isinstance(target_user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    if not await self.exists(self.user):
      self = await self.new(session, self.user)
    if not await self.exists(target_user):
      await self.new(session, target_user)

    statement = (
      update(schema.Currency)
      .where(schema.Currency.user == self.user)
      .values(amount=schema.Currency.__table__.c.amount - shards)
      .returning(schema.Currency.amount)
    )
    new_shards = await session.scalar(statement)

    statement = (
      update(schema.Currency)
      .where(schema.Currency.user == target_user)
      .values(amount=schema.Currency.__table__.c.amount + shards)
    )
    await session.execute(statement)

    self.amount = new_shards or self.amount - shards


  async def give(
    self,
    session: AsyncSession,
    shards: int,
    daily_time: Optional[Union[Timestamp, datetime, float]] = None
  ):
    """
    Give a given amount of shards to this user.

    For daily shards, provide the timestamp in daily_time.

    Args:
      session: Database write session
      shards: Amount of shards to give to this user
      daily_time: Daily claim time, if this is a daily
    """

    if isinstance(daily_time, datetime):
      # Timestamp is an instance of datetime
      daily_time = daily_time.timestamp()
    elif daily_time is not None and not isinstance(daily_time, float):
      raise TypeError("Cannot read roll time of unsupported type")

    if not await self.exists(self.user):
      self = await self.new(session, self.user)

    statement = (
      update(schema.Currency)
      .where(schema.Currency.user == self.user)
    )
    updates = {"amount": schema.Currency.__table__.c.amount + shards}
    if daily_time:
      updates |= {"last_daily": daily_time}
      if self.first_daily is None:
        updates |= {"first_daily": daily_time}

    statement = statement.values(updates).returning(schema.Currency.amount)
    new_shards = await session.scalar(statement)

    self.amount = new_shards or self.amount + shards
    if daily_time:
      self.last_daily = daily_time
      if self.first_daily is None:
        self.first_daily = daily_time


@define(kw_only=True)
class UserStats(BasePity, BaseRarity):
  """Gacha user's roll statistics for a given rarity, including first rolls and number of rolls."""

  count: Optional[int] = field(default=None)

  first_roll: Optional[float] = field(default=None)
  last_roll: Optional[float] = field(default=None)
  cards_unique: int = field(default=0)
  cards_rolled: int = field(default=0)

  @classmethod
  async def fetch(cls, user: Union[BaseUser, Snowflake]):
    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    if not await GachaUser.exists(user):
      return []

    subq_cards = (
      select(
        schema.Card.rarity,
        func.count(schema.Roll.card.distinct()).label("cards"),
        func.sum(schema.Roll.card).label("rolled"),
        func.min(schema.Roll.time).label("first_roll"),
        func.max(schema.Roll.time).label("last_roll")
      )
      .join(schema.Roll, schema.Roll.card == schema.Card.id)
      .where(schema.Roll.user == user)
      .where(schema.Card.unlisted == False)
      .group_by(schema.Card.rarity)
      .subquery("subq_cards")
    )
    subq_pity = (
      select(schema.Pity)
      .where(schema.Pity.user == user)
      .subquery("subq_pity")
    )
    query = (
      select(
        schema.Settings,
        subq_pity,
        func.coalesce(subq_cards.c.cards, 0).label("cards"),
        func.coalesce(subq_cards.c.rolled, 0).label("rolled"),
      )
      .join(subq_pity, subq_pity.c.rarity == schema.Settings.rarity, isouter=True)
      .join(subq_cards, subq_cards.c.rarity == schema.Settings.rarity, isouter=True)
    )

    async with new_session() as session:
      results = (await session.execute(query)).all()

    return [cls(
      user=user,
      first_roll=result.first_roll,
      last_roll=result.last_roll,
      cards_unique=result.cards,
      cards_rolled=result.rolled,
      count=result.count,
      **result.Settings.asdict()
    ) for result in results]


@define(kw_only=True, slots=False)
class UserCard(BaseCard, BaseRarity):
  """Mitsuki gacha card as rolled by a user."""

  user: Snowflake
  count: int = field(default=0)
  first_acquired: float
  last_acquired: float

  mention: str = field(init=False)
  first_acquired_f: str = field(init=False)
  first_acquired_d: str = field(init=False)
  last_acquired_f: str = field(init=False)
  last_acquired_d: str = field(init=False)

  @property
  def first_acquired_dt(self):
    return Timestamp.fromtimestamp(self.first_acquired, tz=timezone.utc)

  @property
  def last_acquired_dt(self):
    return Timestamp.fromtimestamp(self.last_acquired, tz=timezone.utc)

  def __attrs_post_init__(self):
    self.mention = f"<@{self.user}>"
    self.first_acquired_f = self.first_acquired_dt.format("f")
    self.first_acquired_d = self.first_acquired_dt.format("D")
    self.last_acquired_f  = self.last_acquired_dt.format("f")
    self.last_acquired_d  = self.last_acquired_dt.format("D")


  @classmethod
  async def fetch(cls, id: str, user: Union[BaseUser, Snowflake]) -> "UserCard":
    """
    Fetch a card in a user's inventory by its ID.

    Args:
      id: Card ID
      user: Target user object or user ID
    """
    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    subq_rolls = (
      select(
        schema.Roll.card,
        func.count(schema.Roll.card).label("count"),
        func.min(schema.Roll.time).label("first_acquired"),
        func.max(schema.Roll.time).label("last_acquired")
      )
      .where(schema.Roll.user == user)
      .group_by(schema.Roll.card)
      .subquery("subq_rolls")
    )

    statement = (
      select(subq_rolls, schema.Card, schema.Settings)
      .join(schema.Card, schema.Card.id == subq_rolls.c.card)
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
      .where(schema.Card.id == id)
    )
    async with new_session() as session:
      result = (await session.execute(statement)).first()

    if not result:
      return None
    return cls(
      user=user, count=result.count, first_acquired=result.first_acquired, last_acquired=result.last_acquired,
      **(result.Card.asdict() | result.Settings.asdict())
    )


  @classmethod
  async def fetch_all(
    cls,
    user: Union[BaseUser, Snowflake],
    *,
    sort: Optional[str] = None
  ) -> List["UserCard"]:
    """
    Fetch all cards in a user's inventory.

    Args:
      user: Target user object or user ID
    """
    if isinstance(user, BaseUser):
      user = user.id
    elif not isinstance(user, int):
      # Snowflake is an instance of int
      raise TypeError("Cannot read user object of unsupported type")

    subq_rolls = (
      select(
        schema.Roll.card,
        func.count(schema.Roll.card).label("count"),
        func.min(schema.Roll.time).label("first_acquired"),
        func.max(schema.Roll.time).label("last_acquired")
      )
      .where(schema.Roll.user == user)
      .group_by(schema.Roll.card)
      .subquery("subq_rolls")
    )
    statement = (
      select(subq_rolls, schema.Card, schema.Settings)
      .join(schema.Card, schema.Card.id == subq_rolls.c.card)
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
    )

    sort = sort or "date"
    match sort.lower():
      case "rarity":
        statement = statement.order_by(schema.Card.rarity.desc()).order_by(subq_rolls.c.first_acquired.desc())
      case "alpha":
        statement = statement.order_by(func.lower(schema.Card.name))
      case "date":
        statement = statement.order_by(subq_rolls.c.first_acquired.desc())
      case "series":
        statement = (
          statement
          .order_by(schema.Card.type)
          .order_by(schema.Card.series)
          .order_by(schema.Card.rarity)
          .order_by(schema.Card.id)
        )
      case "count":
        statement = statement.order_by(subq_rolls.c.count.desc()).order_by(subq_rolls.c.first_acquired.desc())
      case "id":
        statement = statement.order_by(schema.Card.id)
      case _:
        raise ValueError(f"Invalid sort setting '{sort}'")

    async with new_session() as session:
      results = (await session.execute(statement)).all()

    return [
      cls(
        user=user, count=result.count, first_acquired=result.first_acquired, last_acquired=result.last_acquired,
        **(result.Card.asdict() | result.Settings.asdict())
      )
      for result in results
    ]


@define(kw_only=True, slots=False)
class CardStats(BaseCard, BaseRarity):
  users: int = field(default=0)
  rolled: int = field(default=0)

  first_user_acquired: Optional[float] = field(default=None)
  last_user_acquired: Optional[float] = field(default=None)

  first_user: Optional[Snowflake] = field(default=None)
  last_user: Optional[Snowflake] = field(default=None)

  linked_name: str = field(init=False, default="-")

  first_user_mention: str = field(init=False, default="-")
  first_user_acquired_f: str = field(init=False, default="-")
  first_user_acquired_d: str = field(init=False, default="-")

  last_user_mention: str = field(init=False, default="-")
  last_user_acquired_f: str = field(init=False, default="-")
  last_user_acquired_d: str = field(init=False, default="-")

  @property
  def first_user_acquired_dt(self):
    if not self.first_user_acquired:
      return None
    return Timestamp.fromtimestamp(self.first_user_acquired, tz=timezone.utc)

  @property
  def last_user_acquired_dt(self):
    if not self.last_user_acquired:
      return None
    return Timestamp.fromtimestamp(self.last_user_acquired, tz=timezone.utc)


  def __attrs_post_init__(self):
    if self.first_user:
      self.first_user_mention = f"<@{self.first_user}>"

    if self.last_user:
      self.last_user_mention = f"<@{self.last_user}>"

    if self.first_user_acquired:
      self.first_user_acquired_f = self.first_user_acquired_dt.format("f")
      self.first_user_acquired_d = self.first_user_acquired_dt.format("D")

    if self.last_user_acquired:
      self.last_user_acquired_f = self.last_user_acquired_dt.format("f")
      self.last_user_acquired_d = self.last_user_acquired_dt.format("D")

    self.linked_name = f"[{escape_text(self.name)}]({self.image})" if self.image else self.name


  @classmethod
  async def search(
    cls,
    key: str,
    *,
    user: Optional[Union[BaseUser, Snowflake]] = None,
    limit: Optional[int] = None,
    unobtained: bool = False,
  ):
    # 1. Fetch names
    statement = (
      select(schema.Card.id.distinct(), schema.Card.name)
      .join(schema.Roll, schema.Roll.card == schema.Card.id, isouter=unobtained)
    )

    if user:
      if isinstance(user, BaseUser):
        user = user.id
      elif not isinstance(user, int):
        # Snowflake is an instance of int
        raise TypeError("Cannot read user object of unsupported type")
      statement = statement.where(schema.Roll.user == user)

    async with new_session() as session:
      matches = (await session.execute(statement)).all()

    # 2. Match search
    results = Search.process(matches, key, cutoff=60.0, limit=limit)
    card_ids = [result.id for result in results]
  
    # 3. Return cards
    subq_rolls = (
      select(
        schema.Roll.card,
        func.count(schema.Roll.user.distinct()).label("users"),
        func.count(schema.Roll.user).label("rolled"),
        func.min(schema.Roll.time).label("first_user_acquired"),
        func.max(schema.Roll.time).label("last_user_acquired"),
      )
      .group_by(schema.Roll.card)
      .subquery("subq_rolls")
    )
    subq_first = (
      select(subq_rolls, schema.Roll.user.label("first_user"))
      .where(subq_rolls.c.first_user_acquired == schema.Roll.time)
      .subquery("subq_first")
    )
    subq_last = (
      select(subq_rolls, schema.Roll.user.label("last_user"))
      .where(subq_rolls.c.last_user_acquired == schema.Roll.time)
      .subquery("subq_last")
    )
    statement = (
      select(
        schema.Card,
        schema.Settings,
        func.coalesce(subq_rolls.c.users, 0).label("users"),
        func.coalesce(subq_rolls.c.rolled, 0).label("rolled"),  
        subq_first.c.first_user_acquired.label("first_user_acquired"),
        subq_first.c.first_user.label("first_user"),
        subq_last.c.last_user_acquired.label("last_user_acquired"),
        subq_last.c.last_user.label("last_user"),
      )
      .join(schema.Settings, schema.Settings.rarity == schema.Card.rarity)
      .join(subq_rolls, subq_rolls.c.card == schema.Card.id, isouter=unobtained)
      .join(subq_first, schema.Card.id == subq_first.c.card, isouter=unobtained)
      .join(subq_last, schema.Card.id == subq_last.c.card, isouter=unobtained)
      .where(schema.Card.unlisted == False)
      .where(schema.Card.id.in_(card_ids))
      .order_by(
        case(
          {item: idx for idx, item in enumerate(card_ids)},
          value=schema.Card.id
        )
      )
    )

    async with new_session() as session:
      results = (await session.execute(statement)).all()

    return [
      cls(
        users=result.users,
        rolled=result.rolled,
        first_user_acquired=result.first_user_acquired,
        last_user_acquired=result.last_user_acquired,
        first_user=result.first_user,
        last_user=result.last_user,
        **(result.Card.asdict() | result.Settings.asdict())
      )
      for result in results
    ]


@define(kw_only=True, slots=False)
class Banner(BaseBanner):
  """Gacha banner."""

  @classmethod
  async def fetch_current(
    cls,
    *,
    time: Optional[Union[Timestamp, datetime, int, float]] = None,
    rarity: Optional[int] = None
  ):
    """
    Fetch currently active banners as of a given time.
    
    Args:
      time: Reference current time
      rarity: Target card rarity, or any rarity if none

    Returns:
      List of current banner information
    """

    # Convert time arg to timestamp
    time = time or datetime.now(tz=timezone.utc).timestamp()
    if isinstance(time, datetime):
      # Timestamp is an instance of datetime
      time = time.timestamp()
    elif isinstance(time, int):
      time = float(time)
    elif not isinstance(time, float):
      raise TypeError("Cannot read time of unsupported type")

    statement = (
      select(schema.Banner)
      .where(schema.Banner.active == True)
      .where(schema.Banner.start_time <= time)
      .where(schema.Banner.end_time > time)
    )
    if rarity:
      statement = (
        statement
        .where(
          or_(
            schema.Banner.min_rarity <= rarity,
            schema.Banner.min_rarity == None
          )
        )
        .where(
          or_(
            schema.Banner.max_rarity >= rarity,
            schema.Banner.max_rarity == None
          )
        )
      )

    async with new_session() as session:
      results = (await session.scalars(statement)).all()

    return [cls(**result.asdict()) for result in results]


  @classmethod
  async def fetch_all(cls):
    """
    Fetch all banners.
    
    Returns:
      List of banner information
    """

    statement = select(schema.Banner).order_by(schema.Banner.start_time.desc())

    async with new_session() as session:
      results = (await session.scalars(statement)).all()

    return [cls(**result.asdict()) for result in results]


  @staticmethod
  async def count(
    *,
    current_on: Optional[Union[Timestamp, datetime, int, float]] = None,
    rarity: Optional[int] = None,
  ):
    """
    Obtain the count of all banners.

    Args:
      current_on: Reference current time, or all banners if none
      rarity: Target card rarity, or any rarity if none
    
    Returns:
      Banner count
    """

    current_on = current_on or datetime.now(tz=timezone.utc).timestamp()
    if isinstance(current_on, datetime):
      # Timestamp is an instance of datetime
      current_on = current_on.timestamp()
    elif isinstance(current_on, int):
      current_on = float(current_on)
    elif not isinstance(current_on, float):
      raise TypeError("Cannot read time of unsupported type")

    statement = (
      select(func.count(schema.Banner.id))
    )
    if current_on:
      statement = (
        statement
        .where(schema.Banner.active == True)
        .where(schema.Banner.start_time <= current_on)
        .where(schema.Banner.end_time > current_on)
      )
    if rarity:
      statement = (
        statement
        .where(schema.Banner.min_rarity <= rarity)
        .where(schema.Banner.max_rarity >= rarity)
      )

    async with new_session() as session:
      return await session.scalar(statement) or 0


@define(kw_only=True)
class Arona:
  random: SystemRandom
  cost: int
  # daily_tz: str # Superseded by settings.mitsuki.daily_reset
  daily_shards: int
  first_time_shards: Optional[int] = field(default=0)

  currency_icon: str = field(converter=str)
  currency_name: str = field(converter=str)

  rarities: Dict[int, Rarity] = field(factory=dict)

  _cards: Dict[str, Card] = field(factory=dict)

  @property
  def currency(self):
    return f"{self.currency_icon} {self.currency_name}".strip()

  @property
  def rates(self):
    return {r.rarity: r.rate for r in self.rarities.values()}


  @classmethod
  def load(cls, filename: Optional[str] = None):
    filename = filename or settings.gacha.settings
    with open(filename, encoding='UTF-8') as f:
      data = safe_load(f)

    # If a required field is missing, throw error, hence use of [] instead of .get()

    # 1. Configuration
    configuration = cls(
      random=SystemRandom(),
      cost=data["cost"],
      daily_shards=data["daily_shards"],
      first_time_shards=data.get("first_time_shards"),
      currency_icon=data["currency_icon"],
      currency_name=data["currency_name"]
    )

    # 2. Rarities
    rarities = Rarity.parse(data["rarities"])
    # Enforce ascending rarity order
    rarities = {rarity: rarities[rarity] for rarity in sorted(rarities.keys())}

    asyncio.run(cls._update_settings(rarities))
    configuration.rarities = rarities

    return configuration


  def reload(self, filename: Optional[str] = None):
    self = self.load(filename)


  async def load_roster(self, filename: Optional[str] = None):
    filename = filename or settings.gacha.roster
    with open(filename, encoding='UTF-8') as f:
      data = safe_load(f)

    if not isinstance(data, dict):
      raise TypeError("Cannot read roster file")

    # Roster fetching
    # If a required field is missing, skip entry
    cards = {
      card.id: card for card in Card.parse_all(
        data, rarities=self.rarities.keys(), ignore_error=True
      )
    }

    # For logging purposes
    # error_count = len(data) - len(cards)

    self._cards = cards


  async def sync_roster(self):
    if len(self._cards) == 0:
      raise ValueError("No cards to sync, load roster file to continue")

    old_cards: Dict[str, Card] = {card.id: card for card in await Card.fetch_all(unlisted=True, unobtained=True)}
    new_cards: Dict[str, Card] = self._cards

    upsert_cards: List[Card] = []
    delete_cards: List[Card] = []

    for id, new_card in new_cards.items():
      # Existing card
      if old_card := old_cards.get(id):
        del old_cards[id]

        # No updates
        if old_card == new_card:
          continue
        # Has updates
        upsert_cards.append(new_card)

      # New card
      else:
        upsert_cards.append(new_card)

    # Delete cards (sets unlisted)
    delete_cards.extend(old_cards.values())
  
    # Process cards
    async with new_session() as session:
      try:
        for card in upsert_cards:
          await card.add(session)
        for card in delete_cards:
          await card.unlist(session)
      except Exception:
        await session.rollback()
        raise
      await session.commit()


  async def fetch_card(self, id: str, force: bool = False):
    # Fetch from cache, unless force == True
    if (card := self._cards.get(id)) and not force:
      return card

    # If not in cache, or force == True, fetch from db
    if card := await Card.fetch(id):
      self._cards[id] = card
    return card


  async def roll(
    self,
    time: Optional[Union[Timestamp, datetime, float]] = None,
    user: Optional[Union[BaseUser, Snowflake]] = None
  ):
    """
    Roll a gacha card.
    
    If time is specified, may roll from banners current to that time.
    If user is specified, uses the user's pity counter if available.

    Args:
      time: Roll time, used for banner calculation
      user: Roll user, used for pity calculation
    
    Returns:
      Rolled card object
    """

    # ---------------------------------------------------------------------------------------------
    # Argument handling

    # Convert time arg to timestamp
    time = time or datetime.now(tz=timezone.utc).timestamp()
    if isinstance(time, datetime):
      # Timestamp is an instance of datetime
      time = time.timestamp()
    elif not isinstance(time, float):
      raise TypeError("Cannot read roll time of unsupported type")

    # If user is specified, check for pity
    min_rarity = None
    if user:
      # Convert user arg if specified to user id
      if isinstance(user, BaseUser):
        user = user.id
      elif not isinstance(user, int):
        # Snowflake is an instance of int
        raise TypeError("Cannot read user object of unsupported type")

      # Obtain user pity
      pity_counters = await Pity.fetch(user)
      for pity_counter in pity_counters:
        if pity_counter.pity and pity_counter.count + 1 >= pity_counter.pity:
          min_rarity = max(pity_counter.rarity, min_rarity) if min_rarity else pity_counter.rarity

    # ---------------------------------------------------------------------------------------------
    # Rarity calculation

    arona_value = self.random.random()
    rarity_get = min(self.rates.items())

    for rarity, rate in self.rates.items():
      arona_value -= rate
      rarity_get   = rarity

      if min_rarity and rarity < min_rarity:
        continue
      if arona_value < 0.0:
        break

    # ---------------------------------------------------------------------------------------------
    # Banner calculation

    available_banners = await Banner.fetch_current(time=time, rarity=rarity_get)

    banner_rates = [available_banner.rate for available_banner in available_banners]
    if sum(banner_rates) >= 1.0:
      banner_rates /= sum(banner_rates)

    arona_value = self.random.random()
    banner = None

    for idx, banner_rate in enumerate(banner_rates):
      arona_value -= banner_rate
      if arona_value < 0.0:
        banner = available_banners[idx]
        break

    # ---------------------------------------------------------------------------------------------
    # Card rolling

    # Fetch card ids with correct rarity (and banner) properties
    choices = await Card.fetch_all(
      rarity=rarity_get, banner=banner.id if banner else None, rollable_only=True,
    )

    # If no choices (due to unassigned banners), fall back to non-banner roll
    if len(choices) == 0:
      banner  = None
      choices = await Card.fetch_all(rarity=rarity_get, banner=None, rollable_only=True)
  
    # If no choices (due to no cards to roll), raise
    if len(choices) == 0:
      raise RuntimeError("No cards available to roll")

    card = self.random.choice(choices)
    card.roll_pity_counter = min_rarity
    card.roll_pity_at = self.rarities[card.rarity].pity
    if banner:
      card.roll_banner = banner
    return card


  @classmethod
  async def _update_settings(cls, rarities: Dict[int, Rarity]):
    async with new_session() as session:
      try:
        for rarity in rarities.values():
          await cls._update_setting(session, rarity)
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()  


  @staticmethod
  async def _update_setting(session: AsyncSession, rarity: Rarity):
    statement = (
      insert(schema.Settings)
      .values(
        rarity=rarity.rarity,
        rate=rarity.rate,
        pity=rarity.pity,
        dupe_shards=rarity.dupe_shards,
        color=rarity.color,
        stars=rarity.stars
      )
      .on_conflict_do_update(
        index_elements=['rarity'],
        set_=dict(
          rate=rarity.rate,
          pity=rarity.pity,
          dupe_shards=rarity.dupe_shards,
          color=rarity.color,
          stars=rarity.stars
        )
      )
    )
    await session.execute(statement)


try:
  arona = Arona.load()
except Exception:
  arona = None
  raise