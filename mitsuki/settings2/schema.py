# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import UniqueConstraint, text, types
from sqlalchemy.orm import Mapped, mapped_column
from rapidfuzz import fuzz
from typing import Optional, List, Callable, Any
from enum import Enum
import attrs

from mitsuki.lib.userdata import Base


class SettingTypes(Enum):
  BOOLEAN = 0
  INTEGER = 1
  FLOAT = 2
  STRING = 3


@attrs.frozen()
class SettingData:
  type: SettingTypes
  name: str
  default: Optional[Any] = None
  validator: Optional[Callable[..., bool]] = None


class Setting(Base):
  __tablename__ = "system_settings"

  name: Mapped[str] = mapped_column(types.String(64), primary_key=True)
  value: Mapped[Optional[str]] = mapped_column(types.Text)