# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Any, Union, Self
from datetime import timedelta
from enum import IntEnum
import csv
import yaml
import uuid
import asyncio

import attrs
import interactions as ipy
import sqlalchemy as sa
from sqlalchemy import select, update, delete, literal
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki.utils import option, ratio, process_text
from mitsuki.lib.userdata import begin_session, AsDict, sa_insert as insert
from mitsuki.lib.commands import CustomID
from mitsuki.core.settings import get_setting, Settings


_entries: dict[uuid.UUID, "BaseSubmitter"] = {}


@attrs.define(kw_only=True)
class BaseSubmitter:
  id: uuid.UUID = attrs.field(factory=uuid.uuid4)
  data: dict = attrs.field(factory=dict)
  timeout: float = attrs.field(default=300)
  expires: ipy.Timestamp = attrs.field(init=False)


  @classmethod
  async def fetch(cls, id: Union[uuid.UUID, str]) -> Optional[Self]:
    global _entries
    now = ipy.Timestamp.now()

    if isinstance(id, str):
      id = uuid.UUID(id)

    # Cache expiration
    # Global instance may be altered, so we make a copy of keys()
    for _id in list(_entries.keys()):
      if now >= _entries[_id].expires:
        _entries.pop(_id)

    return _entries.get(id)


  def save(self):
    global _entries
    self.expires = ipy.Timestamp.now() + timedelta(seconds=self.timeout)
    _entries[self.id] = self