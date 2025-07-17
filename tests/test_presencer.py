import pytest
import pytest_asyncio

import os
import asyncio
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
import interactions as ipy
import attrs

import mitsuki

from mitsuki import settings, utils
from mitsuki.lib import checks
from mitsuki.lib.userdata import new_session

# Required to load in schema definitions
from mitsuki.modules import gacha, schedule, system

from mitsuki.modules.system import presencer, api


@pytest_asyncio.fixture()
async def single_presence():
  p = api.Presence.create("Spice Market")
  async with new_session.begin() as session:
    await p.add(session)
  return p


async def test_presence_add(init_db):
  ps = await api.Presence.fetch_all()
  assert len(ps) == 0

  p = api.Presence.create("Spice Market")
  assert p.id is None

  async with new_session.begin() as session:
    await p.add(session)

  # Presence.add() modifies id upon db add
  assert p.id is not None

  ps = await api.Presence.fetch_all()
  assert len(ps) == 1

  p_fetch = ps[0]
  assert p_fetch.id is not None
  assert p_fetch.id == p.id
  assert p_fetch.name == p.name


async def test_presence_delete(init_db, single_presence: api.Presence):
  p = single_presence
  assert p.id is not None

  async with new_session.begin() as session:
    await p.delete(session)

  assert p.id is None

  ps = await api.Presence.fetch_all()
  assert len(ps) == 0


async def test_presence_delete_id(init_db, single_presence: api.Presence):
  p = single_presence

  async with new_session.begin() as session:
    p_deleted = await api.Presence.delete_id(session, p.id)

  assert p_deleted.id is None
  assert p_deleted.name == p.name

  ps = await api.Presence.fetch_all()
  assert len(ps) == 0