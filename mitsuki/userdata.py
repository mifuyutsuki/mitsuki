# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import Task, IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.event import listens_for
from sqlite3 import Connection as SQLite3Connection
from os import environ

__all__ = (
  "Base",
  "engine",
  "initialize",
  "checkpoint",
)

USERDATA_PATH = environ.get("USERDATA_PATH")
engine = create_engine(f"sqlite+pysqlite:///{USERDATA_PATH}")


class Base(DeclarativeBase):
  def asdict(self):
    #: Source: https://stackoverflow.com/a/1960546
    return {c.name: getattr(self, c.name) for c in self.__table__.columns}


@listens_for(engine, "connect")
def set_wal(dbapi_connection, connection_record):
  if isinstance(dbapi_connection, SQLite3Connection):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def checkpoint():
  global engine
  try:
    raw_connection   = engine.raw_connection()
    dbapi_connection = raw_connection.dbapi_connection
    if isinstance(dbapi_connection, SQLite3Connection):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA wal_checkpoint")
      cursor.close()
  finally:
    raw_connection.close()


@Task.create(IntervalTrigger(minutes=1))
async def checkpoint_task():
  checkpoint()
  

async def initialize():
  global engine, checkpoint_wal
  Base.metadata.create_all(engine)
  checkpoint_task.start()