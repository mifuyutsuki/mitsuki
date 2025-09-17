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


_cache: dict[str, SettingValueType] = {}


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
  """A collection of application settings with their metadata."""

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
    SettingTypes.STRING, "gacha.daily.reset_time", "Gacha: Daily Reset Time", "00:00", validator=_hhmm_validator
  )
  "Time on which the next gacha daily can be claimed, in 24-hour HH:MM format."

  DailyResetTimeZone = SettingData(
    SettingTypes.STRING, "gacha.daily.reset_tz", "Gacha: Daily Reset Timezone", "+0000", validator=_tz_validator
  )
  "Timezone on which the next gacha daily can be claimed, in ±HHMM offset format from UTC."


  @staticmethod
  def get(setting: SettingData):
    """
    Get an application setting from the cache, returning the default value if not set or not available.

    Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
    including its type and default value.

    Args:
      setting: Setting to be retrieved

    Returns:
      Setting value, or `None` if not set and `no_default` is `True`
    """
    return get_setting(setting)


  @staticmethod
  async def fetch(setting: SettingData, no_default: bool = False):
    """
    Fetch an application setting from the database, returning the default value if not set.

    Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
    including its type and default value.

    Args:
      setting: Setting to be retrieved
      no_default: Whether to return `None` if the setting is not set, instead of the default value

    Returns:
      Setting value, or `None` if not set and `no_default` is `True`
    """
    return await fetch_setting(setting, no_default=no_default)


  @staticmethod
  async def fetch_all():
    """
    Get all application settings and its values.

    Returns:
      Map of setting IDs to tuples of `SettingData` and the current value, or its default if not set.
    """
    return await fetch_settings()


  @staticmethod
  async def set(session: "AsyncSession", setting: SettingData, value: Optional["SettingValueType"] = None) -> None:
    """
    Set an application setting to the database.

    Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
    including its type and default value.

    If value is `None`, the default value will be used based on the setting's metadata.

    Args:
      session: The current database session
      setting: Setting to be set
      value: Value to set the setting to, or the default if `None`  

    Raises:
      ValueError: Value is of an incorrect type or does not pass validation
    """
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


async def preload_settings():
  """
  Preload application settings to the cache.
  """
  global _cache

  statement = sa.select(Setting)
  async with begin_session() as session:
    results = await session.scalars(statement)

  results = {result.name: result.value for result in results}

  for setting in attrs.astuple(Settings(), recurse=False):
    if not isinstance(setting, SettingData):
      continue
    if result := results.get(setting.id):
      _cache[setting.id] = _convert(setting, _convert(result))


def get_setting(setting: SettingData) -> Optional["SettingValueType"]:
  """
  Get an application setting from the cache, returning the default value if not set or not available.

  Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
  including its type and default value.

  Args:
    setting: Setting to be retrieved

  Returns:
    Setting value, or `None` if not set and `no_default` is `True`
  """
  global _cache
  return _cache.get(setting.id, setting.default)


async def fetch_setting(
  setting: SettingData, no_default: bool = False, force: bool = False
) -> Optional["SettingValueType"]:
  """
  Fetch an application setting from the database, returning the default value if not set.

  Settings are given by `SettingData` instances in `Settings`, which contain metadata about the setting,
  including its type and default value.

  Args:
    setting: Setting to be retrieved
    no_default: Whether to return `None` if the setting is not set, instead of the default value
    force: Whether to force fetching from the database

  Returns:
    Setting value, or `None` if not set and `no_default` is `True`
  """
  global _cache
  if not force:
    if cached_value := _cache.get(setting.id):
      return cached_value

  statement = sa.select(Setting.value).where(Setting.name == setting.id)
  async with begin_session() as session:
    result_s = await session.scalar(statement)

  if result_s:
    result = _convert(setting, result_s)
  elif no_default:
    result = None
  else:
    result = setting.default

  if result is not None:
    _cache[setting.id] = result
  return result


async def fetch_settings() -> dict[str, tuple["SettingData", "SettingValueType"]]:
  """
  Get all application settings and its values.

  Returns:
    Map of setting IDs to tuples of `SettingData` and the current value, or its default if not set.
  """
  statement = sa.select(Setting)
  async with begin_session() as session:
    results = await session.scalars(statement)

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

  If value is `None`, the default value will be used based on the setting's metadata.

  Args:
    session: The current database session
    setting: Setting to be set
    value: Value to set the setting to, or the default if `None`  

  Raises:
    ValueError: Value is of an incorrect type or does not pass validation
  """
  global _cache

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
    .on_conflict_do_update(index_elements=["name"], set_={"value": text})
  )
  await session.execute(statement)
  _cache[setting.id] = _value


def is_valid_value(setting: SettingData, value: "SettingValueType") -> bool:
  """
  Check if a value is valid for a given setting.

  If the setting has a validator, it will be used to check the value.  

  Args:
    setting: Setting to validate against
    value: Value to check
  
  Returns:
    `True` if the value is valid for the setting, `False` otherwise.
  """
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


def create_modal(setting: SettingData) -> ipy.Modal:
  """
  Create a Discord modal for editing a setting.

  Args:
    setting: Setting to create a modal for
  
  Returns:
    Modal object to be sent with interactions.py
  """
  current_value = get_setting(setting)

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