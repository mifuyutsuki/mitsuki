# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any, Union, Self, List
from datetime import timezone
from random import SystemRandom

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
class CardCollection(AsDict):
  """A gacha card collection."""

  id: str
  """ID of this collection."""
  name: str
  """Name of this collection."""
  description: Optional[str] = attrs.field(default=None)
  """Description of this collection."""

  rollable: bool = attrs.field(default=False)
  """Whether this collection is rollable, provided the roll cost."""
  discoverable: bool = attrs.field(default=False)
  """Whether this collection is publicly viewable, showing held cards of this collection."""
  show_counts: bool = attrs.field(default=False)
  """Whether to show total cards in this collection, per rarity and including unobtained, if discoverable is set."""

  user_rolled: Optional[int] = attrs.field(default=None, eq=False)
  """Total cards in this collection rolled by a user, only set if fetched using `fetch_user()`."""
  user_obtained: Optional[int] = attrs.field(default=None, eq=False)
  """Unique cards in this collection rolled by a user, only set if fetched using `fetch_user()`."""
  available_count: Optional[int] = attrs.field(default=None, eq=False)
  """Total cards available to roll, only set if fetched using `fetch_user()`."""


  def db_dict(self, exclude_id: bool = False):
    keys = {
      "name", "description", "rollable", "discoverable", "show_counts"
    }
    if not exclude_id:
      keys.add("id")
    return {k: v for k, v in self.asdict().items() if k in keys}


  @classmethod
  async def fetch(cls, id: str):
    """
    Fetch a card collection by its ID.
    
    Args:
      id: Card collection ID
    
    Returns:
      Card collection instance, or `None` if not found
    """
    query = select(models.GachaCollection).where(models.GachaCollection.id == id)

    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  @classmethod
  async def fetch_user(cls, id: str, user: Union[ipy.BaseUser, ipy.Snowflake], *, private: bool = False):
    """
    Fetch a specific card collection with appended roll data for a given user.

    Args:
      user: Snowflake or instance of the user
      private: Whether to show private collections (discoverable=False)

    Returns:
      List of card collection instances with attached roll count data
    """
    if not isinstance(user, int):
      user = user.id

    rolls_query = select(models.GachaRoll).where(models.GachaRoll.user == user).subquery()

    available_count_col = sa.func.count(sa.distinct(models.Card.id)).label("available_count")
    user_rolled_col = sa.func.count(rolls_query.c.card).label("user_rolled")
    user_obtained_col = sa.func.count(sa.distinct(rolls_query.c.card)).label("user_obtained")

    query = (
      select(
        models.GachaCollection,
        available_count_col,
        user_rolled_col,
        user_obtained_col,
      )
      .select_from(models.GachaCollection)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.collection == models.GachaCollection.id)
      .join(models.Card, models.Card.id == models.GachaCollectionCard.card)
      .outerjoin(rolls_query, rolls_query.c.card == models.Card.id)
    )
    query = query.where(models.GachaCollection.id == id)
    if not private:
      query = query.where(models.GachaCollection.discoverable == True)
    query = query.having(available_count_col > 0)
    query = query.group_by(models.GachaCollection.id)

    async with begin_session() as session:
      if result := (await session.execute(query)).first():
        return cls(
          **result.GachaCollection.asdict(),
          available_count=result.available_count,
          user_rolled=result.user_rolled,
          user_obtained=result.user_obtained,
        )


  @classmethod
  async def fetch_all(cls, *, category_id: Optional[str] = None, private: bool = False):
    """
    Fetch all available card collections.

    Args:
      category_id: Collection category to filter the list to, or all public collections if not set
      private: Whether to show private collections (discoverable=False)

    Returns:
      List of card collection instances
    """
    query = select(models.GachaCollection)
    if category_id:
      query = (
        query
        .join(
          models.GachaCollectionCategoryEntry,
          models.GachaCollectionCategoryEntry.collection == models.GachaCollection.id
        )
        .join(
          models.GachaCollectionCategory,
          models.GachaCollectionCategory.id == models.GachaCollectionCategoryEntry.category
        )
        .where(models.GachaCollectionCategory.id == category_id)
      )
    if not private:
      query = query.where(models.GachaCollection.discoverable == True)

    async with begin_session() as session:
      return [cls(**r.asdict()) for r in await session.scalars(query)]


  @classmethod
  async def fetch_all_user(
    cls, user: Union[ipy.BaseUser, ipy.Snowflake], *, category_id: Optional[str] = None, private: bool = False
  ):
    """
    Fetch all available card collections with appended roll data for a given user.

    Args:
      user: Snowflake or instance of the user
      category_id: Collection category to filter the list to, or all public collections if not set
      private: Whether to show private collections (discoverable=False)

    Returns:
      List of card collection instances with attached roll count data
    """
    if not isinstance(user, int):
      user = user.id

    rolls_query = select(models.GachaRoll).where(models.GachaRoll.user == user).subquery()

    available_count_col = sa.func.count(sa.distinct(models.Card.id)).label("available_count")
    user_rolled_col = sa.func.count(rolls_query.c.card).label("user_rolled")
    user_obtained_col = sa.func.count(sa.distinct(rolls_query.c.card)).label("user_obtained")

    query = (
      select(
        models.GachaCollection,
        available_count_col,
        user_rolled_col,
        user_obtained_col,
      )
      .select_from(models.GachaCollection)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.collection == models.GachaCollection.id)
      .join(models.Card, models.Card.id == models.GachaCollectionCard.card)
    )
    if category_id:
      query = (
        query
        .join(
          models.GachaCollectionCategoryEntry,
          models.GachaCollectionCategoryEntry.collection == models.GachaCollection.id
        )
        .join(
          models.GachaCollectionCategory,
          models.GachaCollectionCategory.id == models.GachaCollectionCategoryEntry.category
        )
      )
    query = query.outerjoin(rolls_query, rolls_query.c.card == models.Card.id)
    if category_id:
      query = query.where(models.GachaCollectionCategory.id == category_id)
    if not private:
      query = query.where(models.GachaCollection.discoverable == True)
    query = query.having(available_count_col > 0)
    query = query.group_by(models.GachaCollection.id)

    async with begin_session() as session:
      return [
        cls(
          **r.GachaCollection.asdict(),
          available_count=r.available_count,
          user_rolled=r.user_rolled,
          user_obtained=r.user_obtained,
        )
        for r in await session.execute(query)
      ]


  @classmethod
  async def fetch_card_ids(cls, id: str, *, private: bool = False):
    """
    Fetch card IDs that are part of the given collection.

    Card IDs fetched by this method include limited and locked cards, which are
    rollable using collection tickets.

    Args:
      id: Card collection ID
      private: Whether to show non-public cards (cards with unlisted=True)

    Returns:
      List of card IDs
    """
    query = (
      select(models.Card.id)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .where(models.GachaCollection.id == id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      return list(await session.scalars(query))


  @staticmethod
  async def fetch_card_count(id: str, *, private: bool = False) -> int:
    """
    Count the number of cards in the specified collection.

    Args:
      id: Card collection ID
      private: Whether to show non-public cards (cards with unlisted=True)

    Returns:
      Number of cards in this collection
    """
    query = (
      select(sa.func.count()).select_from(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .where(models.GachaCollection.id == id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      return await session.scalar(query) or 0


  async def card_count(self, *, private: bool = False) -> int:
    """
    Count the number of cards in this collection.

    Args:
      private: Whether to show non-public cards (cards with unlisted=True)

    Returns:
      Number of cards in this collection
    """
    query = (
      select(sa.func.count()).select_from(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .join(models.GachaCollectionCard, models.GachaCollectionCard.card == models.Card.id)
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCard.collection)
      .where(models.GachaCollection.id == self.id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      return await session.scalar(query) or 0


  async def add_to_category(self, session: AsyncSession, category_id: Union[List[str], str]):
    """
    Add this collection to a collection category.

    Args:
      session: Current database session
      category_id: Collection category ID
    """
    if isinstance(category_id, str):
      category_id = [category_id]

    category_query = (
      select(sa.literal(self.id), models.GachaCollectionCategory.id).select_from(models.GachaCollectionCategory)
      .where(models.GachaCollectionCategory.id.in_(category_id))
    )
    stmt = (
      insert(models.GachaCollectionCategoryEntry)
      .from_select(["collection", "category"], category_query)
      .on_conflict_do_nothing()
    )
    await session.execute(stmt)


  async def add_cards_by_grep_id(self, session: AsyncSession, pattern: Union[List[str], str]):
    """
    Add cards to this collection by regex of card IDs.

    Args:
      session: Current database session
      pattern: Regex pattern for card ID
    """
    if isinstance(pattern, str):
      pattern = [pattern]

    cards_query = (
      select(sa.literal(self.id), models.Card.id).select_from(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .where(sa.or_(*[models.Card.id.regexp_match(p) for p in pattern]))
    )
    stmt = (
      insert(models.GachaCollectionCard)
      .from_select(["collection", "card"], cards_query)
      .on_conflict_do_nothing()
    )
    await session.execute(stmt)


  async def add_cards(self, session: AsyncSession, card_ids: list[str]):
    cards_query = (
      select(sa.literal(self.id), models.Card.id).select_from(models.Card)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .where(models.Card.id.in_(card_ids))
    )
    stmt = (
      insert(models.GachaCollectionCard)
      .from_select(["collection", "card"], cards_query)
      .on_conflict_do_nothing()
    )
    await session.execute(stmt)


  async def add(self, session: AsyncSession):
    """
    Add this collection.

    If a collection with this ID already exists, updates the collection.

    Args:
      session: Current database session
    """
    stmt = (
      insert(models.GachaCollection)
      .values(**self.db_dict())
      .on_conflict_do_update(index_elements=["id"], set_=self.db_dict(exclude_id=True))
    )
    await session.execute(stmt)


  async def clear(self, session: AsyncSession):
    """
    Clear cards in this gacha season.

    Note that this removes the card list of the collection associated with
    this season.

    Args:
      session: Current database session
    """
    stmt = delete(models.GachaCollectionCard).where(models.GachaCollectionCard.collection == self.id)
    await session.execute(stmt)


  async def delete(self, session: AsyncSession):
    """
    Delete this collection.
    
    Args:
      session: Current database session
    """
    stmt = delete(models.GachaCollection).where(models.GachaCollection.id == self.id)
    await session.execute(stmt)

    # In case the collection card table hasn't cascaded
    stmt = delete(models.GachaCollectionCard).where(models.GachaCollectionCard.collection == self.id)
    await session.execute(stmt)