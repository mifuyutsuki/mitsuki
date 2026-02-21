import pytest
import pytest_asyncio

import os
import asyncio
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
import interactions as ipy
import attrs
import yaml

import mitsuki

from mitsuki import settings, utils
from mitsuki.lib import checks
from mitsuki.lib.userdata import begin_session

from mitsuki.core import gacha


async def test_season_create(init_db, card_season_ongoing: gacha.GachaSeason):
  created = card_season_ongoing
  fetched = await gacha.GachaSeason.fetch(created.id)

  assert fetched == created


async def test_fetch_current_ongoing(init_db, card_season_ongoing: gacha.GachaSeason):
  season = await gacha.GachaSeason.fetch_current()

  assert season == card_season_ongoing


async def test_fetch_current_ended(init_db, card_season_ended: gacha.GachaSeason):
  season = await gacha.GachaSeason.fetch_current()

  assert season is None


async def test_fetch_table_season(
  init_db, cards: list[gacha.Card], card_season_ongoing: gacha.GachaSeason
):
  season = await gacha.GachaSeason.fetch_current()

  standard = await gacha.Card.fetch_table_standard(season.id)
  seasonal = await gacha.Card.fetch_table_season(season.id)

  standard_count = sum([len(rarity_cards) for rarity_cards in standard.values()])
  seasonal_count = sum([len(rarity_cards) for rarity_cards in seasonal.values()])

  standard_cards = set(sum(standard.values(), []))
  seasonal_cards = set(sum(seasonal.values(), []))

  assert standard_count + seasonal_count == len(cards)
  assert standard_count > 0 and seasonal_count > 0
  assert standard_cards.isdisjoint(seasonal_cards)

  assert not any([card.startswith("c00") for card in standard_cards])
  assert all([card.startswith("c00") for card in seasonal_cards])