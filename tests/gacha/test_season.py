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