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
from typing import Dict, List, Optional
from random import Random

from ..common import get_config


class Gachaman:
  def __init__(self, settings_yaml: str, roster_yaml: str):
    self.settings = Settings(settings_yaml=settings_yaml)
    self.roster   = Roster(roster_yaml=roster_yaml)
    self.random   = None

    self.refresh_random()
  

  def roll(self, min_rarity: Optional[int] = None):
    rates = self.settings.rates
    roll  = self.random.random
    pick  = self.random.choice

    rarity_get = min_rarity if min_rarity else 1
    arona      = roll()
    for rarity in sorted(rates.keys()):
      if rarity < rarity_get:
        continue
      if arona < rates[rarity]:
        rarity_get = rarity
      else:
        break

    available_picks = []
    while len(available_picks) == 0 and rarity_get > 0:
      available_picks = self.roster.rarity_map[rarity_get]
      rarity_get -= 1

    picked = pick(available_picks)
    return self.roster.cards[picked]


  def refresh_random(self):
    seeder      = Random()
    seed        = seeder.randint(0, 2**63)
    self.random = Random(seed)


# =================================================================
  

class Settings:
  def __init__(self, settings_yaml: str):
    self._data: dict    = _load_yaml(settings_yaml)

    self.cost: int                   = self._data.get("cost")
    self.currency_icon: str          = self._data.get("currency_icon")
    self.currency_name: str          = self._data.get("currency_name")
    self.currency: str               = f"{self.currency_icon} {self.currency_name}"
    self.daily_shards: int           = self._data.get("daily_shards")
    self.daily_tz: int               = self._data.get("daily_tz")

    self.rates: Dict[int, float]     = self._load_rates()
    self.pity: Dict[int, int]        = self._load_pity()
    self.dupe_shards: Dict[int, int] = self._load_dupe_shards()
    self.colors: Dict[int, int]      = self._load_colors()
    self.stars: Dict[int, str]       = self._load_stars()

    self.rarities: List[int]         = sorted(self.rates.keys(), reverse=True)
    

  # =================================================================
  # Internal helpers


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
    

class Card:
  def __init__(
    self,
    id: str,
    name: str,
    rarity: int,
    type: str,
    series: str,
    image: Optional[str]
  ):
    self.id: str              = id
    self.name: str            = name
    self.rarity: int          = rarity
    self.type: str            = type
    self.series: str          = series
    self.image: Optional[str] = image
  
  def asdict(self):
    return dict(
      id=self.id,
      name=self.name,
      rarity=self.rarity,
      type=self.type,
      series=self.series,
      image=self.image
    )


class Roster:
  def __init__(self, roster_yaml: str):
    self._data: dict  = _load_yaml(roster_yaml)

    self.cards: Dict[str, Card]           = {}
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
      self.cards[id] = Card(id, name, rarity, type, series, image)
      
      if rarity not in self.rarity_map.keys():
        self.rarity_map[rarity] = []
      self.rarity_map[rarity].append(id)

      if type not in self.type_map.keys():
        self.type_map[type] = []
      self.type_map[type].append(id)

      if series not in self.series_map.keys():
        self.series_map[series] = []
      self.series_map[series].append(id)
  
  def from_id(self, id: str):
    return self.cards.get(id)
  
  def from_ids(self, ids: List[str]):
    cards: List[Card] = []
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


# =================================================================


gacha = Gachaman(
  settings_yaml=get_config("GACHA_SETTINGS_YAML"),
  roster_yaml=get_config("GACHA_ROSTER_YAML")
)
