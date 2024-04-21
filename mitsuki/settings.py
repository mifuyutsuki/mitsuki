# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from yaml import safe_load
from typing import Optional, Dict, Any, List
from attrs import frozen, field
from os import environ

import logging
logger = logging.getLogger(__name__)

__all__ = (
  "mitsuki",
  "dev",
  "gacha",
)


@frozen
class BaseSettings:
  mitsuki: "MitsukiSettings"
  dev: "DevSettings"
  gacha: "GachaSettings"

  @classmethod
  def create(cls, filename: str):
    with open(filename) as f:
      d: Dict[str, Dict[str, Any]] = safe_load(f)

    try:
      return cls(
        mitsuki=MitsukiSettings(**d["mitsuki"]),
        dev=DevSettings(**d["dev"]),
        gacha=GachaSettings(**d["gacha"])
      )
    except KeyError as e:
      raise KeyError(f"Missing settings tree: {str(e)}") from None


@frozen
class MitsukiSettings:
  daily_reset: str
  db_use: str
  db_path: str
  status: List[str]
  status_cycle: int
  status_randomize: bool = field(converter=bool)
  log_info: bool = field(default=False, converter=bool)
  messages: Optional[str] = field(default=None)
  messages_default: Optional[str] = field(default=None)
  messages_dir: Optional[str] = field(default=None)
  messages_custom_dir: Optional[str] = field(default=None)


@frozen
class DevSettings:
  scope: Optional[int] = field(default=None)
  db_path: Optional[str] = field(default=None)


@frozen
class GachaSettings:
  settings: str
  roster: str


_settings_file = environ.get("SETTINGS_YAML") or ""
if len(_settings_file.strip()) > 0:
  root = BaseSettings.create(_settings_file)
else:
  root = None
  logger.warning("No valid SETTINGS_YAML provided")


mitsuki = root.mitsuki if root else None
dev = root.dev if root else None
gacha = root.gacha if root else None