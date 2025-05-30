# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from yaml import safe_load
from typing import Optional, Dict, Any, List, Union, TypeAlias
from attrs import frozen, field
from os import environ, PathLike
from interactions import PartialEmoji

from mitsuki import logger

__all__ = (
  "settings",
  "mitsuki",
  "dev",
  "gacha",
  "emoji",
  "load_settings",
)

FileName: TypeAlias = Union[str, bytes, PathLike]


@frozen(kw_only=True)
class BaseSettings:
  mitsuki: "MitsukiSettings"
  dev: "DevSettings"
  gacha: "GachaSettings"
  emoji: "EmojiSettings"

  @classmethod
  def create(cls, filename: str):
    with open(filename, encoding="UTF-8") as f:
      d: Dict[str, Dict[str, Any]] = safe_load(f)

    try:
      return cls(
        mitsuki=MitsukiSettings(**d["mitsuki"]),
        dev=DevSettings(**d["dev"]),
        gacha=GachaSettings(**d["gacha"]),
        emoji=EmojiSettings(**d["emoji"]),
      )
    except KeyError as e:
      raise KeyError(f"Missing settings tree: {str(e)}") from None


@frozen(kw_only=True)
class MitsukiSettings:
  daily_reset: str
  db_use: str
  db_path: str
  db_pg_path: str
  status: List[str]
  status_cycle: int
  status_randomize: bool = field(converter=bool)
  log_info: bool = field(default=False, converter=bool)
  messages: Optional[str] = field(default=None)
  messages_default: Optional[str] = field(default=None)
  messages_dir: Optional[str] = field(default=None)
  messages_custom_dir: Optional[str] = field(default=None)


@frozen(kw_only=True)
class DevSettings:
  scope: Optional[int] = field(default=None)
  db_path: Optional[str] = field(default=None)
  db_pg_path: Optional[str] = field(default=None)


@frozen(kw_only=True)
class GachaSettings:
  settings: str
  roster: str


@frozen(kw_only=True)
class EmojiSettings:
  yes: PartialEmoji = field(converter=PartialEmoji.from_str)
  no: PartialEmoji = field(converter=PartialEmoji.from_str)
  on: PartialEmoji = field(converter=PartialEmoji.from_str)
  off: PartialEmoji = field(converter=PartialEmoji.from_str)

  new: PartialEmoji = field(converter=PartialEmoji.from_str)
  edit: PartialEmoji = field(converter=PartialEmoji.from_str)
  delete: PartialEmoji = field(converter=PartialEmoji.from_str)
  list: PartialEmoji = field(converter=PartialEmoji.from_str)
  gallery: PartialEmoji = field(converter=PartialEmoji.from_str)
  configure: PartialEmoji = field(converter=PartialEmoji.from_str)
  refresh: PartialEmoji = field(converter=PartialEmoji.from_str)
  back: PartialEmoji = field(converter=PartialEmoji.from_str)

  text: PartialEmoji = field(converter=PartialEmoji.from_str)
  time: PartialEmoji = field(converter=PartialEmoji.from_str)
  date: PartialEmoji = field(converter=PartialEmoji.from_str)

  page_first: PartialEmoji = field(converter=PartialEmoji.from_str)
  page_previous: PartialEmoji = field(converter=PartialEmoji.from_str)
  page_next: PartialEmoji = field(converter=PartialEmoji.from_str)
  page_last: PartialEmoji = field(converter=PartialEmoji.from_str)
  page_goto: PartialEmoji = field(converter=PartialEmoji.from_str)


settings = None
mitsuki = None
dev = None
gacha = None
emoji = None


def load_settings(settings_file: Optional[FileName] = None) -> None:
  """
  Load or reload a given Mitsuki settings file.

  If `settings_file` is not provided, the `.env` variable SETTINGS_YAML is used.
  """

  global settings, mitsuki, dev, gacha, emoji

  settings_file = settings_file or environ.get("SETTINGS_YAML")
  if not settings_file or len(settings_file.strip()) <= 0:
    raise ValueError("Cannot load Mitsuki settings file. Ensure SETTINGS_YAML is set in .env to continue")

  settings = BaseSettings.create(settings_file)
  mitsuki = settings.mitsuki
  dev = settings.dev
  gacha = settings.gacha
  emoji = settings.emoji


load_settings()