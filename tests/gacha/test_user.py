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


async def test_fetch_profile(init_db, mock_user, gacha_user: gacha.GachaUser):
  created = gacha_user
  fetched = await gacha.GachaUser.fetch_profile(mock_user.id)

  assert fetched is not None
  assert fetched.user == created.user
  assert fetched.first_daily == fetched.last_daily
  assert fetched.amount > 0

  # Note: The gacha_user fixture instance is created using GachaUser.daily(),
  # and thus includes daily claim information.
  assert created.claimed_first_daily
  assert created.claimed_daily


async def test_daily_unclaimed(init_db, mock_user, gacha_user: gacha.GachaUser):
  # last user daily (now) < last reset < current time (now + 1d)
  now = ipy.Timestamp.now() + timedelta(days=1)

  user_before = gacha_user
  async with begin_session() as session:
    user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

  assert user_after.amount > user_before.amount
  assert user_after.claimed_daily
  assert not user_after.claimed_first_daily


async def test_daily_claimed(init_db, mock_user, gacha_user: gacha.GachaUser):
  # last reset < current time (now - 1d) < last user daily (now)
  now = ipy.Timestamp.now() - timedelta(days=1)

  user_before = gacha_user
  async with begin_session() as session:
    user_after = await gacha.GachaUser.daily(session, mock_user.id, now=now)

  assert user_after.amount == user_before.amount
  assert not user_after.claimed_daily
  assert not user_after.claimed_first_daily


async def test_daily_burst(init_db, mock_user, gacha_user: gacha.GachaUser):
  # last reset < current time (now - 1d) < last user daily (now)
  user_before = await gacha.GachaUser.fetch(mock_user.id)
  assert user_before is not None

  # First call
  now = ipy.Timestamp.now() + timedelta(days=1, minutes=1)
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