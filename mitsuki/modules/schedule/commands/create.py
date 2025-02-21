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

from mitsuki import bot
from mitsuki.utils import escape_text, is_caller, get_member_color_value
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
  ScheduleTypes
)
from ..daemon import daemon
from ..errors import (
  ScheduleException,
  ScheduleNotFound,
)
from ..utils import (
  check_fetch_schedule,
  has_schedule_permissions,
)
from ..customids import CustomIDs


class CreateSchedule(WriterCommand):
  schedule: Schedule

  class Templates(StrEnum):
    SUCCESS        = "schedule_manage_create_success"
    ALREADY_EXISTS = "schedule_manage_create_already_exists"  


  async def prompt(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Schedule Title",
          custom_id="title",
          placeholder="e.g. \"Daily Questions\"",
          min_length=3,
          max_length=64,
        ),
        title="Create Schedule",
        custom_id=CustomIDs.SCHEDULE_CREATE.response()
      )
    )


  async def response(self, schedule_title: str):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_title = schedule_title.strip()

    # Length check
    if len(schedule_title) <= 0:
      raise BadInput(field="Schedule title")

    # Duplicate check
    guild_schedules = await Schedule.fetch_many(guild=self.ctx.guild.id)
    if schedule_title in (s.title for s in guild_schedules):
      return await self.send(self.Templates.ALREADY_EXISTS)

    self.schedule = Schedule.create(self.ctx, schedule_title)
    await self.send_commit(self.Templates.SUCCESS, other_data={"schedule_title": schedule_title})


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)