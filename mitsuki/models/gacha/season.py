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
from sqlalchemy.types import BigInteger, JSON
from typing import Optional

from mitsuki.lib.userdata import Base, AsDict


class GachaSeason(Base):
  """Database entry for gacha seasons."""

  __tablename__ = "gacha_seasons"

  id: Mapped[str] = mapped_column(primary_key=True)
  """Season ID."""
  name: Mapped[str]
  """Name of this season."""
  description: Mapped[Optional[str]]
  """Description of this season."""
  image: Mapped[Optional[str]]
  """Banner image of this collection."""
  collection: Mapped[str] = mapped_column(ForeignKey("gacha_collections.id"))
  """ID of the collection containing rate-up cards of this season."""
  pickup_rate: Mapped[float]
  """Rate of rolling this season's rate-up cards over the general pool, out of 1.0."""
  start_time: Mapped[float]
  """Time this season starts after the previous ends, in timestamp format."""
  end_time: Mapped[float]
  """Time this season ends and the next one begins, in timestamp format."""