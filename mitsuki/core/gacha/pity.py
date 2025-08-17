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
class UserPity(AsDict):
  """Pity counter of a user for this card rarity."""

  user: ipy.Snowflake = attrs.field(converter=ipy.Snowflake)
  """Gacha user ID."""
  rarity: int
  """Card rarity for the pity counter."""
  count: int
  """User's pity counter for this card rarity."""


  @classmethod
  async def fetch(cls, session: AsyncSession, user: Union[ipy.BaseUser, ipy.Snowflake]) -> list[Self]:
    """
    Fetch pity counters of a given gacha user.

    Args:
      session: Current database session
      user: Snowflake or instance of the user

    Returns:
      List of user pity counters, or `None` if either the user has not
      registered, or no rarities have pity
    """
    if isinstance(user, ipy.BaseUser):
      user = user.id

    query = (
      select(models.UserPity)
      .join(models.CardRarity, models.CardRarity.rarity == models.UserPity.rarity)
      .where(models.UserPity.user == user)
      .where(models.CardRarity.pity > 1)
    )

    results = await session.scalars(query)
    if len(results) > 0:
      return [cls(**r.asdict()) for r in results]
    return []