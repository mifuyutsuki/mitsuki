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


@attrs.define(kw_only=True)
class CardStats(AsDict):
  """A gacha card with annotated roll statistics."""

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

  rolled_count: int
  """Number of times this card has been rolled by users."""
  users_count: int
  """Number of users who have rolled this card."""
  first_rolled: Optional[ipy.Timestamp] = attrs.field(default=None, converter=option(ipy.Timestamp.fromtimestamp))
  """Time this card is first rolled/obtained by a user, if the card has been rolled."""
  last_rolled: Optional[ipy.Timestamp] = attrs.field(default=None, converter=option(ipy.Timestamp.fromtimestamp))
  """Time this card is last rolled/obtained by a user, if the card has been rolled."""
  first_rolled_by: Optional[ipy.Snowflake] = attrs.field(default=None, converter=option(ipy.Snowflake))
  """ID of user that first rolled/obtained this card, if the card has been rolled."""
  last_rolled_by: Optional[ipy.Snowflake] = attrs.field(default=None, converter=option(ipy.Snowflake))
  """ID of user that last rolled/obtained this card, if the card has been rolled."""


  @classmethod
  async def fetch(cls, id: str, *, private: bool = False) -> Optional[Self]:
    """
    Fetch global statistics of a card.

    Args:
      id: Card ID to fetch
      private: Whether to return non-public cards (cards with unlisted=True)

    Returns:
      Instance of card statistics, or `None` if card doesn't exist
    """
    group_query = (
      select(
        models.GachaRoll.card,
        sa.func.count(models.GachaRoll.id).label("rolled_count"),
        sa.func.count(models.GachaRoll.user.distinct()).label("users_count"),
        sa.func.min(models.GachaRoll.time).label("first_rolled"),
        sa.func.max(models.GachaRoll.time).label("last_rolled"),
      )
      .group_by(models.GachaRoll.card)
      .subquery()
    )
    first_query = select(models.GachaRoll).subquery()
    last_query = select(models.GachaRoll).subquery()
    roll_query = (
      select(
        group_query,
        first_query.c.user.label("first_rolled_by"),
        last_query.c.user.label("last_rolled_by"),
      )
      .join(first_query, first_query.c.time == group_query.c.first_rolled)
      .join(last_query, last_query.c.time == group_query.c.last_rolled)
      .subquery()
    )

    query = (
      select(
        models.Card,
        sa.func.coalesce(roll_query.c.rolled_count, 0).label("rolled_count"),
        sa.func.coalesce(roll_query.c.users_count, 0).label("users_count"),
        roll_query.c.first_rolled,
        roll_query.c.first_rolled_by,
        roll_query.c.last_rolled,
        roll_query.c.last_rolled_by,
      )
      .join(roll_query, roll_query.c.card == models.Card.id, isouter=True)
      .where(models.Card.id == id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      if result := (await session.execute(query)).first():
        return cls(
          **result.Card.asdict(),
          rolled_count=result.rolled_count,
          users_count=result.users_count,
          first_rolled=result.first_rolled,
          first_rolled_by=result.first_rolled_by,
          last_rolled=result.last_rolled,
          last_rolled_by=result.last_rolled_by,
        )