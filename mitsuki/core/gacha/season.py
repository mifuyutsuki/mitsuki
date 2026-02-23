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
from mitsuki.core.gacha import CardCollection
from mitsuki.core.settings import get_setting, Settings

import mitsuki.models.gacha as models


@attrs.define(kw_only=True)
class GachaSeason(AsDict):
  """A gacha season."""

  id: str
  """Season ID."""
  name: str
  """Name of this season."""
  collection: str
  """ID of the collection containing rate-up cards of this season."""
  pickup_rate: float
  """Rate of rolling this season's rate-up cards over the general pool, out of 1.0."""
  start_time: float
  """Time this season starts after the last one ends, in timestamp format."""
  end_time: float
  """Time this season ends and the next one begins, in timestamp format."""
  description: Optional[str] = attrs.field(default=None)
  """Description of this season."""
  image: Optional[str] = attrs.field(default=None)
  """Banner image of this season."""


  @classmethod
  async def fetch_current(cls, *, now: Optional[ipy.Timestamp] = None) -> Optional[Self]:
    """
    Fetch the current gacha season, if there are any.

    Args:
      now: Reference time to determine the current season, or current time if unset
    
    Returns:
      Gacha season instance, or `None` if none are current
    """
    now = now or ipy.Timestamp.now(tz=timezone.utc)
    now = now.timestamp()

    query = (
      select(models.GachaSeason)
      .where(models.GachaSeason.start_time <= now)
      .where(models.GachaSeason.end_time > now)
      .order_by(models.GachaSeason.start_time.asc())
      .limit(1)
    )
    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  @classmethod
  async def fetch(cls, id: str) -> Optional[Self]:
    """
    Fetch a gacha season by its ID.

    Args:
      id: Gacha season ID

    Returns:
      Instance of gacha season, or `None` if doesn't exist
    """
    query = select(models.GachaSeason).where(models.GachaSeason.id == id)

    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  @classmethod
  async def fetch_all(cls) -> list[Self]:
    """
    Fetch all gacha seasons from the latest (in terms of end time).

    Returns:
      List of gacha seasons, if any
    """
    query = select(models.GachaSeason).order_by(models.GachaSeason.end_time.desc())

    async with begin_session() as session:
      results = await session.scalars(query)
    return [cls(**r.asdict()) for r in results]


  async def card_count(self) -> int:
    """
    Fetch the number of cards that are part of this season.

    Returns:
      Number of cards
    """
    return await CardCollection.fetch_card_count(self.collection, private=False)


  async def add(self, session: AsyncSession, *, create_collection: bool = False) -> None:
    """
    Add this gacha season.

    Args:
      session: Current database session
      create_collection: Whether to create the associated card collection as well
    """
    if create_collection:
      collection = CardCollection(
        id=self.collection, name=self.name, description=f"Cards part of the season '{self.name}'.",
        rollable=False, discoverable=True, show_counts=True
      )
      await collection.add(session)
    stmt = insert(models.GachaSeason).values(**self.asdict())
    await session.execute(stmt)


  async def delete(self, session: AsyncSession, *, delete_collection: bool = False) -> None:
    """
    Delete this gacha season.

    Args:
      session: Current database session
      delete_collection: Whether to delete the associated card collection as well
    """
    stmt = delete(models.GachaSeason).where(models.GachaSeason.id == self.id)
    await session.execute(stmt)
    if delete_collection:
      stmt = delete(models.GachaCollection).where(models.GachaCollection.id == self.collection)
      await session.execute(stmt)