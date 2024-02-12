# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from os import environ

__all__ = (
  "Base",
  "engine",
  "initialize",
)

USERDATA_PATH = environ.get("USERDATA_PATH")
engine = create_engine(f"sqlite+pysqlite:///{USERDATA_PATH}")


class Base(DeclarativeBase):
  def asdict(self):
    #: Source: https://stackoverflow.com/a/1960546
    return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def initialize():
  global engine
  Base.metadata.create_all(engine)