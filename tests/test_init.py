import pytest
import pytest_asyncio

import os

import sqlalchemy as sa
import interactions as ipy
import attrs

import mitsuki

from mitsuki import settings
from mitsuki.lib import userdata

# Required to load in schema definitions
from mitsuki.modules import gacha, schedule


async def test_db_empty_init():
  """For tests, an in-memory SQLite database is to be used."""

  async with userdata.new_session.begin() as session:
    assert await session.scalar(sa.text("SELECT COUNT(*) FROM sqlite_schema")) == 0


async def test_db_fresh_init():
  """Tables can be initialized from scratch."""

  async with userdata.new_session.begin() as session:
    assert await session.scalar(sa.text("SELECT COUNT(*) FROM sqlite_schema")) == 0

  await userdata.initialize()

  async with userdata.new_session.begin() as session:
    assert await session.scalar(sa.text("SELECT COUNT(*) FROM sqlite_schema")) > 0


def test_default_settings():
  """For tests, default settings are to be used."""

  assert settings.mitsuki.db_use == "sqlite"
  assert settings.mitsuki.db_path == "data/db.sqlite3"
  assert settings.mitsuki.db_pg_path == "localhost:5432/mitsuki"
  assert settings.mitsuki.daily_reset == "00:00+0000"

  assert settings.gacha.settings == "exampleassets/gacha_settings.yaml"
  assert settings.gacha.roster == "exampleassets/gacha_roster.yaml"

  for emoji in attrs.astuple(settings.emoji, recurse=False):
    assert isinstance(emoji, ipy.PartialEmoji)
    assert emoji.id is None


def test_default_env():
  """For tests, default environment variables (example.env) are to be used. Tokens must be blank."""

  assert os.environ.get("SETTINGS_YAML") == "defaults/settings.yaml"
  assert len(os.environ.get("BOT_TOKEN", "")) == 0
  assert len(os.environ.get("DEV_BOT_TOKEN", "")) == 0
  assert len(os.environ.get("SENTRY_DSN", "")) == 0