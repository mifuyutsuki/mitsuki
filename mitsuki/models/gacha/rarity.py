# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import ForeignKey, Row, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import BigInteger
from typing import Optional

from mitsuki.lib.userdata import Base, AsDict


class CardRarity(Base):
  """Database entry of gacha card rarities, which store per-rarity settings."""

  __tablename__ = "gacha_settings"

  rarity: Mapped[int] = mapped_column(primary_key=True)
  """Card rarity, expressed as the amount of stars."""
  rate: Mapped[float]
  """Rate of obtaining cards of this rarity, relative to the sum of all rates."""
  dupe_shards: Mapped[int] = mapped_column(default=0)
  """Amount of shards given on obtaining a duplicate of this rarity."""
  color: Mapped[int]
  """Color of this rarity, used to color the roll message embed."""
  pity: Mapped[Optional[int]]
  """Amount of pity before a card of at least this rarity is given, if set."""
  emoji: Mapped[Optional[str]]
  """Emoji name to use as the star, or the default `m_gacha_star` if unset."""

  # Deprecated in v5.0, replaced by 'emoji' field
  # stars: Mapped[str]