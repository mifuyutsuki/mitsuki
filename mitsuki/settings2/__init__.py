# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""
New Mitsuki Settings system.

In future versions, settings that can be changed in-bot will be moved here.
This includes things such as the presences cycle (status cycle) and
gacha shard counts, but not message paths and custom emoji settings.
"""

from .settings import Settings, SettingData, SettingTypes, get, get_all, set

__all__ = (
  "Settings",
  "SettingData",
  "SettingTypes",
  "get",
  "get_all",
  "set",
)