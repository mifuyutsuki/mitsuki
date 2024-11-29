# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from mitsuki.lib.userdata import Base


class Roll(Base):
  __tablename__ = "gacha_rolls"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  user: Mapped[int]
  card: Mapped[str]
  time: Mapped[float]


class Currency(Base):
  __tablename__ = "gacha_currency"

  user: Mapped[int] = mapped_column(primary_key=True)
  amount: Mapped[int]
  last_daily: Mapped[Optional[float]]
  first_daily: Mapped[Optional[float]]


class Inventory(Base):
  __tablename__ = "gacha_inventory"

  user: Mapped[int] = mapped_column(primary_key=True)
  card: Mapped[str] = mapped_column(primary_key=True)
  count: Mapped[int]
  first_acquired: Mapped[Optional[float]]


class Pity(Base):
  __tablename__ = "gacha_pity2"

  user: Mapped[int] = mapped_column(primary_key=True)
  rarity: Mapped[int] = mapped_column(primary_key=True)
  count: Mapped[int]


class Card(Base):
  __tablename__ = "gacha_cards2"

  id: Mapped[str] = mapped_column(primary_key=True)
  name: Mapped[str]
  rarity: Mapped[int] = mapped_column(ForeignKey("gacha_settings.rarity"))
  type: Mapped[str]
  series: Mapped[str]
  image: Mapped[Optional[str]]

  group: Mapped[str]
  tags: Mapped[Optional[str]]

  limited: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  locked: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  unlisted: Mapped[bool] = mapped_column(server_default=text("FALSE"))


class Settings(Base):
  __tablename__ = "gacha_settings"

  rarity: Mapped[int] = mapped_column(primary_key=True)
  rate: Mapped[float]
  dupe_shards: Mapped[int] = mapped_column(default=0)
  color: Mapped[int]
  stars: Mapped[str]
  pity: Mapped[Optional[int]]


class Banner(Base):
  __tablename__ = "gacha_banners"

  id: Mapped[str] = mapped_column(primary_key=True)
  name: Mapped[str]
  active: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  start_time: Mapped[Optional[float]]
  end_time: Mapped[Optional[float]]
  rate: Mapped[float] = mapped_column(server_default=text("0.0"))
  min_rarity: Mapped[Optional[int]]
  max_rarity: Mapped[Optional[int]]


class BannerCard(Base):
  __tablename__ = "gacha_banner_cards"
  __table_args__ = (
    UniqueConstraint("card", "banner"),
  )

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  card: Mapped[str] = mapped_column(ForeignKey("gacha_cards2.id"))
  banner: Mapped[str] = mapped_column(ForeignKey("gacha_banners.id"))


class Tags(Base):
  __tablename__ = "gacha_tags"

  id: Mapped[str] = mapped_column(primary_key=True)
  name: Mapped[str]
  description: Mapped[str]