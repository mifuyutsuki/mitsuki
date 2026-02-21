import pytest
import pytest_asyncio

import os
import asyncio
import random
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


@pytest.fixture()
async def card_rarities():
  rarities = [
    gacha.CardRarity(rarity=1, rate=0.615, dupe_shards=75, color=0, pity=None, emoji=None),
    gacha.CardRarity(rarity=2, rate=0.315, dupe_shards=120, color=0, pity=5, emoji=None),
    gacha.CardRarity(rarity=3, rate=0.055, dupe_shards=300, color=0, pity=25, emoji=None),
    gacha.CardRarity(rarity=4, rate=0.015, dupe_shards=600, color=0, pity=75, emoji=None),
  ]
  async with begin_session() as session:
    for rarity in rarities:
      await rarity.add(session)

  return rarities


@pytest.fixture()
def card_data():
  with open("exampleassets/gacha_roster.yaml", "r") as f:
    return yaml.safe_load(f)


@pytest.fixture()
async def cards(card_rarities: list[gacha.CardRarity], card_data: dict):
  cards = [
    gacha.Card(id=id, name=card["name"], rarity=card["rarity"], type=card["type"], series=card["series"])
    for id, card in card_data.items()
  ]
  async with begin_session() as session:
    for card in cards:
      await card.add(session)

  return cards


@pytest.fixture()
async def gacha_user(mock_user):
  async with begin_session() as session:
    return await gacha.GachaUser.daily(session, mock_user.id)
  

@pytest.fixture()
async def card_collection_empty(cards: list[gacha.Card]):
  collection = gacha.CardCollection(
    id="c00", name="Character: Mitsuki",
    rollable=True, discoverable=True, show_counts=True,
  )

  async with begin_session() as session:
    await collection.add(session)
  return collection


@pytest.fixture()
async def card_collection(cards: list[gacha.Card], card_collection_empty: gacha.CardCollection):
  collection       = card_collection_empty
  collection_cards = [card.id for card in cards if card.id.startswith("c00")]

  async with begin_session() as session:
    await collection.add_cards(session, collection_cards)
  return collection


@pytest.fixture()
async def card_season_ongoing(card_collection: gacha.CardCollection):
  now        = ipy.Timestamp.now()
  start_time = now - timedelta(days=1)
  end_time   = now + timedelta(days=56)
  season     = gacha.GachaSeason(
    id="2510.1", name="Season 1", collection=card_collection.id,
    pickup_rate=0.7, start_time=start_time.timestamp(), end_time=end_time.timestamp(),
  )

  async with begin_session() as session:
    await season.add(session)
  return season


@pytest.fixture()
async def card_season_ended(card_collection: gacha.CardCollection):
  now        = ipy.Timestamp.now()
  start_time = now - timedelta(days=60)
  end_time   = now - timedelta(days=56)
  season     = gacha.GachaSeason(
    id="2506.1", name="Season 0", collection=card_collection.id,
    pickup_rate=0.7, start_time=start_time.timestamp(), end_time=end_time.timestamp(),
  )

  async with begin_session() as session:
    await season.add(session)
  return season


@pytest.fixture()
async def card_rolls(cards: list[gacha.Card], gacha_user: gacha.GachaUser):
  rand = random.Random(33550306)
  random_time = lambda: (
    ipy.Timestamp.now() - timedelta(
      days=rand.randrange(1, 15), hours=rand.randrange(0, 23), minutes=rand.randrange(0, 59),
      seconds=rand.randrange(0, 59), microseconds=rand.randrange(0, 999)
    )
  )

  card_zero = await gacha.Card.fetch("c00.01.1", unobtained=True)
  assert card_zero is not None

  rolls = [card_zero.set_roll_time(random_time())]
  for _ in range(24):
    rolls.append(await gacha.CardCache.roll(now=random_time()))

  async with begin_session() as session:
    for roll in rolls:
      await roll.give_to(session, gacha_user.user, rolled=True)

  await gacha.CardCache.sync_search()
  return rolls