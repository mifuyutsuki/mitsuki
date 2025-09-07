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


class GachaRoll(Base):
  """Database entry of user gacha rolls."""

  __tablename__ = "gacha_rolls"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  """ID of this roll."""
  user: Mapped[int] = mapped_column(BigInteger)
  """ID of user who rolled this card."""
  card: Mapped[str]
  """ID of card being rolled."""
  time: Mapped[float]
  """Time this card was rolled, in timestamp format."""

  pity_excluded: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether this card does not count towards the user's pity (e.g. collection rolls)."""
  collection: Mapped[Optional[str]]
  """The collection this card is rolled from (including seasons), if any."""