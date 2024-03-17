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
from attrs import frozen
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

    d_mitsuki = d["mitsuki"]
    d_dev     = d["dev"]
    d_gacha   = d["gacha"]

    return cls(
      mitsuki=MitsukiSettings(
        messages_default=d_mitsuki.get("messages_default"),
        daily_reset=d_mitsuki.get("daily_reset"),
        db_use=d_mitsuki.get("db_use"),
        db_path=d_mitsuki.get("db_path"),
        status=d_mitsuki.get("status"),
        status_cycle=d_mitsuki.get("status_cycle"),
        status_randomize=bool(d_mitsuki.get("status_randomize")),
        messages=d_mitsuki.get("messages")
      ),
      dev=DevSettings(
        scope=d_dev.get("scope"),
        db_path=d_dev.get("db_path")
      ),
      gacha=GachaSettings(
        settings=d_gacha.get("settings"),
        roster=d_gacha.get("roster")
      )
    )


@frozen
class MitsukiSettings:
  messages_default: str
  daily_reset: str
  db_use: str
  db_path: str
  status: List[str]
  status_cycle: int
  status_randomize: bool
  messages: Optional[str] = None


@frozen
class DevSettings:
  scope: Optional[int] = None
  db_path: Optional[str] = None


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