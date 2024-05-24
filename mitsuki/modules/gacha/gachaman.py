# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from yaml import safe_load
from typing import Dict, List, Optional, Any, Callable, TypeVar
from random import SystemRandom

from mitsuki import settings

from .schema import SourceCard, SourceSettings
from .userdata import add_cards, add_settings

T = TypeVar("T")


class Gachaman:
  cost: int
  currency_icon: str
  currency_name: str
  daily_shards: int
  daily_tz: int

  premium_daily_shards: Optional[int]
  premium_guilds: Optional[List[int]]

  first_time_shards: Optional[int]

  of_rarity: Dict[int, SourceSettings]
  rarities: List[int]

  rates: Dict[int, float]
  pity: Dict[int, int]
  dupe_shards: Dict[int, int]
  colors: Dict[int, int]
  stars: Dict[int, str]

  cards: Dict[str, SourceCard]
  rarity_map: Dict[int, List[str]]
  type_map: Dict[str, List[str]]
  series_map: Dict[str, List[str]]

  _data_settings: Dict[str, Any]
  _data_roster: Dict[str, Dict]
  _settings_yaml: str
  _roster_yaml: str

  arona: SystemRandom = SystemRandom()


  def __init__(self, settings_yaml: str, roster_yaml: str):
    self.reload(settings_yaml=settings_yaml, roster_yaml=roster_yaml)


  def reload(
    self,
    settings_yaml: Optional[str] = None,
    roster_yaml: Optional[str] = None
  ):
    settings_yaml = settings_yaml or self._settings_yaml
    roster_yaml   = roster_yaml or self._roster_yaml

    self._load_settings(settings_yaml)
    self._load_roster(roster_yaml)

    self._settings_yaml = settings_yaml
    self._roster_yaml = roster_yaml


  async def sync_db(self):
    await add_settings(self.of_rarity.values())
    await add_cards(self.cards.values())


  def from_id(self, id: str):
    return self.cards.get(id)


  def from_ids(self, ids: List[str]):
    cards: List[SourceCard] = []
    for id in ids:
      card = self.from_id(id)
      if card is not None:
        cards.append(card)

    return cards


  def roll(self, min_rarity: Optional[int] = None, user_pity: Optional[Dict[int, int]] = None):
    min_rarity  = min_rarity or self.rarities[0]
    rarity_get  = self.rarities[0]
    arona_value = self.arona.random()

    if user_pity:
      for rarity, pity in self.pity.items():
        if pity > 1 and user_pity.get(rarity, 0) >= pity - 1:
          min_rarity = max(rarity, min_rarity)

    for rarity in self.rarities:
      rarity_get   = rarity
      arona_value -= self.rates[rarity]
      if rarity < min_rarity:
        continue
      if arona_value < 0.0:
        break

    available_picks = None
    while available_picks is None and rarity_get > 0:
      available_picks = self.rarity_map.get(rarity_get)
      rarity_get -= 1

    arona_pick = self.arona.choice(available_picks)
    return self.cards[arona_pick]


  @property
  def currency(self):
    return f"{self.currency_icon} {self.currency_name}".strip()


  # ===========================================================================  

  def _load_settings(self, filename: str):
    _data: Dict = _load_yaml(filename)
    self._settings_yaml = filename

    self.cost          = _data["cost"]
    self.currency_icon = _data["currency_icon"]
    self.currency_name = _data.get("currency_name")
    self.daily_shards  = _data.get("daily_shards")
    self.daily_tz      = _data.get("daily_tz")

    self.premium_daily_shards = _data.get("premium_daily_shards")
    self.premium_guilds       = _data.get("premium_guilds")
    self.first_time_shards    = _data.get("first_time_shards")

    self.of_rarity = self._parse_settings(_data)

    rarities = self.of_rarity.keys()
    self.rates       = {r: self.of_rarity[r].rate for r in rarities}
    self.pity        = {r: self.of_rarity[r].pity for r in rarities}
    self.dupe_shards = {r: self.of_rarity[r].dupe_shards for r in rarities}
    self.colors      = {r: self.of_rarity[r].color for r in rarities}
    self.stars       = {r: self.of_rarity[r].stars for r in rarities}
    self.rarities    = sorted(rarities)


  def _load_roster(self, filename: str):
    _data: Dict = _load_yaml(filename)
    self._roster_yaml = filename

    self.cards      = {}
    self.rarity_map = {}
    self.type_map   = {}
    self.series_map = {}

    for id, data in _data.items():
      try:
        # Mandatory fields
        name = data["name"]
        rarity = data["rarity"]
        type = data["type"]
        series = data["series"]
      except KeyError:
        continue

      image = data.get("image")
      self.cards[id] = SourceCard(id, name, rarity, type, series, image)

      if rarity not in self.rarity_map.keys():
        self.rarity_map[rarity] = []
      self.rarity_map[rarity].append(id)

      if type not in self.type_map.keys():
        self.type_map[type] = []
      self.type_map[type].append(id)

      if series not in self.series_map.keys():
        self.series_map[series] = []
      self.series_map[series].append(id)


  def _parse_settings(self, data: Dict):
    rates_get: Dict[str, float]     = data.get("rates") or {}
    pity_get: Dict[str, float]      = data.get("pity") or {}
    dupe_shards_get: Dict[str, int] = data.get("dupe_shards") or {}
    colors_get: Dict[str, int]      = data.get("colors") or {}
    stars_get: Dict[str, str]       = data.get("stars") or {}

    # Rates are loaded first
    rarities = []
    total_weight = sum(rates_get.values())
    rates: Dict[int, float] = _transform_settings(
      rates_get,
      lambda weight: weight / total_weight
    )
    rarities.extend(sorted(rates.keys()))

    # Everything else
    pity: Dict[int, int] = {r: 0 for r in rarities}
    pity.update(_transform_settings(pity_get))

    dupe_shards: Dict[int, int] = {r: 0 for r in rarities}
    dupe_shards.update(_transform_settings(dupe_shards_get))

    colors: Dict[int, int] = {r: 0x0000ff for r in rarities}
    colors.update(_transform_settings(colors_get))

    stars: Dict[int, str] = {r: "" for r in rarities}
    stars.update(_transform_settings(stars_get))

    settings: Dict[int, SourceSettings] = {
      r: SourceSettings(
        rarity=r,
        rate=rates[r],
        pity=pity[r],
        dupe_shards=dupe_shards[r],
        color=colors[r],
        stars=stars[r]
      ) for r in rarities
    }
    return settings


# =================================================================


def _load_yaml(filename: str):
  with open(filename, encoding='UTF-8') as f:
    return safe_load(f)


def _transform_settings(data: Dict[str, Any], function: Optional[Callable[[T], T]] = None):
  function = function or (lambda v: v)
  new_data = {}
  for k, v in data.items():
    new_data[int(k[1:])] = function(v)
  return new_data


# =================================================================


_settings_yaml = settings.gacha.settings
_roster_yaml   = settings.gacha.roster

gacha = Gachaman(
  settings_yaml=_settings_yaml,
  roster_yaml=_roster_yaml
)


def reload():
  global gacha
  gacha = Gachaman(
    settings_yaml=_settings_yaml,
    roster_yaml=_roster_yaml
  )