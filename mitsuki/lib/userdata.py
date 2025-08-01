# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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
from attrs import asdict as _asdict
from os import environ
from urllib.parse import quote_plus
from typing import Optional
from mitsuki import settings

__all__ = (
  "Base",
  "AsDict",
  "engine",
  "initialize",
  "new_session",
  "begin_session",
)

_dev_mode = environ.get("ENABLE_DEV_MODE") == "1"

if settings.mitsuki.db_use == "sqlite":
  host_db = settings.dev.db_path if _dev_mode else settings.mitsuki.db_path
  engine = create_async_engine(f"sqlite+aiosqlite:///{host_db}")

elif settings.mitsuki.db_use == "postgresql":
  host_db = settings.dev.db_pg_path if _dev_mode else settings.mitsuki.db_pg_path
  username = environ.get("DB_USERNAME")
  password = quote_plus(environ.get("DB_PASSWORD"))
  engine = create_async_engine(f"postgresql+asyncpg://{username}:{password}@{host_db}")

else:
  raise SystemExit(
    f"Database '{settings.mitsuki.db_use}' not recognized or supported"
  )


_engine = None
_session = None
new_session = async_sessionmaker(engine, expire_on_commit=False)


class AsDict:
  def asdict(self, recurse: bool = False):
    return _asdict(self, recurse=recurse)


class Base(DeclarativeBase, AsyncAttrs):
  def asdict(self):
    #: Source: https://stackoverflow.com/a/1960546
    return {c.name: getattr(self, c.name) for c in self.__table__.columns}

  @property
  def columns(self):
    return [c.name for c in self.__table__.columns]


def init(db_url: Optional[str] = None):
  global _engine, _session
  db_url = db_url or environ.get("DB_URL")

  if not db_url:
    raise ValueError("Required environment variable DB_URL is empty or not set")
  if db_url.startswith("sqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
  elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
  else:
    raise ValueError("Database type for DB_URL is invalid or unsupported")

  _engine = create_async_engine(db_url)
  _session = async_sessionmaker(_engine, expire_on_commit=False)


# def engine():
#   global _engine
#   if not _engine:
#     raise RuntimeError("Database engine is uninitialized, cannot run db operations")


def begin_session():
  global _session
  if not _session:
    raise RuntimeError("Database engine is uninitialized, cannot run db operations")

  return _session.begin()


async def initialize():
  global engine
  en = engine
  async with en.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

    if "sqlite" in en.url.drivername:
      await conn.exec_driver_sql("PRAGMA foreign_keys=ON")