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


async def test_roll(init_db, cards: list[gacha.Card]):
  card_ids = [card.id for card in cards]

  rolled = await gacha.CardCache.roll()
  assert rolled.id in card_ids
  assert rolled.roll_time is not None


async def test_roll_give(init_db, mock_user, cards: list[gacha.Card], gacha_user: gacha.GachaUser):
  card_ids = [card.id for card in cards]

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) == 0

  rolled = await gacha.CardCache.roll()
  assert rolled.id in card_ids
  assert rolled.roll_time is not None

  async with begin_session() as session:
    await rolled.give_to(session, gacha_user.user, rolled=True)

  assert rolled.held_count == 1
  assert rolled.is_new_roll
  assert rolled.roll_pity is not None and rolled.roll_pity > 0

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) > 0


async def test_roll_give_duplicate(init_db, mock_user, cards: list[gacha.Card], gacha_user: gacha.GachaUser):
  card_ids = [card.id for card in cards]

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) == 0

  rolled = await gacha.CardCache.roll()
  assert rolled.id in card_ids
  assert rolled.roll_time is not None

  async with begin_session() as session:
    await rolled.give_to(session, gacha_user.user, rolled=True)
    await rolled.give_to(session, gacha_user.user, rolled=True)

  assert rolled.held_count == 2
  assert not rolled.is_new_roll
  assert rolled.roll_pity is not None and rolled.roll_pity > 0

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) > 0