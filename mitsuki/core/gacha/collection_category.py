# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any, Union, Self, List, Dict

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
class CardCollectionCategory(AsDict):
  """A category of gacha card collections."""

  id: str
  """ID of this collection category."""
  name: str
  """Name of this collection category."""
  description: Optional[str] = attrs.field(default=None)
  """Description of this collection category."""
  count: Optional[int] = attrs.field(default=None)
  """Number of collections in category, only set if fetched."""


  def db_dict(self, exclude_id: bool = False) -> Dict[str, Any]:
    keys = {
      "name", "description"
    }
    if not exclude_id:
      keys.add("id")
    return {k: v for k, v in self.asdict().items() if k in keys}
  

  @classmethod
  async def fetch(cls, id: str, *, private: bool = False) -> Optional[Self]:
    """
    Fetch a card collection category by its ID.

    Args:
      id: Card collection ID
      private: Whether to include private collections in count (discoverable=False)
    
    Returns:
      Card collection category instance with attached collection count, or `None` if not found
    """
    collection_query = (
      select(models.GachaCollection.id, sa.func.count(models.GachaCollectionCard.card).label("card_count"))
      .join(models.GachaCollectionCard, models.GachaCollectionCard.collection == models.GachaCollection.id)
      .group_by(models.GachaCollection.id)
      .subquery()
    )
    count_query = (
      select(
        models.GachaCollectionCategory.id,
        sa.func.count(models.GachaCollectionCategoryEntry.collection).label("count")
      )
      .select_from(models.GachaCollectionCategory)
      .join(
        models.GachaCollectionCategoryEntry,
        models.GachaCollectionCategoryEntry.category == models.GachaCollectionCategory.id
      )
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCategoryEntry.collection)
      .join(collection_query, collection_query.c.id == models.GachaCollection.id)
    )
    if not private:
      count_query = count_query.where(models.GachaCollection.discoverable == True).where(collection_query.c.card_count > 0)
    count_query = (
      count_query
      .group_by(models.GachaCollectionCategory.id)
      .subquery()
    )

    query = (
      select(models.GachaCollectionCategory, count_query.c.count)
      .join(count_query, count_query.c.id == models.GachaCollectionCategory.id)
      .where(models.GachaCollectionCategory.id == id)
    )
    if not private:
      query = query.where(count_query.c.count > 0)

    async with begin_session() as session:
      if result := (await session.execute(query)).first():
        return cls(
          **result.GachaCollectionCategory.asdict(),
          count=result.count
        )


  @classmethod
  async def fetch_all(cls, *, private: bool = False) -> List[Self]:
    """
    Fetch all available card collection categories.

    Args:
      private: Whether to include private collections in count (discoverable=False)

    Returns:
      List of card collection category instances with attached collection count
    """
    collection_query = (
      select(models.GachaCollection.id, sa.func.count(models.GachaCollectionCard.card).label("card_count"))
      .join(models.GachaCollectionCard, models.GachaCollectionCard.collection == models.GachaCollection.id)
      .group_by(models.GachaCollection.id)
      .subquery()
    )
    count_query = (
      select(
        models.GachaCollectionCategory.id,
        sa.func.count(models.GachaCollectionCategoryEntry.collection).label("count")
      )
      .select_from(models.GachaCollectionCategory)
      .join(
        models.GachaCollectionCategoryEntry,
        models.GachaCollectionCategoryEntry.category == models.GachaCollectionCategory.id
      )
      .join(models.GachaCollection, models.GachaCollection.id == models.GachaCollectionCategoryEntry.collection)
      .join(collection_query, collection_query.c.id == models.GachaCollection.id)
    )
    if not private:
      count_query = count_query.where(models.GachaCollection.discoverable == True).where(collection_query.c.card_count > 0)
    count_query = (
      count_query
      .group_by(models.GachaCollectionCategory.id)
      .subquery()
    )

    query = (
      select(models.GachaCollectionCategory, count_query.c.count)
      .join(count_query, count_query.c.id == models.GachaCollectionCategory.id)
    )
    if not private:
      query = query.where(count_query.c.count > 0)

    async with begin_session() as session:
      return [
        cls(
          **r.GachaCollectionCategory.asdict(),
          count=r.count
        )
        for r in await session.execute(query)
      ]


  async def add_collections(self, session: AsyncSession, collection_ids: list[str]):
    """
    Add collections to this collection category.

    Args:
      session: Current database session
      collection_ids: List of collection IDs to add to category
    """
    collections_query = (
      select(sa.literal(self.id), models.GachaCollection.id).select_from(models.GachaCollection)
      .where(models.GachaCollection.id.in_(collection_ids))
    )
    stmt = (
      insert(models.GachaCollectionCategoryEntry)
      .from_select(["category", "colletion"], collections_query)
      .on_conflict_do_nothing()
    )
    await session.execute(stmt)


  async def add(self, session: AsyncSession):
    """
    Add this collection category.

    If a collection with this ID already exists, updates the collection.

    Args:
      session: Current database session
    """
    stmt = (
      insert(models.GachaCollectionCategory)
      .values(**self.db_dict())
      .on_conflict_do_update(index_elements=["id"], set_=self.db_dict(exclude_id=True))
    )
    await session.execute(stmt)


  async def clear(self, session: AsyncSession):
    """
    Clear this collection category, setting its collection count to zero.

    Args:
      session: Current database session
    """
    stmt = delete(models.GachaCollectionCategoryEntry).where(models.GachaCollectionCategoryEntry.category == self.id)
    await session.execute(stmt)
  
    if self.count is not None:
      self.count = 0


  async def delete(self, session: AsyncSession):
    """
    Delete this collection category.

    Args:
      session: Current database session
    """
    stmt = delete(models.GachaCollectionCategory).where(models.GachaCollectionCategory.id == self.id)
    await session.execute(stmt)

    # In case the collection category entry table hasn't cascaded
    stmt = delete(models.GachaCollectionCategoryEntry).where(models.GachaCollectionCategoryEntry.category == self.id)
    await session.execute(stmt)