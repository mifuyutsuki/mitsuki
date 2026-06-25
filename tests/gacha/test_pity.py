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


async def test_fetch_pity(init_db, mock_user, card_rarities: list[gacha.CardRarity], gacha_user: gacha.GachaUser):
  pity_counters = await gacha.UserPity.fetch(mock_user.id)

  card_rarities_with_pity = [r for r in card_rarities if r.pity and r.pity > 1]
  assert len(pity_counters) == len(card_rarities_with_pity)

  for fetched in pity_counters:
    assert fetched.count == 0