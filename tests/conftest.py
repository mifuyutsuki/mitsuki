import pytest
import pytest_asyncio
import dotenv

import interactions as ipy
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
  create_async_engine,
  async_sessionmaker,
)

import mitsuki

from mitsuki import settings, modules
from mitsuki.lib.userdata import new_session, initialize


@pytest.fixture(autouse=True)
def init_empty(monkeypatch):
  dotenv.load_dotenv("example.env", override=True)

  test_settings = settings.BaseSettings.create("defaults/settings.yaml")
  test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
  # test_session = async_sessionmaker(test_engine, expire_on_commit=False)
  new_session.configure(bind=test_engine)

  monkeypatch.setattr(mitsuki.lib.userdata, "engine", test_engine)
  monkeypatch.setattr(mitsuki.settings, "settings", test_settings)
  # monkeypatch.setattr(mitsuki.lib.userdata, "new_session", test_session)

  settings.load_settings("defaults/settings.yaml")


@pytest_asyncio.fixture()
async def init_db(init_empty):
  await initialize()


@pytest.fixture()
def mock_guild():
  class MockGuild:
    id = 110000000000000000
    name = "Student Council"

  return MockGuild()


@pytest.fixture()
def mock_user():
  class MockUser:
    id = 100000000000000000
    username = ".everyone"
    global_name = "Student Council President"
    # avatar = ipy.Asset(mock_bot, f"{ipy.Asset.BASE}/embed/avatars/0")

  return MockUser()


@pytest.fixture()
def mock_bot(mock_guild, mock_user):
  class MockClient(ipy.Client):
    guilds = [mock_guild]

  return MockClient()


@pytest.fixture()
async def mock_ctx(mock_bot: ipy.Client, mock_user: ipy.BaseUser, mock_guild: ipy.BaseGuild):
  class MockInteractionContext:
    bot = mock_bot
    author = mock_user
    author_id = ipy.Snowflake(100000000000000000)
    user = mock_user
    user_id = ipy.Snowflake(100000000000000000)
    guild = mock_guild
    guild_id = ipy.Snowflake(110000000000000000)

  return MockInteractionContext()