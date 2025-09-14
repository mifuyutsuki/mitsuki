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

from mitsuki.core.settings import get_setting, set_setting, Settings
from mitsuki.core import gacha

TEST_DATETIME = ipy.Timestamp(
  year=2024, month=2, day=14, hour=0, minute=15, second=0, microsecond=0, tzinfo=timezone.utc
)
"""Reference time for tests, corresponding to 14 Feb 2024 00:15:00."""

# TEST_DATETIME_ALT = ipy.Timestamp(year=2024, month=2, day=14, hour=4, minute=15, second=0, microsecond=0)
# """Alternative reference time for tests, corresponding to 14 Feb 2024 00:15:00."""


@pytest.fixture(params=[
  "00:00",
  "04:00",
  "21:00",
])
async def custom_daily_reset(request: pytest.FixtureRequest):
  async with begin_session() as session:
    await set_setting(session, Settings.DailyResetTime, request.param)

  daily_reset_s = await get_setting(Settings.DailyResetTime)
  h, m = daily_reset_s.split(":")
  return TEST_DATETIME.replace(hour=int(h), minute=int(m))


@pytest.fixture()
async def gacha_user_custom_reset(mock_user, custom_daily_reset: ipy.Timestamp):
  # Similar to gacha_user, but the daily reset is parametrized
  # Set to be daily reset - 1h
  async with begin_session() as session:
    return await gacha.GachaUser.daily(session, mock_user.id, now=custom_daily_reset - timedelta(hours=1))


async def test_fetch_user(init_db, mock_user, gacha_user: gacha.GachaUser):
  created = gacha_user
  fetched = await gacha.GachaUser.fetch(mock_user.id)

  assert fetched is not None
  assert fetched.user == created.user
  assert fetched.first_daily == fetched.last_daily
  assert fetched.amount > 0

  # Note: The gacha_user fixture instance is created using GachaUser.daily(),
  # and thus includes daily claim information.
  assert created.claimed_first_daily
  assert created.claimed_daily


async def test_fetch_profile(init_db, mock_user, card_rolls: list[gacha.Card], gacha_user: gacha.GachaUser):
  created = gacha_user
  fetched = await gacha.GachaUser.fetch_profile(mock_user.id)

  assert fetched is not None
  assert fetched.user == created.user
  assert fetched.first_daily == fetched.last_daily
  assert fetched.amount > 0

  assert len(fetched.pity_counters) > 0
  assert len(fetched.rolled_cards) > 0
  assert len(fetched.recent_rolls) > 0

  # Note: The gacha_user fixture instance is created using GachaUser.daily(),
  # and thus includes daily claim information.
  assert created.claimed_first_daily
  assert created.claimed_daily


async def test_daily_unclaimed(
  init_db, mock_user, custom_daily_reset: ipy.Timestamp, gacha_user_custom_reset: gacha.GachaUser
):
  # last user daily < last reset < "current" time

  # Daily reset | Last daily | "Current" time
  # 14/2 00:00  | 13/2 23:00 | 14/2 06:00
  # 14/2 04:00  | 14/2 03:00 | 14/2 10:00
  # 14/2 21:00  | 14/2 20:00 | 15/2 03:00

  now = custom_daily_reset + timedelta(hours=1)

  user_before = gacha_user_custom_reset
  async with begin_session() as session:
    user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

  assert user_after.amount > user_before.amount
  assert user_after.claimed_daily
  assert not user_after.claimed_first_daily


async def test_daily_claimed(
  init_db, mock_user, custom_daily_reset: ipy.Timestamp, gacha_user_custom_reset: gacha.GachaUser
):
  # last user daily < "current" time < last reset

  # Daily reset | Last daily | "Current" time
  # 14/2 00:00  | 13/2 23:00 | 13/2 23:30
  # 14/2 04:00  | 14/2 03:00 | 14/2 03:30
  # 14/2 21:00  | 14/2 20:00 | 14/2 20:30

  now = custom_daily_reset - timedelta(minutes=30)

  user_before = gacha_user_custom_reset
  async with begin_session() as session:
    user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

  assert user_after.amount == user_before.amount
  assert not user_after.claimed_daily
  assert not user_after.claimed_first_daily


async def test_daily_burst(
  init_db, mock_user, custom_daily_reset: ipy.Timestamp, gacha_user_custom_reset: gacha.GachaUser
):
  # last reset < current time (now - 1d) < last user daily (now)
  user_before = await gacha.GachaUser.fetch(mock_user.id)
  assert user_before is not None

  # First call
  now = custom_daily_reset + timedelta(days=1, minutes=1)
  async with begin_session() as session:
    user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

  assert user_after.amount > user_before.amount
  assert user_after.claimed_daily
  assert not user_after.claimed_first_daily

  # Subsequent calls
  for s in range(5):
    user_before = user_after

    now += timedelta(seconds=s)
    async with begin_session() as session:
      user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

    assert user_after.amount == user_before.amount
    assert not user_after.claimed_daily
    assert not user_after.claimed_first_daily