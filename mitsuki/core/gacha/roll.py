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
from mitsuki.lib.emoji import get_emoji, AppEmoji
from mitsuki.core.settings import get_setting, Settings

import mitsuki.models.gacha as models
from mitsuki.core.gacha import Card


@attrs.define(kw_only=True)
class UserCardRoll(AsDict):
  """
  A user's gacha roll.
  """

  user: ipy.Snowflake
  """ID of user holding this card."""
  time: ipy.Timestamp = attrs.field(converter=ipy.Timestamp.fromtimestamp)
  """Time this user rolled this card."""

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

  color: int = attrs.field(default=0x46a1eb, eq=False)
  """Accent color of this card, which depends on its rarity."""
  dupe_shards: int = attrs.field(default=75, eq=False)
  """Amount of shards given on obtaining a duplicate of this rarity."""
  emoji: Optional[str] = attrs.field(default=None, eq=False)
  """Emoji name to use as the rarity star, or the default `m_gc_star1` if unset."""


  @property
  def emoji_str(self):
    """
    Get the 'star' emoji string of this rarity, multiplied by the rarity value.

    If this object's `emoji` is not set, this uses the AppEmoji `m_gc_star1`.
    """
    emoji = get_emoji(self.emoji or AppEmoji.GACHA_STAR_REGULAR)
    return self.rarity * str(emoji)


  @classmethod
  async def fetch_recent(cls, session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake], *, cards: int = 5):
    """
    Fetch a user's most recent rolls.

    This method excludes non-public cards from the list (cards with unlisted=True).

    Args:
      session: Current database session
      user: Snowflake or instance of the user
      cards: Number of recent rolls to fetch

    Returns:
      List of cards, sorted from latest rolled
    """
    query = (
      select(
        models.Card,
        models.CardRarity.color,
        models.CardRarity.dupe_shards,
        models.CardRarity.emoji,
        models.GachaRoll.user,
        models.GachaRoll.time,
      )
      .join(models.GachaRoll, models.GachaRoll.card == models.Card.id)
      .join(models.CardRarity, models.CardRarity.rarity == models.Card.rarity)
      .where(models.GachaRoll.user == user)
      .where(models.Card.unlisted == False)
      .order_by(models.GachaRoll.time.desc())
      .limit(cards)
    )
    results = (await session.execute(query)).all()
    return [
      cls(**r.Card.asdict(), color=r.color, dupe_shards=r.dupe_shards, emoji=r.emoji, user=r.user, time=r.time)
      for r in results
    ]