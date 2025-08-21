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
from mitsuki.core.submitter import CardSubmitter, CardSubmitterErrors


async def test_card_submitter_create(init_db, card_rarities: list[gacha.CardRarity], card_data: dict):
  submitter = await CardSubmitter.from_rosc2y_yaml(card_data)

  assert submitter.add_count == len(card_data)
  assert submitter.edit_count == 0
  assert submitter.delist_count == 0
  assert submitter.original_count == 0
  assert sum(submitter.error_counts.values()) == 0


async def test_card_submitter_create_missing_rarity(init_db, card_data: dict):
  submitter = await CardSubmitter.from_rosc2y_yaml(card_data)

  assert submitter.add_count == 0
  assert submitter.edit_count == 0
  assert submitter.delist_count == 0
  assert submitter.original_count == 0
  assert submitter.error_counts[CardSubmitterErrors.RARITY] == len(card_data)


async def test_card_submitter_fetch(init_db, card_rarities: list[gacha.CardRarity], card_data: dict):
  created = await CardSubmitter.from_rosc2y_yaml(card_data)
  fetched = await CardSubmitter.fetch(created.id)

  assert fetched == created


async def test_roster_add(init_db, cards: list[gacha.Card], card_data: dict):
  other_card_data = {
    "c00.00.1": {"name": "Mitsuki", "rarity": 1, "type": "Character", "series": "Mitsuki"}
  }
  submitter = await CardSubmitter.from_rosc2y_yaml(card_data | other_card_data)
  assert submitter.add_count == len(other_card_data)
  assert submitter.edit_count == 0
  assert submitter.delist_count == 0
  assert submitter.original_count == len(cards)
  assert sum(submitter.error_counts.values()) == 0

  # -----

  fetched_submitter = await CardSubmitter.fetch(submitter.id)
  assert fetched_submitter == submitter

  async with begin_session() as session:
    await fetched_submitter.execute(session)

  # -----

  new_cards = await gacha.Card.fetch_all(unobtained=True, private=False)
  assert len(new_cards) == len(cards) + len(other_card_data)


async def test_roster_edit(init_db, cards: list[gacha.Card], card_data: dict):
  edited_card_data = {}
  for id, entry in card_data.items():
    if entry["type"] == "Character":
      entry["name"] = entry["name"] + " (Swimsuit ver.)"
      edited_card_data[id] = entry

  submitter = await CardSubmitter.from_rosc2y_yaml(card_data | edited_card_data)

  assert submitter.add_count == 0
  assert submitter.edit_count == len(edited_card_data)
  assert submitter.delist_count == 0
  assert submitter.original_count == len(cards)
  assert sum(submitter.error_counts.values()) == 0

  # -----

  fetched_submitter = await CardSubmitter.fetch(submitter.id)
  assert fetched_submitter == submitter

  async with begin_session() as session:
    await fetched_submitter.execute(session)

  # -----

  new_cards = await gacha.Card.fetch_all(unobtained=True, private=False)
  assert len(new_cards) == len(cards)


async def test_roster_overwrite(init_db, cards: list[gacha.Card], card_data: dict):
  other_card_data = {
    "c00.00.1": {"name": "Mitsuki", "rarity": 1, "type": "Character", "series": "Mitsuki"}
  }
  submitter = await CardSubmitter.from_rosc2y_yaml(other_card_data)

  assert submitter.add_count == len(other_card_data)
  assert submitter.edit_count == 0
  assert submitter.delist_count == len(cards)
  assert submitter.original_count == len(cards)
  assert sum(submitter.error_counts.values()) == 0

  # -----

  fetched_submitter = await CardSubmitter.fetch(submitter.id)
  assert fetched_submitter == submitter

  async with begin_session() as session:
    await fetched_submitter.execute(session)

  # -----

  new_cards = await gacha.Card.fetch_all(unobtained=True, private=False)
  assert len(new_cards) == len(other_card_data)