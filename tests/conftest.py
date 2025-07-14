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
def mock_message():
  class MockMessage:
    id = ipy.Snowflake(111100000000000000)
    timestamp = ipy.Timestamp.now()

    async def edit(self, *args, **kwargs):
      pass

  return MockMessage()


@pytest.fixture()
def mock_channel(mock_message):
  class MockChannel:
    id = 111000000000000000

    async def fetch_message(self, id, *args, **kwargs):
      pass

    async def send(self, *args, **kwargs):
      return mock_message

    def permissions_for(self, *args, **kwargs):
      return ipy.Permissions.ALL

  return MockChannel()


@pytest.fixture()
def mock_guild():
  class MockGuild:
    id = ipy.Snowflake(110000000000000000)
    name = "Student Council"

  return MockGuild()


@pytest.fixture()
def mock_user():
  class MockUser:
    id = ipy.Snowflake(100000000000000000)
    username = ".everyone"
    global_name = "Student Council President"
    # avatar = ipy.Asset(mock_bot, f"{ipy.Asset.BASE}/embed/avatars/0")

    def has_permission(self, *args):
      return True

  return MockUser()


@pytest.fixture()
def mock_bot(mock_guild, mock_user, mock_channel, monkeypatch):
  class MockApplication:
    team = None
  
  class MockClientUser:
    id = 1

  class MockClient:
    _members = {
      mock_guild.id: {
        mock_user.id: mock_user
      }
    }
    _channels = {
      mock_channel.id: mock_channel
    }

    guilds = [mock_guild]

    # Used by is_owner()
    owner_ids = [mock_user.id]
    app = MockApplication()
    user = MockClientUser()

    async def fetch_user(self, user_id):
      for users in self._members.values():
        if user_id in users:
          return users[user_id]
      return None

    async def fetch_member(self, user_id, guild_id):
      if users := self._members.get(guild_id):
        return users.get(user_id)
      return None

    async def fetch_channel(self, channel_id):
      return self._channels.get(channel_id)

  return MockClient()


@pytest.fixture()
async def mock_ctx(
  mock_bot: ipy.Client, mock_user: ipy.BaseUser, mock_guild: ipy.BaseGuild, mock_message: ipy.BaseMessage
):
  class MockInteractionContext:
    bot = mock_bot
    author = mock_user
    author_id = mock_user.id
    user = mock_user
    user_id = mock_user.id
    guild = mock_guild
    guild_id = mock_guild.id
    deferred = False
    responded = False

    async def defer(self, *args, suppress_error=False, **kwargs):
      if not suppress_error:
        assert not self.deferred
      self.deferred = True

    async def send(self, *args, **kwargs):
      self.responded = True
      return mock_message

  return MockInteractionContext()