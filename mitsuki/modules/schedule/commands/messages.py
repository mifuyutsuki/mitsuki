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
  MessageNotFound,
  MessageTooLong,
)
from ..utils import (
  check_fetch_schedule,
  check_fetch_message,
  has_schedule_permissions,
)
from ..customids import CustomIDs


class ManageMessages(SelectionMixin, ReaderCommand):
  data: "ManageMessages.Data"

  @define(slots=False)
  class Data(AsDict):
    total_messages: int

  class Templates(StrEnum):
    LIST           = "schedule_message_list"
    LIST_EMPTY     = "schedule_message_list_empty"
    VIEW           = "schedule_message_view"


  async def list_from_button(self):
    return await self.list(CustomID.get_id_from(self.ctx))


  async def list(self, schedule_key: str):
    # TODO: Break out list to list-backlog and list-posted
    await assert_in_guild(self.ctx)

    self.edit_origin = True
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
    messages = await ScheduleMessage.fetch_by_schedule(self.ctx.guild.id, schedule.title)
    self.data = self.Data(total_messages=len(messages))

    buttons = [
      Button(
        style=ButtonStyle.GREEN,
        label="Add...",
        custom_id=CustomIDs.MESSAGE_ADD.prompt().id(schedule.id)
      ),
      Button(
        style=ButtonStyle.GRAY,
        label="Refresh",
        custom_id=CustomIDs.MESSAGE_LIST.id(schedule.id),
      ),
      Button(
        style=ButtonStyle.GRAY,
        label="Back to Schedule",
        custom_id=CustomIDs.SCHEDULE_VIEW.id(schedule.id),      
      ),
    ]

    if len(messages) <= 0:
      await self.send(
        self.Templates.LIST_EMPTY,
        other_data={"schedule_title": schedule.title},
        components=buttons
      )
      return

    self.field_data = messages
    self.selection_values = [
      StringSelectOption(
        label=f"{schedule.title} #{message.number or '???'} ",
        value=str(message.id),
        description=message.partial_message
      )
      for message in messages
      if message.id
    ]
    self.selection_placeholder = "Message to view or edit..."
    await self.send_selection(
      self.Templates.LIST,
      other_data={"schedule_title": schedule.title},
      extra_components=buttons
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.create(ctx).view(int(ctx.values[0]))


  async def view_from_select(self):
    return await self.view(int(self.ctx.values[0]), edit_origin=True)


  async def view_from_button(self):
    return await self.view(int(CustomID.get_id_from(self.ctx)), edit_origin=True)


  async def view(self, message_id: int, edit_origin: bool = False):
    await assert_in_guild(self.ctx)

    if not self.ctx.deferred:
      if edit_origin and self.has_origin:
        await self.defer(edit_origin=True)
      else:
        await self.defer(ephemeral=True)

    message  = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule = await check_fetch_schedule(self.ctx, f"@{message.schedule_id}")

    string_templates = []
    if message.message_id:
      string_templates.append("schedule_message_message_link")
    if not schedule.active:
      string_templates.append("schedule_message_schedule_inactive")

    other_data = {}
    if schedule.type == ScheduleTypes.QUEUE and not message.date_posted:
      other_data |= {"target_post_time_f": f"<t:{int(schedule.post_time_of(message))}:f>"}
      string_templates.append("schedule_message_target_post_time")

    await self.send(
      self.Templates.VIEW,
      other_data=message.asdict() | other_data,
      template_kwargs=dict(use_string_templates=string_templates),
      components=[
        Button(
          style=ButtonStyle.BLURPLE,
          label="Edit...",
          custom_id=CustomIDs.MESSAGE_EDIT.prompt().id(message_id)
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Reorder...",
          custom_id=CustomIDs.MESSAGE_REORDER.id(message_id),
          disabled=message.date_posted is not None or schedule.backlog_number < 2
        ),
        Button(
          style=ButtonStyle.RED,
          label="Delete",
          custom_id=CustomIDs.MESSAGE_DELETE.confirm().id(message_id)
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Refresh",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id)
        )
      ]
    )