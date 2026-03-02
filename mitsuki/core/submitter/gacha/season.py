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
from mitsuki.core.gacha import GachaSeason, Card


@attrs.define(kw_only=True)
class GachaSeasonSubmitter(BaseSubmitter):
  season: GachaSeason
  existing_season: Optional[GachaSeason] = attrs.field(default=None)
  card_ids: list[str] = attrs.field(factory=list)
  card_patterns: list[str] = attrs.field(factory=list)
  original_card_count: int = attrs.field(default=0)
  new_card_count: int = attrs.field(default=0)


  @classmethod
  async def from_data(cls, data: dict[str, Any]):
    """
    Create a gacha season submitter from a season data yaml.

    Args:
      data: Season data in key-value entries
    
    Returns:
      Instance of this submitter
    """
    season = GachaSeason(
      id=data["id"], name=data["name"], collection=data.get("collection", data["id"]), pickup_rate=data["pickup_rate"],
      start_time=datetime.fromisoformat(data["start_time"]).astimezone(timezone.utc).timestamp(),
      end_time=datetime.fromisoformat(data["end_time"]).astimezone(timezone.utc).timestamp(),
      description=data.get("description"), image=data.get("image")
    )
    existing = await GachaSeason.fetch(data["id"])

    result = cls(season=season)
    if cards := data.get("cards"):
      result.new_card_count += await Card.grep_id(cards)
      result.card_ids = cards
    if cards_regex := data.get("cards_regex"):
      result.new_card_count += await Card.grep_id_count(cards_regex)
      result.card_patterns = cards_regex
    if existing:
      result.original_card_count = await existing.card_count()
    result.existing_season = existing

    result.save()
    return result


  async def execute(self, session: AsyncSession, *, overwrite: bool = False):
    await self.season.add(session, create_collection=True)
    if overwrite:
      await self.season.clear(session)
    await self.season.add_cards(session, self.card_ids)
    await self.season.add_cards_by_grep_id(session, self.card_patterns)