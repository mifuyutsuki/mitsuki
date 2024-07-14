# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

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
from interactions import (
  Snowflake,
  BaseUser,
  Member,
  InteractionContext,
  Message,
  Timestamp,
  Button,
  ButtonStyle,
  StringSelectMenu,
  Permissions,
)
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki import bot
from mitsuki.utils import escape_text, is_caller, get_member_color_value
from mitsuki.lib.commands import (
  AsDict,
  ReaderCommand,
  WriterCommand,
  TargetMixin,
  MultifieldMixin,
  AutocompleteMixin
)
from mitsuki.lib.checks import (
  assert_bot_permissions,
  assert_user_permissions,
)

from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes


class _Errors(ReaderCommand):
  async def not_in_guild(self):
    await self.send("schedule_error_not_in_guild", ephemeral=True)

  async def schedule_not_found(self, schedule_title: str):
    await self.send(
      "schedule_error_schedule_not_found",
      other_data={"schedule_title": escape_text(schedule_title)},
      ephemeral=True,
    )

  async def message_too_long(self, length: int):
    await self.send(
      "schedule_error_message_too_long",
      other_data={"length": length},
      ephemeral=True,
    )


class CreateSchedule(WriterCommand):
  state: "CreateSchedule.States"
  data: "CreateSchedule.Data"
  schedule: Schedule

  class States(StrEnum):
    SUCCESS = "schedule_create"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    guild_name: str


  async def run(self, schedule_title: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    self.data = self.Data(schedule_title=schedule_title, guild_name=self.ctx.guild.name)
    self.schedule = Schedule.create(self.ctx, schedule_title)

    await self.send_commit(self.States.SUCCESS)


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)


class AddMessage(WriterCommand):
  state: "AddMessage.States"
  data: "AddMessage.Data"
  schedule: Schedule
  schedule_message: ScheduleMessage

  class States(StrEnum):
    SUCCESS = "schedule_add"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    guild_name: str
    message: str
    number: str


  async def run(self, schedule_title: str, message: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin or Schedule manager role(s)"
    )
    await self.defer(ephemeral=True)

    schedule = await Schedule.fetch(schedule_title)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)
    self.schedule = schedule
    if schedule.type == ScheduleTypes.QUEUE:
      number = str(schedule.current_number + 1)
    else:
      number = "???"

    self.schedule_message = schedule.create_message(self.caller_id, message)
    if len(self.schedule_message.assign_to(schedule.format)) >= 2000:
      return await _Errors.create(self.ctx).message_too_long()

    message_data = {"message_" + k: v for k, v in self.schedule_message.asdbdict().items()}
    self.data = self.Data(
      schedule_title=escape_text(schedule_title),
      guild_name=self.ctx.guild.name,
      message=message,
      number=number,
    )
    await self.send_commit(self.States.SUCCESS, other_data=message_data)


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.add(session)


class ListMessages(MultifieldMixin, ReaderCommand):
  state: "ListMessages.States"
  data: "ListMessages.Data"
  schedule: Schedule
  schedule_messages: List[ScheduleMessage]

  class States(StrEnum):
    LIST = "schedule_list"
    NO_LIST = "schedule_list_no_messages"

  @define(slots=False)
  class Data(AsDict):
    pass


  async def run(self, schedule_title: str):
    self.schedule = await Schedule.fetch(schedule_title)
    if not self.schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    self.schedule_messages = await ScheduleMessage.fetch(schedule_title, discoverable=True, backlog=False)
    if len(self.schedule_messages) <= 0:
      await self.send(self.States.NO_LIST, other_data={"schedule_title": schedule_title})
      return

    self.field_data = self.schedule_messages
    await self.send_multifield(self.States.LIST, other_data={"schedule_title": schedule_title})