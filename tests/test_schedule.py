import pytest
import pytest_asyncio

import os
import asyncio

import sqlalchemy as sa
import interactions as ipy
import attrs

import mitsuki

from mitsuki import settings
from mitsuki.lib.userdata import new_session

# Required to load in schema definitions
from mitsuki.modules import gacha, schedule

from mitsuki.modules.schedule import userdata, schema
from mitsuki.modules.schedule.daemon import Daemon, DaemonTask


@pytest.fixture()
def mock_schedule(mock_ctx: ipy.BaseContext):
  return userdata.Schedule.create(mock_ctx, "Test Schedule", type=userdata.ScheduleTypes.QUEUE)


@pytest_asyncio.fixture()
async def db_created_schedule(mock_ctx: ipy.BaseContext, mock_schedule: userdata.Schedule):
  async with new_session.begin() as session:
    await mock_schedule.add(session)

  async with new_session.begin() as session:
    return await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule")


async def test_schedule_create(init_db, mock_ctx: ipy.BaseContext, mock_schedule: userdata.Schedule):
  statement = sa.select(sa.func.count()).select_from(schema.Schedule)
  async with new_session.begin() as session:
    assert await session.scalar(statement) == 0

  schedule = mock_schedule
  async with new_session.begin() as session:
    await schedule.add(session)

  schedule = await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule")
  assert schedule.id is not None
  assert schedule.title == "Test Schedule"
  assert schedule.type == userdata.ScheduleTypes.QUEUE
  assert schedule.date_created == schedule.date_modified


async def test_schedule_modify(init_db, mock_ctx: ipy.BaseContext, db_created_schedule: userdata.Schedule):
  schedule = db_created_schedule
  assert schedule.date_created == schedule.date_modified

  schedule.title = "Test Schedule 2"
  schedule.discoverable = True
  await asyncio.sleep(0.1)

  async with new_session.begin() as session:
    await schedule.update_modify(session, mock_ctx.author.id)

  schedule = await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule")
  assert schedule is None

  schedule = await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule 2")
  assert schedule is not None
  assert schedule.discoverable
  assert schedule.date_created < schedule.date_modified