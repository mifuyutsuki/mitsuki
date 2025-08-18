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


class UserPity(Base):
  """Database entry of users' pity counters."""

  __tablename__ = "gacha_pity2"

  user: Mapped[int] = mapped_column(BigInteger, primary_key=True)
  """Gacha user ID."""
  rarity: Mapped[int] = mapped_column(primary_key=True)
  """Card rarity for the pity counter."""
  count: Mapped[int]
  """User's pity counter for this rarity."""