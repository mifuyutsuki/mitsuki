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


@pytest_asyncio.fixture()
async def multiple_presences():
  names = ["Spice Market", "Daydream Cafe", "Connected Sky"]
  ps = [api.Presence.create(name) for name in names]

  async with new_session.begin() as session:
    for p in ps:
      await p.add(session)

  return ps


@pytest_asyncio.fixture()
def mock_presencer(mock_bot: ipy.Client):
  presencer.set_presencer(mock_bot, cycle_time=60)
  return presencer.presencer()


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


async def test_presencer_empty(init_db, mock_presencer: presencer.Presencer):
  pr = mock_presencer
  assert len(pr.presences) == 0

  await pr.init()
  assert len(pr.presences) == 0
  assert pr.current is None


async def test_presencer_single(init_db, mock_presencer: presencer.Presencer, single_presence: api.Presence):
  pr, p = mock_presencer, single_presence
  assert len(pr.presences) == 0

  await pr.init()
  assert len(pr.presences) == 1
  assert pr.current is not None
  assert pr.current.name == p.name

  current_0 = pr.current
  await pr.cycle()
  current_1 = pr.current

  assert current_1.name == current_0.name


async def test_presencer_multiple(init_db, mock_presencer: presencer.Presencer, multiple_presences: list[api.Presence]):
  pr, ps = mock_presencer, multiple_presences
  assert len(pr.presences) == 0

  await pr.init()
  assert len(pr.presences) == len(ps)
  assert pr.current is not None

  current_0 = pr.current
  await pr.cycle()
  current_1 = pr.current

  assert current_1.name != current_0.name