# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

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


class Card(Base):
  """Database entry of gacha cards."""

  __tablename__ = "gacha_cards"

  id: Mapped[str] = mapped_column(primary_key=True)
  """ID of this card."""
  name: Mapped[str]
  """Name of this card."""
  rarity: Mapped[int] = mapped_column(ForeignKey("gacha_settings.rarity"))
  """Rarity of this card expressed as the amount of stars."""
  type: Mapped[str]
  """Type of this card, e.g. 'Event'."""
  series: Mapped[str]
  """Series of this card, e.g. 'Mitsuki (Summer)'"""
  image: Mapped[Optional[str]]
  """URL to card image."""

  limited: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether the card is only rollable as a season pick-up or using collection tickets."""
  locked: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether the card is not rollable, but obtainable using collection tickets."""
  unlisted: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether the card is neither rollable nor viewable, i.e. 'deleted'."""