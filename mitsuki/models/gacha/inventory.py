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


class UserCard(Base):
  """Database entry for a user's held cards."""

  __tablename__ = "gacha_inventory"

  user: Mapped[BigInteger] = mapped_column(primary_key=True)
  """Gacha user ID."""
  card: Mapped[str] = mapped_column(primary_key=True)
  """Card ID."""
  count: Mapped[int]
  """Amount of this card held by this user."""

  # Deprecated in v5.0, now served by gacha_rolls
  # first_acquired: Mapped[Optional[float]]