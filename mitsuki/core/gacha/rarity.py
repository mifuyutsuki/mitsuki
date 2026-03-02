# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

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
from mitsuki.lib.emoji import get_emoji, AppEmoji
from mitsuki.core.settings import get_setting, Settings

import mitsuki.models.gacha as models


@attrs.define(kw_only=True)
class CardRarity(AsDict):
  """A gacha card rarity."""

  rarity: int
  """Card rarity, expressed as the amount of stars."""
  rate: float
  """Rate of obtaining cards of this rarity, relative to the sum of all rates."""
  dupe_shards: int
  """Amount of shards given on obtaining a duplicate of this rarity."""
  color: int
  """Color of this rarity, used to color the roll message embed."""
  pity: Optional[int] = attrs.field(default=None)
  """Amount of pity before a card of at least this rarity is given, if set."""
  emoji: Optional[str] = attrs.field(default=None)
  """Emoji name to use as the star, or the default `m_gc_star1` if unset."""


  @property
  def emoji_object(self):
    """
    Get the 'star' CustomEmoji/PartialEmoji object of this rarity.

    If this rarity's `emoji` is not set, returns the AppEmoji `m_gc_star1`.
    """
    return get_emoji(self.emoji or AppEmoji.GACHA_STAR_REGULAR)


  @property
  def emoji_str(self):
    """
    Get the 'star' emoji string of this rarity, multiplied by the rarity value.

    If this rarity's `emoji` is not set, uses the AppEmoji `m_gc_star1`.
    """
    return self.rarity * str(self.emoji_object)


  @classmethod
  async def fetch_all(cls):
    """
    Fetch all rarities, in ascending rarity order.

    Returns:
      List of rarity instances
    """
    query = select(models.CardRarity).order_by(models.CardRarity.rarity.asc())
    async with begin_session() as session:
      return [cls(**r.asdict()) for r in await session.scalars(query)]


  async def add(self, session: AsyncSession):
    """
    Add data for this rarity.

    Args:
      session: Current database session
    """
    stmt = insert(models.CardRarity).values(**self.asdict())
    await session.execute(stmt)