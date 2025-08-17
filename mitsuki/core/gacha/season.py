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
  end_time: float
  """Time this season ends and the next one begins, in timestamp format."""
  description: Optional[str] = attrs.field(default=None)
  """Description of this season."""


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
      .where(models.GachaSeason.end_time > now)
      .order_by(models.GachaSeason.end_time.asc())
      .limit(1)
    )
    async with begin_session() as session:
      if result := await session.scalar(query):
        return cls(**result.asdict())


  async def add(self, session: AsyncSession) -> None:
    """
    Add this gacha season.

    Args:
      session: Current database session
    """
    stmt = insert(models.GachaSeason).values(**self.asdict())
    await session.execute(stmt)


  async def add(self, session: AsyncSession) -> None:
    """
    Delete this gacha season.

    Args:
      session: Current database session
    """
    stmt = delete(models.GachaSeason).where(models.GachaSeason.id == self.id)
    await session.execute(stmt)