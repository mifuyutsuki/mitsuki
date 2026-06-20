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
from datetime import datetime, timezone
from enum import StrEnum
import csv
import yaml
import uuid

import attrs
import interactions as ipy
import sqlalchemy as sa
from sqlalchemy import select, update, delete, literal
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki.utils import option, ratio, process_text
from mitsuki.lib.userdata import begin_session, AsDict, sa_insert as insert
from mitsuki.lib.commands import CustomID

from mitsuki.core.settings import get_setting, Settings
from mitsuki.core.submitter import BaseSubmitter
from mitsuki.core.gacha import CardCollectionCategory


@attrs.define(kw_only=True)
class CardPackSetSubmitter(BaseSubmitter):
  to_add: list[CardCollectionCategory] = attrs.field(factory=list)
  to_edit: list[CardCollectionCategory] = attrs.field(factory=list)
  to_remove: list[CardCollectionCategory] = attrs.field(factory=list)

  original_count: int = attrs.field(default=0)
  edit_count: int = attrs.field(default=0)
  error_counts: int = attrs.field(default=0)


  @property
  def add_count(self):
    return len(self.to_add)
  

  @property
  def remove_count(self):
    return len(self.to_remove)


  @property
  def after_count(self):
    return self.original_count + len(self.to_add)


  @classmethod
  async def from_data(cls, data: dict[str, dict[str, Any]]):
    """
    Create a card pack set submitter from a pack set data yaml.

    The data follows the format {<id>: {<field>: <value>, ...}, ...}, where the object inside each id corresponds to
    data for each card pack set. The following fields are available (besides the card pack set id):
    - name: str (required)
    - description: str

    Note that adding packs into a set are done in the card pack submitter instead of this submitter.

    Args:
      data: Card pack set data 
    """
    existing = {c.id: c for c in await CardCollectionCategory.fetch_all(private=True)}
    result = cls()
    result.original_count = len(existing)

    for set_id, set_data in data.items():
      try:
        entry = CardCollectionCategory(
          id=set_id, name=set_data["name"], description=set_data.get("description")
        )
      except (KeyError, ValueError):
        result.error_counts += 1
        continue

      if entry.id not in existing:
        result.to_add.append(entry)
      elif entry != existing.pop(entry.id, None):
        result.to_edit.append(entry)
    
    for remaining in existing.values():
      result.to_remove.append(remaining)

    result.save()
    return result


  async def execute(self, session: AsyncSession):
    for entry in self.to_add:
      await entry.add(session)

    for entry in self.to_edit:
      await entry.add(session)

    for entry in self.to_remove:
      await entry.delete(session)