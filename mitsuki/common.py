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

from dotenv import dotenv_values
from yaml import safe_load

__all__ = (
  "UserdataBase",
  "get_config",
  "load_yaml",
  "initialize",
  "userdata_engine",
  "BOT_TOKEN",
  "DEV_GUILD",
  "MESSAGES_YAML",
)
_env = dotenv_values(".env")


class UserdataBase(DeclarativeBase):
  pass

def get_config(field: str):
  return _env.get(field)

def load_yaml(filename: str):
  with open(filename, encoding='UTF-8') as f:
    return safe_load(f)
  
def initialize():
  global userdata_engine
  UserdataBase.metadata.create_all(userdata_engine)


# Mandatory keys
_userdata_path = _env["USERDATA_PATH"]
BOT_TOKEN = _env["BOT_TOKEN"]
DEV_GUILD = _env["DEV_GUILD"]
MESSAGES_YAML = _env["MESSAGES_YAML"]

userdata_engine = create_engine(f"sqlite+pysqlite:///{_userdata_path}")