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

from .userdata import Schedule, Message as ScheduleMessage


class _Errors(ReaderCommand):
  async def not_in_guild(self):
    await self.send("schedule_error_not_in_guild")

  async def schedule_not_found(self, schedule_title: str):
    await self.send("schedule_error_schedule_not_found", other_data={"schedule_title": schedule_title})


class CreateSchedule(WriterCommand):
  state: "CreateSchedule.States"
  data: "CreateSchedule.Data"
  schedule: Schedule

  class States(StrEnum):
    SUCCESS = "schedule_create_schedule_success"

  @define(slots=False)
  class Data(AsDict):
    title: str
    guild_name: str


  async def run(self, schedule_title: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    self.data = self.Data(title=schedule_title, guild_name=self.ctx.guild.name)

    self.schedule = Schedule.create(self.ctx, schedule_title)
    await self.send_commit(self.States.SUCCESS)


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)


class AddMessage(WriterCommand):
  state: "AddMessage.States"
  data: "AddMessage.Data"
  schedule: Schedule
  message: ScheduleMessage

  class States(StrEnum):
    SUCCESS = "schedule_add_message_success"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    message: str
    number: int


  async def run(self, schedule_title: str, message: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()

    schedule = await Schedule.fetch(schedule_title)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    self.message  = ScheduleMessage.create(self.ctx, self.schedule, message)
    self.data = self.Data(schedule_title=schedule_title, message=message, number=self.message.number)
    await self.send_commit(self.States.SUCCESS)


  async def transaction(self, session: AsyncSession):
    await self.message.add(session)


class ListMessages(MultifieldMixin, ReaderCommand):
  state: "ListMessages.States"
  data: "ListMessages.Data"