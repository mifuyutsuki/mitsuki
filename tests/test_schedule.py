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
from mitsuki.modules import gacha, schedule

from mitsuki.modules.schedule import userdata, schema
from mitsuki.modules.schedule.daemon import Daemon, DaemonTask

# TODO: Move these tests to tests/schedule/

TEST_DATETIME = datetime(year=2024, month=2, day=14, hour=0, minute=0, second=0, microsecond=0)


@pytest.fixture()
def mock_schedule(mock_ctx: ipy.BaseContext):
  return userdata.Schedule.create(mock_ctx, "Test Schedule", type=userdata.ScheduleTypes.QUEUE)


@pytest_asyncio.fixture()
async def db_created_schedule(mock_ctx: ipy.BaseContext, mock_schedule: userdata.Schedule):
  async with new_session.begin() as session:
    await mock_schedule.add(session)

  async with new_session.begin() as session:
    return await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule")


@pytest_asyncio.fixture(params=[
  None,
  (TEST_DATETIME).timestamp(),
  (TEST_DATETIME - timedelta(hours=12)).timestamp(),
  (TEST_DATETIME - timedelta(days=1)).timestamp(),
])
async def db_active_schedule(
  mock_ctx: ipy.BaseContext, mock_channel: ipy.BaseChannel, db_created_schedule: userdata.Schedule,
  request: pytest.FixtureRequest
):
  schedule = db_created_schedule
  schedule.post_channel = mock_channel.id
  schedule.pin = False
  schedule.discoverable = True

  schedule.active = True
  schedule.last_fire = request.param

  text = "Which anime school uniform is your favorite?"
  tags = "anime education fashion"

  message = schedule.create_message(mock_ctx.author.id, text)
  message.set_tags(tags)

  async with new_session.begin() as session:
    await message.add(session)
    await schedule.update(session)

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
  assert not schedule.pin
  assert not schedule.discoverable
  assert schedule.date_created == schedule.date_modified
  assert schedule.last_fire is None


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


async def test_schedule_not_ready(init_db, mock_ctx: ipy.BaseContext, db_created_schedule: userdata.Schedule):
  schedule = db_created_schedule
  assert not await schedule.is_valid(mock_ctx.bot)


async def test_schedule_ready(init_db, mock_ctx: ipy.BaseContext, db_active_schedule: userdata.Schedule):
  schedule = db_active_schedule
  assert await schedule.is_valid(mock_ctx.bot)


async def test_message_create(init_db, mock_ctx: ipy.BaseContext, db_created_schedule: userdata.Schedule):
  statement = sa.select(sa.func.count()).select_from(schema.Message)
  async with new_session.begin() as session:
    assert await session.scalar(statement) == 0

  schedule = db_created_schedule

  text = "Which anime school uniform is your favorite?"
  tags = "anime education fashion"

  message = schedule.create_message(mock_ctx.author.id, text)
  message.set_tags(tags)

  async with new_session.begin() as session:
    await message.add(session)

  messages = await userdata.Message.fetch_by_schedule(mock_ctx.guild.id, "Test Schedule")
  assert len(messages) == 1

  message = messages[0]
  assert message.message == text
  assert message.tags == tags
  assert message.date_created == message.date_modified


@pytest.mark.parametrize("post_time", [
  TEST_DATETIME,
  TEST_DATETIME + timedelta(seconds=1),
  TEST_DATETIME - timedelta(seconds=1),
])
async def test_daemon_post_time(
  init_db, mock_channel: ipy.BaseChannel, mock_ctx: ipy.BaseContext, db_active_schedule: userdata.Schedule,
  post_time: datetime
):
  """
  Messages can be posted, and the next post time advances correctly.

  Ensure that the Schedule Daemon does not double-fire, similar to this library issue:
  https://github.com/interactions-py/interactions.py/issues/1717
  """

  schedule = db_active_schedule

  messages = await userdata.Message.fetch_by_schedule(mock_ctx.guild.id, "Test Schedule")
  message = messages[0]
  assert message.date_posted is None
  assert message.message_id is None

  await DaemonTask.post(mock_ctx.bot, schedule, force=True, time=post_time.timestamp())

  schedule = await userdata.Schedule.fetch(mock_ctx.guild.id, "Test Schedule")
  assert schedule.last_fire is not None
  assert schedule.cron(start_time=schedule.last_fire).next(float) > TEST_DATETIME.timestamp()

  messages = await userdata.Message.fetch_by_schedule(mock_ctx.guild.id, schedule.title)
  message = messages[0]
  assert message.date_posted is not None
  assert message.message_id is not None