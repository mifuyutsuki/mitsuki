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


async def test_collection_create(init_db, card_collection_empty: gacha.CardCollection):
  created = card_collection_empty
  fetched = await gacha.CardCollection.fetch(card_collection_empty.id)

  assert created == fetched


async def test_collection_add_by_regex(init_db, card_collection_empty: gacha.CardCollection):
  expect = await gacha.Card.grep_id_count(r"c00\..*")

  async with begin_session() as session:
    await card_collection_empty.add_cards_by_grep_id(session, r"c00\..*")

  fetched = await gacha.Card.fetch_all_collection(card_collection_empty.id)
  assert expect == len(fetched)


async def test_collection_add_by_regex_multiple(init_db, card_collection_empty: gacha.CardCollection):
  patterns = [r"c00\..*", r"e2308\..*"]
  expect   = await gacha.Card.grep_id_count(patterns)

  async with begin_session() as session:
    await card_collection_empty.add_cards_by_grep_id(session, patterns)

  fetched = await gacha.Card.fetch_all_collection(card_collection_empty.id)
  assert expect == len(fetched)