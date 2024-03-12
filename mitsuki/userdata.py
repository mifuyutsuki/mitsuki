# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy.orm import DeclarativeBase
# from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import (
  create_async_engine,
  async_sessionmaker,
  AsyncAttrs,
)
from os import environ
from urllib.parse import quote_plus
from mitsuki import settings

__all__ = (
  "Base",
  "engine",
  "initialize",
  "new_session",
)

# TODO: postgresql support

if environ.get("ENABLE_DEV_MODE") == "1":
  USERDATA_PATH = settings.dev.db_path
else:
  USERDATA_PATH = settings.mitsuki.db_path

if settings.mitsuki.db_use == "sqlite":
  engine = create_async_engine(f"sqlite+aiosqlite:///{USERDATA_PATH}")
elif settings.mitsuki.db_use == "postgresql":
  raise SystemExit("PostgreSQL support is coming in a future version.")
  # username = environ.get("DB_USERNAME")
  # password = quote_plus(environ.get("DB_PASSWORD"))
  # host_db  = settings.mitsuki.db_path
  # engine = create_async_engine(
  #   f"postgresql+asyncpg://{username}:{password}@{host_db}"
  # )
else:
  raise SystemExit(
    f"Database '{settings.mitsuki.db_use}' not recognized or supported"
  )

  
new_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase, AsyncAttrs):
  def asdict(self):
    #: Source: https://stackoverflow.com/a/1960546
    return {c.name: getattr(self, c.name) for c in self.__table__.columns}

async def initialize():
  global engine
  async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

    if "sqlite" in engine.url.drivername:
      await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
