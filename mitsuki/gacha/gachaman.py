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
from os import environ

from .schema import SourceCard, SourceSettings
from .userdata import add_cards, add_settings

T = TypeVar("T")


class Gachaman:
  def __init__(self, settings_yaml: str, roster_yaml: str):
    self.reload(settings_yaml=settings_yaml, roster_yaml=roster_yaml)
  
  
  def reload(
    self,
    settings_yaml: Optional[str] = None,
    roster_yaml: Optional[str] = None
  ):
    settings_yaml = settings_yaml if settings_yaml else self._settings_yaml
    roster_yaml   = roster_yaml if roster_yaml else self._roster_yaml

    self.settings = Settings(settings_yaml=settings_yaml)
    self.roster   = Roster(roster_yaml=roster_yaml)
    self.random   = SystemRandom()
    
    self._settings_yaml = settings_yaml
    self._roster_yaml = roster_yaml
  

  async def sync_db(self):
    await self.settings.sync_db()
    await self.roster.sync_db()

  
  # =================================================================
  

  def roll(self, min_rarity: Optional[int] = None):
    rates = self.settings.rates
    roll  = self.random.random
    pick  = self.random.choice

    # TODO: Replace min_rarity arg with dict of pity counter

    rarities   = sorted(rates.keys())
    rarity_1   = rarities[0]
    rarity_min = max(min_rarity, rarity_1) if min_rarity else rarity_1

    rarity_get = rarity_min
    arona      = roll()

    for rarity in rarities:
      arona -= rates[rarity]
      if rarity < rarity_min:
        continue

      if arona < 0.0:
        rarity_get = rarity
        break

    available_picks = None
    while available_picks is None and rarity_get > 0:
      available_picks = self.roster.rarity_map.get(rarity_get)
      rarity_get -= 1

    picked = pick(available_picks)
    return self.roster.cards[picked]


  def refresh_random(self):
    self.random = SystemRandom()


# =================================================================
  

class Settings:
  def __init__(self, settings_yaml: str):
    self.reload(settings_yaml=settings_yaml)


  def reload(self, settings_yaml: Optional[str] = None):
    settings_yaml = settings_yaml if settings_yaml else self._settings_yaml

    self._data: dict         = _load_yaml(settings_yaml)
    self._settings_yaml: str = settings_yaml

    self.cost: int                   = self._data.get("cost")
    self.currency_icon: str          = self._data.get("currency_icon")
    self.currency_name: str          = self._data.get("currency_name")
    self.currency: str               = f"{self.currency_icon} {self.currency_name}"
    self.daily_shards: int           = self._data.get("daily_shards")
    self.daily_tz: int               = self._data.get("daily_tz")

    self.of_rarity: Dict[int, SourceSettings] = self._load()

    # Due to how roll() works, rarities order is reversed
    rarities = self.of_rarity.keys()
    self.rarities: List[int] = sorted(rarities, reverse=True)

    self.rates: Dict[int, float]     = {r: self.of_rarity[r].rate for r in rarities}
    self.pity: Dict[int, int]        = {r: self.of_rarity[r].pity for r in rarities}
    self.dupe_shards: Dict[int, int] = {r: self.of_rarity[r].dupe_shards for r in rarities}
    self.colors: Dict[int, int]      = {r: self.of_rarity[r].color for r in rarities}
    self.stars: Dict[int, str]       = {r: self.of_rarity[r].stars for r in rarities}

    self.rarities: List[int]         = sorted(self.rates.keys(), reverse=True)
    
  
  async def sync_db(self):
    await add_settings(self.of_rarity.values())


  # =================================================================
  # Internal helpers


  def _load(self):
    rates_get: Dict[str, float] = self._data.get("rates") or {}
    pity_get: Dict[str, float] = self._data.get("pity") or {}
    dupe_shards_get: Dict[str, int] = self._data.get("dupe_shards") or {}
    colors_get: Dict[str, int] = self._data.get("colors") or {}
    stars_get: Dict[str, str] = self._data.get("stars") or {}

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


  def _load_rates(self):
    data: Dict[str, float] = self._data.get("rates")
    if data is None:
      return {}
    
    rates: Dict[int, float] = {}
    total_weight = sum(data.values())
    for rarity_key, weight in data.items():
      rarity = int(rarity_key[1:2])
      rate   = weight / total_weight
      rates[rarity] = rate
    
    return rates


  def _load_pity(self):
    data: Dict[str, float] = self._data.get("pity")
    if data is None:
      return {}

    pity: Dict[int, int] = {}

    for rarity_key, rarity_pity in data.items():
      rarity = int(rarity_key[1:2])
      pity[rarity] = rarity_pity

    return pity


  def _load_dupe_shards(self):
    data: Dict[str, int] = self._data.get("dupe_shards")
    if data is None:
      return {}
    
    available_rarities = self.rates.keys()

    dupe_shards: Dict[int, int] = {
      available_rarity: 0 for available_rarity in available_rarities
    }

    for rarity_key, dupe_shards_amount in data.items():
      rarity = int(rarity_key[1:2])

      if rarity in dupe_shards.keys():
        dupe_shards[rarity] = dupe_shards_amount
    
    return dupe_shards


  def _load_colors(self):
    data: Dict[str, int] = self._data.get("colors")
    if data is None:
      return {}
    
    colors: Dict[int, int] = {}
    for rarity_key, color in data.items():
      rarity = int(rarity_key[1:2])
      colors[rarity] = color
    
    return colors
  

  def _load_stars(self):
    data: Dict[str, int] = self._data.get("stars")
    if data is None:
      return {}
    
    stars: Dict[int, str] = {}
    for rarity_key, rarity_stars in data.items():
      rarity = int(rarity_key[1:2])
      stars[rarity] = rarity_stars
    
    return stars


class Roster:
  def __init__(self, roster_yaml: str):
    self.reload(roster_yaml=roster_yaml)


  def reload(self, roster_yaml: Optional[str] = None):
    roster_yaml: str       = roster_yaml if roster_yaml else self._roster_yaml
    self._data: dict       = _load_yaml(roster_yaml)
    self._roster_yaml: str = roster_yaml

    self.cards: Dict[str, SourceCard]     = {}
    self.rarity_map: Dict[str, List[str]] = {}
    self.type_map: Dict[str, List[str]]   = {}
    self.series_map: Dict[str, List[str]] = {}
        
    for id, data in self._data.items():
      try:
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
  

  async def sync_db(self):
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
  

  def from_ids_as_dict(self, ids: List[str]):
    cards: List[dict] = []
    for id in ids:
      if id in self.cards.keys():
        cards.append(self.cards[id].asdict())

    return cards


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


gacha = Gachaman(
  settings_yaml=environ.get("GACHA_SETTINGS_YAML"),
  roster_yaml=environ.get("GACHA_ROSTER_YAML")
)


def reload():
  global gacha
  gacha = Gachaman(
    settings_yaml=environ.get("GACHA_SETTINGS_YAML"),
    roster_yaml=environ.get("GACHA_ROSTER_YAML")
  )