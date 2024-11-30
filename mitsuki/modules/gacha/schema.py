# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import ForeignKey, Row
from sqlalchemy.orm import Mapped, mapped_column
from rapidfuzz import fuzz
from typing import Optional, List, Callable
from attrs import define, field
from attrs import asdict as _asdict

from mitsuki.lib.userdata import Base, AsDict
from mitsuki.utils import escape_text

# New definitions
from .schema2 import *


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
  first_acquired_f: str = field(init=False)
  first_acquired_d: str = field(init=False)
  linked_name: str = field(init=False)

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
      image=result.Card.image,

      color=result.Settings.color,
      stars=result.Settings.stars
    )

  @classmethod
  def create_many(cls, results: List[Row]):
    return [cls.create(result) for result in results]

  def __attrs_post_init__(self):
    self.mention = f"<@{self.user}>"
    self.first_acquired_f = f"<t:{self.first_acquired}:f>"
    self.first_acquired_d = f"<t:{self.first_acquired}:D>"
    self.linked_name = f"[{escape_text(self.name)}]({self.image})" if self.image else self.name

  def asdict(self):
    return _asdict(self)


@define
class UserPity:
  user: int
  rarity: int
  count: int

  @classmethod
  def create(cls, result: Pity):
    return cls(user=result.user, rarity=result.rarity, count=result.count)

  @classmethod
  def create_many(cls, results: List[Pity]):
    return [cls.create(result) for result in results]

  def asdict(self):
    return _asdict(self)


# =============================================================================


@define
class SearchCard:
  id: str
  search: str
  score: float = field(default=0.0)

  @classmethod
  def from_db(
    cls,
    result: Row,
    search_key: str,
    ratio: Callable[[str, str], float] = fuzz.token_ratio,
    **ratio_kwargs
  ):
    return cls(
      id=result.id,
      search=result.search,
      score=ratio(search_key, result.search, **ratio_kwargs)
    )

  @classmethod
  def from_db_many(
    cls,
    results: List[Row],
    search_key: str,
    cutoff: float = 0.0,
    ratio: Callable[[str, str], float] = fuzz.token_ratio,
    **ratio_kwargs
  ):
    li = [
      cls.from_db(result, search_key, ratio, **ratio_kwargs) for result in results
    ]
    li.sort(key=lambda c: c.score, reverse=True)
    return [i for i in li if i.score >= cutoff]


@define
class RosterCard:
  id: str
  name: str
  rarity: int
  type: str
  series: str

  color: int
  stars: str
  dupe_shards: int
  image: Optional[str] = field(default=None)

  card: str = field(init=False)
  card_id: str = field(init=False)
  linked_name: str = field(init=False)

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
      stars=result.Settings.stars,
      dupe_shards=result.Settings.dupe_shards
    )

  @classmethod
  def from_db_many(cls, results: List[Row]):
    return [cls.from_db(result) for result in results]

  def __attrs_post_init__(self):
    self.card = self.id    # Used by /gacha view
    self.card_id = self.id # Used by /system gacha cards
    self.linked_name = f"[{escape_text(self.name)}]({self.image})" if self.image else self.name

  def asdict(self):
    return _asdict(self)


@define
class StatsCard:
  id: str
  name: str
  rarity: int
  type: str
  series: str

  color: int
  stars: str
  image: Optional[str] = field(default=None)

  users: int = field(default=0)
  rolled: int = field(default=0)
  first_user_acquired_float: Optional[float] = field(default=None)
  first_user: Optional[int] = field(default=None)
  last_user_acquired_float: Optional[float] = field(default=None)
  last_user: Optional[int] = field(default=None)

  card: str = field(init=False)
  card_id: str = field(init=False)
  linked_name: str = field(init=False)

  first_user_mention: Optional[str] = field(init=False)
  first_user_acquired: Optional[int] = field(init=False)
  first_user_acquired_f: str = field(init=False)
  first_user_acquired_d: str = field(init=False)
  last_user_mention: Optional[str] = field(init=False)
  last_user_acquired: Optional[int] = field(init=False)
  last_user_acquired_f: str = field(init=False)
  last_user_acquired_d: str = field(init=False)

  @classmethod
  def from_db(cls, result: Row):
    return cls(
      id=result.id,
      name=result.name,
      rarity=result.rarity,
      type=result.type,
      series=result.series,
      image=result.image,

      users=result.users,
      rolled=result.rolled,
      first_user_acquired_float=result.first_user_acquired,
      first_user=result.first_user,
      last_user_acquired_float=result.last_user_acquired,
      last_user=result.last_user,

      color=result.color,
      stars=result.stars
    )

  @classmethod
  def from_db_many(cls, results: List[Row]):
    return [cls.from_db(result) for result in results]

  def __attrs_post_init__(self):
    self.first_user_mention = f"<@{self.first_user}>" if self.first_user else "-"
    self.first_user_acquired = (
      int(self.first_user_acquired_float) if self.first_user_acquired_float else None
    )
    self.first_user_acquired_f = (
      f"<t:{self.first_user_acquired}:f>" if self.first_user_acquired else "-"
    )
    self.first_user_acquired_d = (
      f"<t:{self.first_user_acquired}:D>" if self.first_user_acquired else "-"
    )
    self.last_user_mention = f"<@{self.last_user}>" if self.last_user else "-"
    self.last_user_acquired = (
      int(self.last_user_acquired_float) if self.last_user_acquired_float else None
    )
    self.last_user_acquired_f = (
      f"<t:{self.last_user_acquired}:f>" if self.last_user_acquired else "-"
    )
    self.last_user_acquired_d = (
      f"<t:{self.last_user_acquired}:D>" if self.last_user_acquired else "-"
    )
    self.card = self.id    # Used by /gacha view
    self.card_id = self.id # Used by /system gacha cards
    self.linked_name = f"[{escape_text(self.name)}]({self.image})" if self.image else self.name

  def asdict(self):
    return _asdict(self)


@define
class UserStats(AsDict):
  rarity: int
  stars: str
  cards: int
  rolled: int

  set_pity: Optional[int] = field(default=None)
  user_pity: Optional[int] = field(default=None)

  last_id: Optional[str] = field(default=None)
  last_name: Optional[str] = field(default=None)
  last_rarity: Optional[int] = field(default=None)
  last_type: Optional[str] = field(default=None)
  last_series: Optional[str] = field(default=None)
  last_image: Optional[str] = field(default=None)

  last_time_float: Optional[float] = field(default=None)
  last_time: Optional[int] = field(default=None, init=False)
  last_time_f: Optional[str] = field(default="-", init=False)
  last_time_d: Optional[str] = field(default="-", init=False)

  def __attrs_post_init__(self):
    if self.last_time_float:
      self.last_time = int(self.last_time_float)
      self.last_time_f = f"<t:{self.last_time}:f>"
      self.last_time_d = f"<t:{self.last_time}:D>"

  @classmethod
  def from_db(cls, result: Row):
    return cls(
      rarity=result.Settings.rarity,
      stars=result.Settings.stars,
      cards=result.cards,
      rolled=result.rolled,
      set_pity=result.Settings.pity,
      user_pity=result.pity_count,

      last_id=result.id,
      last_name=result.name,
      last_type=result.type,
      last_series=result.series,
      last_image=result.image,
      last_time_float=result.time,
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
  group: str = field(default="-")

  image: Optional[str] = field(default=None)

  def __attrs_post_init__(self):
    if self.group == "-":
      self.group = self.type

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