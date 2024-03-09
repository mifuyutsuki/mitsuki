# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from mitsuki.userdata import Base
from sqlalchemy import ForeignKey, Row
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from attrs import define, field
from attrs import asdict as _asdict


class Rolls(Base):
  __tablename__ = "gacha_rolls"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  user: Mapped[int]
  card: Mapped[str] = mapped_column(ForeignKey("gacha_cards.id"))
  time: Mapped[float]

  card_ref: Mapped["Card"] = relationship()

  def __repr__(self):
    return (
      f"Rolls(id={self.id!r}, user={self.user!r}, "
      f"time={self.time!r}, card={self.card!r})"
    )
  

class Currency(Base):
  __tablename__ = "gacha_currency"

  user: Mapped[int] = mapped_column(primary_key=True)
  amount: Mapped[int]
  last_daily: Mapped[Optional[float]]
  
  def __repr__(self):
    return (
      f"Currency(user={self.user!r}, amount{self.amount!r}, "
      f"last_daily={self.last_daily!r})"
    )


class Inventory(Base):
  __tablename__ = "gacha_inventory"

  user: Mapped[int] = mapped_column(primary_key=True)
  card: Mapped[str] = mapped_column(ForeignKey("gacha_cards.id"), primary_key=True)
  count: Mapped[int]
  first_acquired: Mapped[Optional[float]]

  card_ref: Mapped["Card"] = relationship()

  def __repr__(self):
    return (
      f"Inventory(id={self.id!r}, user={self.user!r}, "
      f"card={self.card!r}, count={self.count!r}, "
      f"first_acquired={self.first_acquired!r})"
    )


class Pity(Base):
  __tablename__ = "gacha_pity"

  user: Mapped[int] = mapped_column(primary_key=True)
  counter1: Mapped[int]
  counter2: Mapped[int]
  counter3: Mapped[int]
  counter4: Mapped[int]
  counter5: Mapped[int]
  counter6: Mapped[int]
  counter7: Mapped[int]
  counter8: Mapped[int]
  counter9: Mapped[int]

  def __repr__(self):
    return (
      f"Pity(user={self.user!r}, "
      f"counter1={self.counter1!r}, "
      f"counter2={self.counter2!r}, "
      f"counter3={self.counter3!r}, "
      f"counter4={self.counter4!r}, "
      f"counter5={self.counter5!r}, "
      f"counter6={self.counter6!r}, "
      f"counter7={self.counter7!r}, "
      f"counter8={self.counter8!r}, "
      f"counter9={self.counter9!r})"
    )


class Pity2(Base):
  __tablename__ = "gacha_pity2"

  user: Mapped[int] = mapped_column(primary_key=True)
  rarity: Mapped[int] = mapped_column(ForeignKey("gacha_settings.rarity"), primary_key=True)
  count: Mapped[int]

  rarity_ref: Mapped["Settings"] = relationship()

  def __repr__(self) -> str:
    return (
      f"Pity2(user={self.user!r}, "
      f"rarity={self.rarity!r}, count={self.count!r})"
    )


class Card(Base):
  __tablename__ = "gacha_cards"

  id: Mapped[str] = mapped_column(primary_key=True)
  name: Mapped[str]
  rarity: Mapped[int] = mapped_column(ForeignKey("gacha_settings.rarity"))
  type: Mapped[str]
  series: Mapped[str]
  image: Mapped[Optional[str]]

  rarity_ref: Mapped["Settings"] = relationship()

  def __repr__(self):
    return (
      f"Card(id={self.id!r}, name={self.name!r}, "
      f"rarity={self.rarity!r}, type={self.type!r}, "
      f"series={self.series!r}, image={self.image!r})"
    )


class Settings(Base):
  __tablename__ = "gacha_settings"

  rarity: Mapped[int] = mapped_column(primary_key=True)
  rate: Mapped[float]
  dupe_shards: Mapped[int] = mapped_column(default=0)
  color: Mapped[int]
  stars: Mapped[str]
  pity: Mapped[Optional[int]]


# =============================================================================

@define
class UserCard:
  user: int
  amount: int
  first_acquired: int
  card: str
  name: str
  rarity: int
  type: str
  series: str
  color: int = field(repr=False)
  stars: str = field(repr=False)
  
  image: Optional[str] = field(default=None)
  
  mention: str = field(init=False)

  @classmethod
  def create(cls, result: Row):
    return cls(
      user=result.Inventory.user,
      amount=result.Inventory.count,
      first_acquired=int(result.Inventory.first_acquired),
      card=result.Inventory.card,
      name=result.Card.name,
      rarity=result.Card.rarity,
      type=result.Card.type,
      series=result.Card.series,
      color=result.Settings.color,
      stars=result.Settings.stars,
      image=result.Card.image
    )
  
  @classmethod
  def create_many(cls, results: List[Row]):
    return [cls.create(result) for result in results]
  
  def __attrs_post_init__(self):
    self.mention = f"<@{self.user}>"

  def asdict(self):
    return _asdict(self)


@define
class UserPity:
  user: int
  rarity: int
  count: int

  @classmethod
  def create(cls, result: Pity2):
    return cls(user=result.user, rarity=result.rarity, count=result.count)
  
  @classmethod
  def create_many(cls, results: List[Pity2]):
    return [cls.create(result) for result in results]
  
  def asdict(self):
    return _asdict(self)


# =============================================================================


@define
class RosterCard:
  id: str
  name: str
  rarity: int
  type: str
  series: str
  color: int
  stars: str
  image: Optional[str] = field(default=None)

  @classmethod
  def from_db(cls, result: Row):
    return cls(
      id=result.Card.id,
      name=result.Card.name,
      rarity=result.Card.rarity,
      type=result.Card.type,
      series=result.Card.series,
      image=result.Card.image,
      color=result.Settings.color,
      stars=result.Settings.stars
    )
  
  @classmethod
  def from_db_many(cls, results: List[Row]):
    return [cls.from_db(result) for result in results]


@define
class SourceCard:
  id: str
  name: str
  rarity: int
  type: str
  series: str
  image: Optional[str] = field(default=None)
  
  def asdict(self):
    return _asdict(self)


@define
class SourceSettings:
  rarity: int
  rate: float
  pity: int
  dupe_shards: int
  color: int
  stars: str