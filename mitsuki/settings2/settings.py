# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any

import attrs
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as slinsert
from sqlalchemy.dialects.postgresql import insert as pginsert

from mitsuki.lib.userdata import engine, new_session
from .schema import SettingTypes, SettingData, Setting

insert = pginsert if "postgresql" in engine.url.drivername else slinsert

def _hhmm_validator(hhmm: str):
  try:
    hh, mm = hhmm.split(":")
    hh, mm = int(hh), int(mm)
  except Exception:
    return False
  return (0 <= hh < 24) and (0 <= mm < 60)


def _tz_validator(tz: str):
  try:
    dir, hh, mm = tz[0], tz[1:3], tz[3:5]
    hh, mm = int(hh), int(mm)
  except Exception:
    return False
  return (dir in ("+", "-")) and (0 <= hh < 24) and (0 <= mm < 60)


@attrs.frozen()
class Settings:
  StatusCycle = SettingData(SettingTypes.INTEGER, "runtime.status_cycle", 300, lambda s: s >= 60)

  DailyShards = SettingData(SettingTypes.INTEGER, "gacha.shards.daily", 120)
  FirstTimeShards = SettingData(SettingTypes.INTEGER, "gacha.shards.first_time", 625)

  DailyResetTime = SettingData(SettingTypes.INTEGER, "gacha.daily.reset_time", "00:00", _hhmm_validator)
  DailyResetTimeZone = SettingData(SettingTypes.INTEGER, "gacha.daily.reset_tz", "+0000", _tz_validator)

  @staticmethod
  async def get(setting: SettingData, no_default: bool = False):
    return await get(setting, no_default=no_default)

  @staticmethod
  async def get_all():
    return await get_all()

  @staticmethod
  async def set(session: AsyncSession, setting: SettingData, value):
    return await set(session, setting, value)


def _convert(setting: SettingData, value: str):
  match setting.type:
    case SettingTypes.BOOLEAN:
      return value == "1"
    case SettingTypes.INTEGER:
      return int(value)
    case SettingTypes.FLOAT:
      return float(value)
    case SettingTypes.STRING:
      return value


async def get(setting: SettingData, no_default: bool = False):
  statement = sa.select(Setting.value).where(Setting.name == setting.name)
  async with new_session.begin() as session:
    result = await session.scalar(statement)

  if not result:
    if no_default:
      return None
    return setting.default
  return _convert(setting, result)


async def get_all() -> dict[str, Any]:
  statement = sa.select(Setting)
  async with new_session.begin() as session:
    results = (await session.scalars(statement)).all()

  output = {}
  results = {result.name: result.value for result in results}
  for setting in attrs.astuple(Settings(), recurse=False):
    if not isinstance(setting, SettingData):
      continue
    if setting.name in results:
      output[setting.name] = _convert(results[setting.name])
    else:
      output[setting.name] = setting.default
  return output


async def set(session: AsyncSession, setting: SettingData, value):
  try:
    # Type validation and conversion
    match setting.type:
      case SettingTypes.BOOLEAN:
        value = "1" if bool(value) else "0"
      case SettingTypes.INTEGER:
        value, _ = str(value), int(value)
      case SettingTypes.FLOAT:
        value, _ = str(value), float(value)
      case SettingTypes.STRING:
        value = str(value)
  except (ValueError, TypeError):
    raise ValueError(f"Value has incorrect type for setting {setting.name}: {value!r}") from None

  if setting.validator and not setting.validator(value):
    raise ValueError(f"Value is invalid for setting {setting.name}: {value!r}")

  statement = (
    sa.insert(Setting)
    .values(name=setting.name, value=setting.value)
    .on_conflict_do_update(index_elements=["value"], set_={"value": setting.value})
  )
  await session.execute(statement)