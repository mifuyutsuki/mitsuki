import pytest
import pytest_asyncio
import dotenv

# Ensure that the test .env is loaded before importing `mitsuki`
dotenv.load_dotenv("example.env", override=True)

import interactions as ipy
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
  create_async_engine,
  async_sessionmaker,
)

import mitsuki

from mitsuki import settings, modules
from mitsuki.lib.userdata import begin_session, db_migrate, db_init

# Required to load in schema definitions
from mitsuki.modules import schedule, system
from mitsuki.models import gacha


class MockMessage:
  id = ipy.Snowflake(111100000000000000)
  timestamp = ipy.Timestamp.now()

  async def edit(self, *args, **kwargs):
    pass

class MockChannel:
  id = 111000000000000000
  _message: MockMessage = None
  client: "MockClient" = None

  def __init__(self, message=None):
    self._message = message or MockMessage()

  async def fetch_message(self, id, *args, **kwargs):
    pass

  async def send(self, *args, **kwargs):
    return self._message

  def permissions_for(self, *args, **kwargs):
    return ipy.Permissions.ALL

class MockGuild:
  id = ipy.Snowflake(110000000000000000)
  name = "Student Council"

class MockUser:
  id = ipy.Snowflake(100000000000000000)
  username = ".everyone"
  global_name = "Student Council President"
  # avatar = ipy.Asset(mock_bot, f"{ipy.Asset.BASE}/embed/avatars/0")

  def has_permission(self, *args):
    return True

class MockApplication:
  team = None

class MockClientUser:
  id = 1

class MockClient:
  activity = None
  status = None

  app = MockApplication()
  user = MockClientUser()
  _channel = MockChannel()
  _owner = MockUser()

  def __init__(self):
    self.owner_ids = [self._owner.id]
    self.guilds = [MockGuild()]
    self._channels = {self._channel.id: self._channel}
    self._members = {
      self.guilds[0].id: {
        self._owner.id: self._owner
      }
    }

  async def change_presence(self, status, activity):
    self.status = status
    self.activity = activity

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

class MockInteractionContext:
  deferred = False
  responded = False

  def __init__(self):
    self.bot = MockClient()
    self.author = MockUser()
    self.author_id = self.author.id
    self.user = self.author
    self.user_id = self.author_id
    self.guild = MockGuild()
    self.guild_id = self.guild.id

  async def defer(self, *args, suppress_error=False, **kwargs):
    if not suppress_error:
      assert not self.deferred
    self.deferred = True

  async def send(self, *args, **kwargs):
    self.responded = True
    return MockMessage()

@pytest.fixture(autouse=True)
def init_empty():
  db_init("sqlite:///:memory:")


@pytest_asyncio.fixture()
async def init_db(init_empty):
  await db_migrate()


@pytest.fixture()
def mock_message():
  return MockMessage()


@pytest.fixture()
def mock_channel(mock_message):
  return MockChannel(message=mock_message)


@pytest.fixture()
def mock_guild():
  return MockGuild()


@pytest.fixture()
def mock_user():
  return MockUser()


@pytest.fixture()
def mock_bot(mock_guild, mock_user, mock_channel, monkeypatch):
  return MockClient()


@pytest.fixture()
async def mock_ctx(
  mock_bot: ipy.Client, mock_user: ipy.BaseUser, mock_guild: ipy.BaseGuild, mock_message: ipy.BaseMessage, monkeypatch
):
  async def message_send_override(self, *args, **kwargs):
    return mock_message
  monkeypatch.setattr("mitsuki.lib.view.core.StaticView.send", message_send_override)
  monkeypatch.setattr("mitsuki.lib.view.core.View.send", message_send_override)

  return MockInteractionContext()