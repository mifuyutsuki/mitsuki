import pytest
import pytest_asyncio
import dotenv

from sqlalchemy.ext.asyncio import (
  create_async_engine,
  async_sessionmaker,
)

import mitsuki

from mitsuki import settings
from mitsuki.lib.userdata import new_session


@pytest.fixture(autouse=True)
def init(monkeypatch):
  dotenv.load_dotenv("example.env", override=True)

  test_settings = settings.BaseSettings.create("defaults/settings.yaml")
  test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
  # test_session = async_sessionmaker(test_engine, expire_on_commit=False)
  new_session.configure(bind=test_engine)

  monkeypatch.setattr(mitsuki.lib.userdata, "engine", test_engine)
  monkeypatch.setattr(mitsuki.settings, "settings", test_settings)
  # monkeypatch.setattr(mitsuki.lib.userdata, "new_session", test_session)

  settings.load_settings("defaults/settings.yaml")