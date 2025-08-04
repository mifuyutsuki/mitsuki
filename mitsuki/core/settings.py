# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any, Union

import attrs
import interactions as ipy
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki.lib.userdata import begin_session, sa_insert
from mitsuki.lib.commands import CustomID
from mitsuki.models.settings import SettingTypes, SettingData, Setting, SettingValueType


SETTINGS_EDIT = CustomID("settings_edit")


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
  StatusCycle = SettingData(
    SettingTypes.INTEGER, "runtime.status_cycle_seconds", "Mitsuki: Status Cycle", 300, validator=lambda s: s >= 60
  )
  "Duration of each status message (presence) in seconds before cycling to the next message."

  DailyShards = SettingData(
    SettingTypes.INTEGER, "gacha.shards.daily", "Gacha: Daily Shards", 120
  )
  "Amount of Shards to give as a daily."

  FirstTimeShards = SettingData(
    SettingTypes.INTEGER, "gacha.shards.first_time", "Gacha: First-time Shards", 625
  )
  "Amount of Shards to give as a daily when claimed for the first time."

  DailyResetTime = SettingData(
    SettingTypes.INTEGER, "gacha.daily.reset_time", "Gacha: Daily Reset Time", "00:00", validator=_hhmm_validator
  )
  "Time on which the next gacha daily can be claimed, in 24-hour HH:MM format."

  DailyResetTimeZone = SettingData(
    SettingTypes.INTEGER, "gacha.daily.reset_tz", "Gacha: Daily Reset Timezone", "+0000", validator=_tz_validator
  )
  "Timezone on which the next gacha daily can be claimed, in ±HHMM offset format from UTC."


  @staticmethod
  async def get(setting: SettingData, no_default: bool = False):
    return await get_setting(setting, no_default=no_default)


  @staticmethod
  async def get_all():
    return await get_settings()


  @staticmethod
  async def set(session: "AsyncSession", setting: SettingData, value):
    return await set_setting(session, setting, value)


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


async def get_setting(setting: SettingData, no_default: bool = False) -> Optional["SettingValueType"]:
  statement = sa.select(Setting.value).where(Setting.name == setting.id)
  async with begin_session() as session:
    result = await session.scalar(statement)

  if not result:
    if no_default:
      return None
    return setting.default
  return _convert(setting, result)


async def get_settings() -> dict[str, tuple["SettingData", "SettingValueType"]]:
  statement = sa.select(Setting)
  async with begin_session() as session:
    results = (await session.scalars(statement)).all()

  output = {}
  results = {result.name: result.value for result in results}

  for setting in attrs.astuple(Settings(), recurse=False):
    if not isinstance(setting, SettingData):
      continue
    if result := results.get(setting.id):
      output[setting.id] = (setting, _convert(result))
    else:
      output[setting.id] = (setting, setting.default)

  return output


async def set_setting(
  session: "AsyncSession", setting: SettingData, value: Optional["SettingValueType"] = None
) -> None:
  """
  Set an application setting to the database.

  Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
  including its type and default value.

  If value is None, the default value will be used based on the setting's metadata.

  Args:
    session: The current database session
    setting: Setting to be set
    value: Value to set the setting to, or the default if None  

  Raises:
    ValueError: Value is of an incorrect type or does not pass validation.
  """

  try:
    # Type validation and conversion
    match value, setting.type:
      case None, _:
        text, _value = str(setting.default), setting.default
      case _, SettingTypes.BOOLEAN:
        text, _value = ("1" if bool(value) else "0"), bool(value)
      case _, SettingTypes.INTEGER:
        text, _value = str(value), int(value)
      case _, SettingTypes.FLOAT:
        text, _value = str(value), float(value)
      case _, SettingTypes.STRING:
        text = _value = str(value)
  except (ValueError, TypeError):
    raise ValueError(f"Value has incorrect type for setting {setting.id}: {value!r}") from None

  if setting.validator and not setting.validator(_value):
    raise ValueError(f"Value is invalid for setting {setting.id}: {value!r}")

  statement = (
    sa_insert(Setting)
    .values(name=setting.id, value=text)
    .on_conflict_do_update(index_elements=["value"], set_={"value": text})
  )
  await session.execute(statement)


def is_valid_value(setting: SettingData, value: "SettingValueType") -> bool:
  try:
    # Type validation and conversion
    match setting.type:
      case SettingTypes.BOOLEAN:
        _value = bool(value)
      case SettingTypes.INTEGER:
        _value = int(value)
      case SettingTypes.FLOAT:
        _value = float(value)
      case SettingTypes.STRING:
        _value = str(value)
  except (ValueError, TypeError):
    return False

  return not setting.validator or setting.validator(_value)


async def create_modal(setting: SettingData):
  current_value = await get_setting(setting, no_default=False)

  return ipy.Modal(
    ipy.InputText(
      label=setting.name,
      style=ipy.TextStyles.SHORT,
      custom_id="value",
      placeholder=setting.default,
      value=current_value,
      required=False,
    ),
    title="Edit Settings",
    custom_id=SETTINGS_EDIT.id(setting.id),
  )