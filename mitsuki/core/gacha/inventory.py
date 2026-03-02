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
from mitsuki.core.gacha import Card


@attrs.define(kw_only=True)
class UserCard(AsDict):
  """
  A gacha card that has been rolled by a user.
  """

  user: ipy.Snowflake
  """ID of user holding this card."""
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

  count: int
  """Amount this user holds the card."""
  rolled_count: int
  """Number of times this user rolled the card."""
  first_rolled: ipy.Timestamp = attrs.field(converter=ipy.Timestamp.fromtimestamp)
  """Time this user first rolled this card."""
  last_rolled: ipy.Timestamp = attrs.field(converter=ipy.Timestamp.fromtimestamp)
  """Time this user last rolled this card."""


  @classmethod
  async def fetch(cls, id: str, user: Union[ipy.BaseUser, ipy.Snowflake], *, private: bool = False):
    """
    Fetch a user card.

    Args:
      id: Card ID
      user: User holding the card
      private: Whether to return non-public cards (cards with unlisted=True)
    
    Returns:
      Instance of user card, or `None` of card doesn't exist or is unlisted
    """
    if not isinstance(user, int):
      user = user.id

    roll_query = (
      select(
        models.GachaRoll.user,
        models.GachaRoll.card,
        sa.func.count(models.GachaRoll.card).label("rolled_count"),
        sa.func.min(models.GachaRoll.time).label("first_rolled"),
        sa.func.max(models.GachaRoll.time).label("last_rolled"),
      )
      .group_by(models.GachaRoll.user, models.GachaRoll.card)
      .subquery()
    )
    query = (
      select(
        models.Card,
        models.UserCard.user,
        models.UserCard.count,
        roll_query.c.rolled_count,
        roll_query.c.first_rolled,
        roll_query.c.last_rolled,
      )
      .join(models.UserCard, models.UserCard.card == models.Card.id)
      .join(roll_query, (roll_query.c.user == models.UserCard.user) & (roll_query.c.card == models.UserCard.card))
      .where(models.UserCard.user == user)
      .where(models.UserCard.card == id)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    async with begin_session() as session:
      if result := (await session.execute(query)).first():
        return cls(
          **result.Card.asdict(),
          user=result.user, count=result.count, rolled_count=result.rolled_count,
          first_rolled=result.first_rolled, last_rolled=result.last_rolled
        )


  @classmethod
  async def fetch_all(
    cls,
    user: Union[ipy.BaseUser, ipy.Snowflake],
    *,
    sort: Optional[str] = None,
    private: bool = False):
    """
    Fetch all cards own by the specified user.

    Args:
      user: Target user
      sort: Sort card by (date, rarity, alpha, series, count, id)
      private: Whether to return non-public cards (cards with unlisted=True)

    Returns:
      List of user cards, or empty list if user doesn't exist
    """
    if not isinstance(user, int):
      user = user.id
    sort = sort or "date"

    roll_query = (
      select(
        models.GachaRoll.user,
        models.GachaRoll.card,
        sa.func.count(models.GachaRoll.card).label("rolled_count"),
        sa.func.min(models.GachaRoll.time).label("first_rolled"),
        sa.func.max(models.GachaRoll.time).label("last_rolled"),
      )
      .group_by(models.GachaRoll.user, models.GachaRoll.card)
      .subquery()
    )
    query = (
      select(
        models.Card,
        models.UserCard.user,
        models.UserCard.count,
        roll_query.c.rolled_count,
        roll_query.c.first_rolled,
        roll_query.c.last_rolled,
      )
      .join(models.UserCard, models.UserCard.card == models.Card.id)
      .join(roll_query, (roll_query.c.user == models.UserCard.user) & (roll_query.c.card == models.UserCard.card))
      .where(models.UserCard.user == user)
    )
    if not private:
      query = query.where(models.Card.unlisted == False)

    match sort.lower():
      case "date":
        query = query.order_by(roll_query.c.first_rolled.desc())
      case "rarity":
        query = query.order_by(models.Card.rarity.desc()).order_by(roll_query.c.first_rolled.desc())
      case "alpha":
        query = query.order_by(sa.func.lower(models.Card.name))
      case "series":
        query = (
          query.order_by(models.Card.type).order_by(models.Card.series)
          .order_by(models.Card.rarity).order_by(models.Card.id)
        )
      case "count":
        query = query.order_by(models.UserCard.count.desc()).order_by(roll_query.c.first_rolled.desc())
      case "id":
        query = query.order_by(models.Card.id)
      case _:
        raise ValueError(f"Invalid sort setting '{sort}'")

    async with begin_session() as session:
      results = (await session.execute(query)).all()
    return [
      cls(
        **result.Card.asdict(),
        user=result.user, count=result.count, rolled_count=result.rolled_count,
        first_rolled=result.first_rolled, last_rolled=result.last_rolled
      ) for result in results
    ]