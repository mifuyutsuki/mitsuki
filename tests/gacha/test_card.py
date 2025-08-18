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


async def test_rarities(init_db, card_rarities: list[gacha.CardRarity]):
  created = card_rarities
  fetched = await gacha.CardRarity.fetch_all()

  assert len(fetched) == len(created)


async def test_create(init_db, cards: list[gacha.Card]):
  created = cards
  fetched = await gacha.Card.fetch_all(unobtained=True, private=True)

  assert len(fetched) == len(created)


async def test_fetch_no_roll(init_db, cards: list[gacha.Card]):
  fetched = await gacha.Card.fetch_all()

  assert len(fetched) == 0


async def test_roll(init_db, cards: list[gacha.Card]):
  card_ids = [card.id for card in cards]

  rolled = await gacha.CardCache.roll()

  assert rolled.id in card_ids