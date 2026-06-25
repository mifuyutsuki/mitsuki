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


class GachaCollectionCategory(Base):
  """Database entry for card collection categories."""

  __tablename__ = "gacha_collection_categories"

  id: Mapped[str] = mapped_column(primary_key=True)
  """ID of this collection category."""
  name: Mapped[str]
  """Name of this collection category."""
  description: Mapped[Optional[str]]
  """Description of this collection category."""


class GachaCollectionCategoryEntry(Base):
  """Database relation for card collection categories."""

  __tablename__ = "gacha_collection_category_entries"

  category: Mapped[str] = mapped_column(
    ForeignKey("gacha_collection_categories.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
  )
  """Collection category ID."""
  collection: Mapped[str] = mapped_column(
    ForeignKey("gacha_collections.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
  )
  """ID of collection in this category."""