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


async def test_roll_give(init_db, mock_user, cards: list[gacha.Card]):
  card_ids = [card.id for card in cards]

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) == 0

  rolled = await gacha.CardCache.roll()
  assert rolled.id in card_ids

  async with begin_session() as session:
    await rolled.give_to(session, mock_user.id, rolled=True)

  rolls = await gacha.Card.fetch_all(unobtained=False)
  assert len(rolls) > 0


async def test_user_card(init_db, mock_user, cards: list[gacha.Card]):
  rolled = await gacha.CardCache.roll()
  user_card = await gacha.UserCard.fetch(rolled.id, mock_user.id)
  assert user_card is None

  async with begin_session() as session:
    await rolled.give_to(session, mock_user.id, rolled=True)

  user_card = await gacha.UserCard.fetch(rolled.id, mock_user.id)
  assert user_card is not None
  assert user_card.count == user_card.rolled_count == 1
  assert user_card.first_rolled == user_card.last_rolled