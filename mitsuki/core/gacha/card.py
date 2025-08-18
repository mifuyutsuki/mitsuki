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
from random import SystemRandom

import attrs
import interactions as ipy
import sqlalchemy as sa
from sqlalchemy import select, update, delete, literal
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki.utils import option, ratio, process_text
from mitsuki.lib.userdata import begin_session, AsDict, sa_insert as insert
from mitsuki.lib.commands import CustomID
from mitsuki.core.settings import get_setting, Settings

import mitsuki.models.gacha as models
from mitsuki.core.gacha import GachaSeason, CardCollection, CardRarity


_cache: Optional["CardCache"] = None


@attrs.define(kw_only=True)
class Card(AsDict):
  """A gacha card."""

  id: str
  """ID of this card."""
  name: str
  """Name of this card."""
  rarity: int
  """Rarity of this card expressed as the amount of stars."""
  type: str
  """Type of this card, e.g. 'Event'."""
  series: str
  """Series of this card, e.g. 'Mitsuki (Summer)'"""
  image: Optional[str] = attrs.field(default=None)
  """URL to card image."""

  limited: bool = attrs.field(default=False)
  """Whether the card is only rollable as a season pick-up or using collection tickets."""
  locked: bool = attrs.field(default=False)
  """Whether the card is not rollable, but obtainable using collection tickets."""
  unlisted: bool = attrs.field(default=False)
  """Whether the card is neither rollable nor viewable, i.e. 'deleted'."""

  convert_to: dict[str, int] = attrs.field(factory=dict)
  """Items that duplicates of this card convert to, if set, in the format {id: amount, ...}."""

  roll_time: Optional[ipy.Timestamp] = attrs.field(default=None)
  """Time when this card was rolled, only set if obtained from a card roll."""
  season_pickup: bool = attrs.field(default=False)
  """Whether this card is a season pickup, only set if obtained from a card roll."""
  collection_pickup: bool = attrs.field(default=False)
  """Whether this card is obtained from a collection ticket, only set if obtained from a card roll."""


  def db_dict(self, exclude_id: bool = False):
    keys = {
      "name", "rarity", "type", "series", "image",
      "locked", "limited", "unlisted", "convert_to"
    }
    if not exclude_id:
      keys.add("id")
    return {k: v for k, v in self.asdict().items() if k in keys}


  @classmethod
  async def fetch(cls, id: str, *, unobtained: bool = False, private: bool = False) -> Optional[Self]:
    """
    Fetch a card by its ID.

    Args:
      id: Card ID
      unobtained: Whether to return unobtained cards (cards without a roll entry)
      private: Whether to return non-public cards (cards with unlisted=True)

    Returns:
      Card instance, or `None` if a card with given ID doesn't exist
    """
    query = select(models.Card)
    if not unobtained:
      roll_query = select(models.GachaRoll.card.distinct().label("card")).subquery()
      query = query.join(roll_query, roll_query.c.card == models.Card.id)
    if not private:
      query = query.where(models.Card.unlisted == False)
    query = query.where(models.Card.id == id)

    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  @classmethod
  async def fetch_multiple(cls, ids: list[str], *, unobtained: bool = False, private: bool = False) -> list[Self]:
    """
    Fetch cards by the given list of IDs.

    The returned list follows the order they are listed in ids.

    Args:
      ids: List of card IDs
      unobtained: Whether to return unobtained cards (cards without a roll entry)
      private: Whether to return non-public cards (cards with unlisted=True)
    """
    if len(ids) == 0:
      return []

    query = select(models.Card)
    if not unobtained:
      roll_query = select(models.GachaRoll.card.distinct().label("card")).subquery()
      query = query.join(roll_query, roll_query.c.card == models.Card.id)
    if not private:
      query = query.where(models.Card.unlisted == False)
    query = query.where(models.Card.id.in_(ids))

    async with begin_session() as session:
      results = session.scalars(query)

    # Sort the result list to match the order of `ids`
    return sorted([cls(**r.asdict()) for r in results], key=lambda r: ids.index(r.id))


  @classmethod
  async def fetch_all(cls, *, unobtained: bool = False, private: bool = False) -> list[Self]:
    """
    Fetch all cards.

    Args:
      private: Whether to return non-public cards (cards with no roll entry or with unlisted=True)

    Returns:
      List of card instances
    """
    query = select(models.Card)
    if not unobtained:
      roll_query = select(models.GachaRoll.card.distinct().label("card")).subquery()
      query = query.join(roll_query, roll_query.c.card == models.Card.id)
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      results = await session.scalars(query)
    return [cls(**r.asdict()) for r in results]


  @classmethod
  async def fetch_all_standard(cls, *, private: bool = False) -> list[Self]:
    """
    Fetch all cards in the standard roster.

    Standard roster includes all cards in the general rollable pool, which
    excludes limited and locked cards.

    Args:
      private: Whether to show non-public cards (cards with unlisted=True)

    Returns:
      List of card instances
    """
    query = (
      select(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .where(models.Card.limited == False)
      .where(models.Card.locked == False)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      results = await session.scalars(query)
    return [cls(**r.asdict()) for r in results]


  @classmethod
  async def fetch_all_season(cls, *, now: Optional[ipy.Timestamp] = None, private: bool = False) -> list[Self]:
    """
    Fetch all cards in the current season.

    Args:
      now: Reference time to determine the current season, or current time if unset
      private: Whether to show non-public cards (cards with unlisted=True)

    Returns:
      List of card instances
    """
    now = now or ipy.Timestamp.now()
    now = now.timestamp()

    season_query = (
      select(models.GachaSeason)
      .where(models.GachaSeason.end_time > now)
      .order_by(models.GachaSeason.end_time.asc())
      .limit(1)
      .subquery()
    )

    query = (
      select(models.Card)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .join(season_query, season_query.c.collection == models.GachaCollection.id)
      .where(models.Card.locked == False)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      results = await session.scalars(query)
    return [cls(**r.asdict()) for r in results]


  @classmethod
  async def fetch_all_collection(cls, collection_id: str, *, private: bool = False):
    """
    Fetch all cards in a given collection.

    Card IDs fetched by this method include limited and locked cards, which are
    rollable using collection tickets.

    Args:
      id: Card collection ID
      private: Whether to show non-public cards (cards with unlisted=True)
    
    Returns:
      List of card IDs
    """
    query = (
      select(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .where(models.GachaCollection.id == collection_id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      results = await session.scalars(query)
    return [cls(**r.asdict()) for r in results]


  @staticmethod
  async def fetch_all_collection_roll(collection_id: str, *, private: bool = False):
    """
    Fetch all cards in a given collection, in the {rarity: [cards]} format
    used for rolling a card.

    Card IDs fetched by this method include limited and locked cards, which are
    rollable using collection tickets.

    Args:
      id: Card collection ID
      private: Whether to show non-public cards (cards with unlisted=True)
    
    Returns:
      List of card IDs categorized by rarity
    """
    query = (
      select(models.Card.rarity, models.Card.id)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .where(models.GachaCollection.id == collection_id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      results = (await session.execute(query)).all()

    choices: dict[int, list[str]] = {}
    for result in results:
      if result.rarity not in choices:
        choices[result.rarity] = []
      choices[result.rarity].append(result.id)
    return choices


  @classmethod
  async def roll(cls, *, min_rarity: Optional[int] = None):
    """
    Roll a card from the main roster.

    If there is an ongoing season, has a chance of obtaining a season pickup
    card, with a rate depending on each season.

    Args:
      min_rarity: Lowest card rarity to obtain

    Returns:
      Card instance with additional roll-related data set
    """
    return await CardCache.roll(min_rarity=min_rarity)


  async def add(self, session: AsyncSession, collection_id: Optional[str] = None) -> None:
    """
    Add this card to the database.

    If a card with this ID already exists, updates the card.

    Args:
      session: Current database session
      collection_id: Collection to add this card to, if specified
    """
    stmt = (
      insert(models.Card)
      .values(**self.db_dict())
      .on_conflict_do_update(index_elements=["id"], set_=self.db_dict(exclude_id=True))
    )
    await session.execute(stmt)

    if collection_id:
      await self.add_to_collection(session, collection_id)


  async def add_to_collection(self, session: AsyncSession, collection_id: str) -> None:
    """
    Add this card to a collection.

    Args:
      session: Current database session
      collection_id: Collection to add this card to
    """
    stmt = insert(models.GachaCollectionCard).values(collection=collection_id, card=self.id)
    await session.execute(stmt)


  async def delist(self, session: AsyncSession) -> None:
    """
    Delist this card.

    Unlisting a card removes it from public display, including in user card
    statistics and in collection views.

    Args:
      session: Current database session
    """
    self.unlisted = True
    stmt = update(models.Card).where(models.Card.id == self.id).values(unlisted=True).returning(models.Card.id)
    return await session.scalar(stmt) is not None


  async def update(self, session: AsyncSession) -> bool:
    """
    Update this card in the database.

    Args:
      session: Current database session
    
    Returns:
      True if the operation succeeded, or False otherwise
    """
    stmt = (
      update(models.Card)
      .where(models.Card.id == self.id)
      .values(**self.asdict(db_only=True, exclude_id=True))
      .returning(models.Card.id)
    )
    return await session.scalar(stmt) is not None


  async def give_to(
    self, session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake], amount: int = 1, *, rolled: bool = False
  ):
    """
    Grant a number of this card to the target user.

    Args:
      user: Instance or snowflake of the target gacha user
      amount: Number of this card to give
      rolled: Whether this card is rolled, and to update user data accordingly
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id
    if amount < 1:
      raise ValueError(f"Invalid card give amount of less than 1 ('{amount}')")
    if rolled and self.roll_time is None:
      raise ValueError("Instance is missing card roll time, which is required for granting rolled cards")

    inventory_stmt = (
      insert(models.UserCard)
      .values(user=user, card=self.id, count=amount)
      .on_conflict_do_update(
        index_elements=["user", "card"],
        set_={"count": models.UserCard.__table__.c.count + amount}
      )
    )
    pity_increment_stmt = (
      update(models.UserPity).where(models.UserPity.user == user).values(count=models.UserPity.__table__.c.count + 1)
    )
    pity_reset_stmt = (
      update(models.UserPity)
      .where(models.UserPity.user == user)
      .where(models.UserPity.rarity == self.rarity)
      .values(count=0)
    )
    roll_entry_stmt = (
      insert(models.GachaRoll).values(user=user, card=self.id, time=self.roll_time)
    )

    await session.execute(inventory_stmt)
    if rolled:
      await session.execute(pity_increment_stmt)
      await session.execute(pity_reset_stmt)
      await session.execute(roll_entry_stmt)


@attrs.define(kw_only=True)
class CardCache:
  """Gacha card cache, primarily used for rolls."""

  random: SystemRandom = attrs.field(factory=SystemRandom)
  """Randomizer instance for rolls."""

  card_names: dict[str, str] = attrs.field(factory=dict)
  """Gacha card names in the roster, used for card search."""
  rarities: dict[int, "CardRarity"] = attrs.field(factory=dict)
  """Gacha card rarity settings."""
  season: Optional["GachaSeason"] = attrs.field(default=None)
  """Current season, if any."""

  rarity_rates: dict[int, float] = attrs.field(factory=dict)
  """Gacha card rates per rarity, relative to the sum of all other rarity rates."""

  roster_cards: dict[int, list[str]] = attrs.field(factory=dict)
  """IDs of cards that are part of the rollable roster, categorized per rarity."""
  season_cards: dict[int, list[str]] = attrs.field(factory=dict)
  """IDs of cards that are part of the current season, categorized per rarity."""


  @property
  def season_ends(self):
    """Time this season ends, or `None` if no season is running"""
    if self.season:
      return ipy.Timestamp.fromtimestamp(self.season.end_time)


  @property
  def season_rate(self):
    """Rate of rolling this season's cards over the general pool, out of 1, or `None` if no season is running"""
    if self.season:
      return self.season.pickup_rate


  @property
  def season_available(self):
    """Whether this season is available, i.e. there are cards to roll."""
    return self.season and any([len(cards) > 0 for cards in self.season_cards.values()])


  @classmethod
  async def init(cls, *, now: Optional[ipy.Timestamp] = None) -> Self:
    """
    Initialize the card cache.

    Args:
      now: Reference time to determine the current season, or current time if unset

    Returns:
      Card cache instance
    """
    result = cls()
    await result.sync(now=now)
    return result


  async def sync(self, *, now: Optional[ipy.Timestamp] = None) -> None:
    """
    Synchronize the card cache with the database.

    Args:
      now: Reference time to determine the current season, or current time if unset

    Returns:
      Card cache instance
    """
    now = now or ipy.Timestamp.now()

    # Store fetch results in temp vars to avoid incomplete syncing
    temp_rarities = await CardRarity.fetch_all()
    temp_season   = await GachaSeason.fetch_current(now=now)

    # Note: To account for rosters/collections with cardless rarities,
    # these rarity rates are not the final one used in calculation.
    temp_rarity_rates = {r.rarity: r.rate for r in temp_rarities}
    temp_cards = {}

    temp_roster_cards = {r.rarity: [] for r in temp_rarities}
    for card in await Card.fetch_all_standard():
      temp_cards[card.id] = card.name
      temp_roster_cards[card.rarity].append(card.id)

    temp_season_cards = {r.rarity: [] for r in temp_rarities}
    for card in await Card.fetch_all_season(now=now):
      if card.id not in temp_cards:
        temp_cards[card.id] = card.name
      temp_season_cards[card.rarity].append(card.id)

    self.rarities     = temp_rarities
    self.season       = temp_season
    self.rarity_rates = temp_rarity_rates
    self.roster_cards = temp_roster_cards
    self.season_cards = temp_season_cards


  @classmethod
  async def search(cls, key: str, *, private: bool = False, limit: Optional[int] = None):
    """
    Search a card by name.

    Args:
      private: Whether to show non-public cards (cards with unlisted=True)
    
    Returns:
      List of card instances
    """
    global _cache
    if not _cache:
      _cache = await cls.init()
    cache = _cache

    if private:
      card_names = {c.id: c.name for c in await Card.fetch_all(unobtained=True, private=True)}
    else:
      card_names = cache.card_names

    scores = [(id, ratio(key, name, processor=process_text)) for id, name in card_names.items()]
    scores.sort(key=lambda score: score[1], reverse=True)

    # Primary score cutoff
    scores = [(id, score) for id, score in scores if score > 45.0]
    if limit:
      scores = scores[:limit]

    ids = [id for id, _ in scores]
    return await Card.fetch_multiple(ids, unobtained=private, private=private)


  @classmethod
  async def roll(cls, *, min_rarity: Optional[int] = None, now: Optional[ipy.Timestamp] = None):
    """
    Roll a card from the main roster.

    If there is an ongoing season, has a chance of obtaining a season pickup
    card, with a rate depending on each season.

    Args:
      min_rarity: Lowest card rarity to obtain
      now: Reference time to determine roll time and current season, or current time if unset

    Returns:
      Card instance with additional roll-related data set
    """
    global _cache
    now = now or ipy.Timestamp.now()

    if not _cache:
      _cache = await cls.init()
    cache = _cache

    # Is season still current?
    if cache.season_ends and now >= cache.season_ends:
      await cache.sync(now=now)

    # Season pick-up?
    cards = cache.roster_cards
    season_pickup = False

    if (
      cache.season_rate is not None
      and cache.season_available
      and cache.random.random() < cache.season_rate
    ):
      season_pickup = True
      cards = cache.season_cards

    # Roll
    if result := await cls._roll(cards, min_rarity=min_rarity):
      result.roll_time = now
      result.season_pickup = season_pickup
      return result
    else:
      raise RuntimeError("Failed to roll a card - missing setup or roster")


  @classmethod
  async def roll_collection(
    cls, collection_id: str, *, min_rarity: Optional[int] = None, now: Optional[ipy.Timestamp] = None
  ):
    """
    Roll a card from a collection.

    Args:
      collection_id: Card collection ID
      min_rarity: Lowest card rarity to obtain
      now: Reference time to determine roll time, or current time if unset

    Returns:
      Card instance with additional roll-related data set
    """
    global _cache
    now = now or ipy.Timestamp.now()

    if not _cache:
      _cache = await cls.init()

    cards = await Card.fetch_all_collection_roll(collection_id, private=False)
    if len(cards) == 0:
      raise RuntimeError("Failed to roll a card - collection has no cards")

    if result := await cls._roll(cards, min_rarity=min_rarity):
      result.roll_time = now
      result.collection_pickup = True
      return result
    else:
      raise RuntimeError("Failed to roll a card - missing setup or roster")


  @classmethod
  async def _roll(cls, choices: dict[int, list[str]], *, min_rarity: Optional[int] = None) -> Optional["Card"]:
    global _cache
    if not _cache:
      _cache = await cls.init()
    cache = _cache

    # Rates are normalized; only rates with corresponding card choices are
    # considered. As an example:
    # 
    # With cards of each rarity present:
    # -> {1: 0.785, 2: 0.185, 3: 0.03}
    # -- Sum of rates is 1.0, so the rates are unchanged when normalized.
    # -> {1: 0.785, 2: 0.185, 3: 0.03}
    # 
    # Without cards of rarity 1:
    # -> {2: 0.185, 3: 0.03}
    # -- Sum of rates is 0.215, so rates change upon normalization:
    # -> {2: 0.86, 3: 0.14}

    usable_rates = {
      rarity: rate
      for rarity, rate in cache.rarity_rates.items()
      if len(choices.get(rarity, [])) > 0
    }
    if len(usable_rates) == 0:
      return None

    total_usable_rates = sum(usable_rates.values())
    if total_usable_rates != 1.0:
      usable_rates = {
        rarity: rate / total_usable_rates
        for rarity, rate in usable_rates.items()
      }

    # Rate finding
    arona = cache.random.random()
    card_rarity = None

    for rarity, rate in usable_rates.items():
      if min_rarity and rarity < min_rarity:
        continue
      if arona < rate:
        card_rarity = rarity
        break
      arona -= rate

    if card_rarity is None:
      return None

    # Select obtained card
    card_get = None
    while card_get is None:
      if card_rarity < 1:
        return None
      try:
        card_get = cache.random.choice(choices[card_rarity])
      except (KeyError, IndexError):
        card_rarity -= 1
        continue

    return await Card.fetch(card_get, unobtained=True, private=False)