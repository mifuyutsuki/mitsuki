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


class GachaCollection(Base):
  """Database entry for card collections."""

  __tablename__ = "gacha_collections"

  id: Mapped[str] = mapped_column(primary_key=True)
  """ID of this collection."""
  name: Mapped[str]
  """Name of this collection."""
  description: Mapped[Optional[str]]
  """Description of this collection."""

  rollable: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether this collection is rollable, provided the roll cost."""
  discoverable: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether this collection is publicly viewable, showing held cards of this collection."""
  show_counts: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  """Whether to show total cards in this collection, per rarity and including unobtained, if discoverable is set."""

  roll_cost: Mapped[Optional[dict]] = mapped_column(JSON)
  """Items needed to roll once in this collection, if rollable is set, in format {item_id: amount, ...}."""


class GachaCollectionCard(Base):
  """Database relation for card collections."""

  __tablename__ = "gacha_collection_cards"

  collection: Mapped[str] = mapped_column(
    ForeignKey("gacha_collections.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
  )
  """Card collection ID."""
  card: Mapped[str] = mapped_column(
    ForeignKey("gacha_cards2.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
  )
  """ID of card in this collection."""