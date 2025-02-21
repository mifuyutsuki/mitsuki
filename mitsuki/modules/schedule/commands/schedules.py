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


class ManageSchedules(SelectionMixin, ReaderCommand):
  data: "ManageSchedules.Data"
  schedules: List[Schedule]

  @define(kw_only=True, slots=False)
  class Data(AsDict):
    total_schedules: int

  class Templates(StrEnum):
    LIST             = "schedule_manage_list" # Multifield/Selection
    LIST_EMPTY       = "schedule_manage_list_empty"
    LIST_UNAVAILABLE = "schedule_manage_list_unavailable"
    VIEW             = "schedule_manage_view"


  async def list(self):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    can_create = await has_user_permissions(self.ctx, Permissions.ADMINISTRATOR)
    buttons = [
      Button(
        style=ButtonStyle.GREEN,
        label="Create...",
        custom_id=CustomIDs.SCHEDULE_CREATE.prompt(),
        disabled=not can_create
      ),
      Button(
        style=ButtonStyle.GRAY,
        label="Refresh",
        custom_id=CustomIDs.SCHEDULE_MANAGE,
      ),
    ]

    total_schedules = await Schedule.fetch_many(guild=self.ctx.guild.id, sort="name")
    allowed_schedules = []
    if can_create:
      # This variable being True implies admin
      allowed_schedules = total_schedules
    else:
      # Non-admins can only manage and view schedules based on manager roles
      for schedule in total_schedules:
        if await has_schedule_permissions(self.ctx, schedule):
          allowed_schedules.append(schedule)

    self.data = self.Data(
      total_schedules=len(allowed_schedules)
    )

    if len(allowed_schedules) <= 0 and not can_create:
      return await self.send(self.Templates.LIST_UNAVAILABLE, components=[])
    if len(allowed_schedules) <= 0:
      return await self.send(self.Templates.LIST_EMPTY, components=buttons)

    self.selection_values = [schedule.title for schedule in allowed_schedules]
    self.selection_placeholder = "Select a Schedule to manage..."

    self.field_data = allowed_schedules
    await self.send_selection(self.Templates.LIST, extra_components=buttons)


  async def selection_callback(self, ctx: ComponentContext):
    return await self.view_from_select(ctx)


  async def view_from_select(self, ctx: ComponentContext):
    return await self.create(ctx).view(ctx.values[0])


  async def view_from_button(self):
    return await self.view(CustomID.get_id_from(self.ctx))


  async def view(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    can_configure = await has_user_permissions(self.ctx, Permissions.ADMINISTRATOR)
    schedule      = await check_fetch_schedule(self.ctx, schedule_key)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    self.data = self.Data(
      total_schedules=0
    )
    await self.send(
      self.Templates.VIEW,
      other_data=schedule.asdict(),
      components=[
        ActionRow(
          Button(
            style=ButtonStyle.GREEN,
            label="Add...",
            custom_id=CustomIDs.MESSAGE_ADD.prompt().id(schedule.id)
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Messages",
            custom_id=CustomIDs.MESSAGE_LIST.id(schedule.id)
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Configure",
            custom_id=CustomIDs.CONFIGURE.id(schedule.id),
            disabled=not can_configure
          ),
        ),
        ActionRow(
          Button(
            style=ButtonStyle.GRAY,
            label="Refresh",
            custom_id=CustomIDs.SCHEDULE_VIEW.id(schedule.id),
          ),
          Button(
            style=ButtonStyle.GRAY,
            label="Back to Schedules",
            custom_id=CustomIDs.SCHEDULE_MANAGE,
          ),
        )
      ]
    )