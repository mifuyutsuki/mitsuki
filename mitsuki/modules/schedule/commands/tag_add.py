# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import re
from attrs import define, field
from typing import Optional, Union, List, Dict, Any, NamedTuple
from enum import Enum, StrEnum
from contextlib import suppress
from interactions import (
  ComponentContext,
  Snowflake,
  BaseUser,
  Member,
  InteractionContext,
  Message,
  Timestamp,
  ActionRow,
  Button,
  ButtonStyle,
  StringSelectMenu,
  StringSelectOption,
  ChannelSelectMenu,
  ChannelType,
  TYPE_ALL_CHANNEL,
  RoleSelectMenu,
  Role,
  Permissions,
  Modal,
  ShortText,
  ParagraphText,
  spread_to_rows,
)
from interactions.client.errors import Forbidden, NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki import settings
from mitsuki.utils import escape_text, is_caller, get_member_color_value, truncate
from mitsuki.lib.commands import (
  CustomID,
  AsDict,
  ReaderCommand,
  WriterCommand,
  TargetMixin,
  MultifieldMixin,
  AutocompleteMixin,
  SelectionMixin,
)
from mitsuki.lib.checks import (
  assert_in_guild,
  assert_bot_permissions,
  assert_user_permissions,
  assert_user_roles,
  has_user_permissions,
  has_user_roles,
  has_bot_channel_permissions,
)
from mitsuki.lib.errors import (
  MitsukiSoftException,
  UserDenied,
  BadInput,
  BadInputRange,
  BadLength,
)
from mitsuki.lib.userdata import new_session

from ..userdata import (
  Schedule,
  Message as ScheduleMessage,
  ScheduleTag,
  ScheduleTypes,
)
from ..daemon import daemon
from ..errors import (
  ScheduleException,
  ScheduleNotFound,
  MessageNotFound,
  MessageTooLong,
  TagInvalidName,
  TagAlreadyExists,
  TagNotFound,
)
from ..utils import (
  check_fetch_schedule,
  check_fetch_message,
  has_schedule_permissions,
)
from ..customids import CustomIDs


class AddTag(WriterCommand):
  schedule_tag: ScheduleTag


  class Templates(StrEnum):
    SUCCESS = "schedule_tag_add_success"


  async def prompt_from_button(self):
    return await self.prompt(CustomID.get_id_from(self.ctx))


  async def prompt(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)

    schedule_title = truncate(schedule.title, length=32)
    await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label=f"Tag in \"{schedule_title}\"",
          custom_id="name",
          placeholder="e.g. 'fashion'",
          min_length=1
        ),
        ParagraphText(
          label=f"Description (Optional)",
          custom_id="description",
          placeholder="Outfits, accessories, and other things related to appearance.",
          max_length=100,
          required=False,
        ),
        title=f"Add Tag",
        custom_id=CustomIDs.TAG_ADD.response().id(schedule.id)
      )
    )


  async def response_from_prompt(self, name: str, description: Optional[str] = None):
    return await self.response(CustomID.get_id_from(self.ctx), name, description)


  async def response(self, schedule_key: str, name: str, description: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)

    name = name.strip().lower()

    # Length check
    if len(name) <= 0:
      raise BadInput(field="Schedule tag")

    # Spaces check
    if ' ' in name:
      raise TagInvalidName()
  
    # Duplicate check
    tags = [tag.name for tag in await ScheduleTag.fetch_all(schedule, guild=self.ctx.guild.id, public=False)]
    if name in tags:
      raise TagAlreadyExists(name)

    self.schedule_tag = schedule.create_tag(self.caller_id, name, description)

    m = await self.send_commit(
      self.Templates.SUCCESS,
      other_data=self.schedule_tag.asdict() | {
        "schedule_title": schedule.title,
      },
      components=[]
    )

    # Deferred action to fetch tag id
    # if m and self.schedule_tag.id:
    #   await self.ctx.edit(m, components=[
    #     Button(
    #       style=ButtonStyle.GRAY,
    #       label="Go to Tag",
    #       emoji=settings.emoji.page_next,
    #       custom_id=CustomIDs.TAG_VIEW.id(self.schedule_tag.id)
    #     ),
    #   ])


  async def transaction(self, session: AsyncSession):
    await self.schedule_tag.add(session)