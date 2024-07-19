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
  StringSelectOption,
  Permissions,
  Modal,
  ShortText,
  ParagraphText,
  spread_to_rows,
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
  assert_user_roles,
  has_user_permissions,
  has_user_roles,
  UserDenied,
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
  SCHEDULE_CREATE_BUTTON: str = "schedule_create_button"
  SCHEDULE_CREATE_MODAL: str = "schedule_create_modal"
  state: "CreateSchedule.States"
  data: "CreateSchedule.Data"
  schedule: Schedule

  class States(StrEnum):
    SUCCESS = "schedule_create"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    guild_name: str


  async def prompt(self):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Schedule Name",
          custom_id="title",
          placeholder="Daily Questions",
          min_length=1,
        ),
        title="Create Schedule",
        custom_id=self.SCHEDULE_CREATE_MODAL
      )
    )

  async def run(self, schedule_title: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    self.edit_origin = False
    await self.defer(ephemeral=True)

    self.data = self.Data(schedule_title=schedule_title, guild_name=self.ctx.guild.name)
    self.schedule = Schedule.create(self.ctx, schedule_title)

    await self.send_commit(self.States.SUCCESS)


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)


class ManageSchedules(MultifieldMixin, ReaderCommand):
  SCHEDULE_MANAGE_BUTTON: str = "schedule_manage_button"
  SCHEDULE_MANAGE_SELECT: str = "schedule_manage_select"
  state: "ManageSchedules.States"
  data: "ManageSchedules.Data"
  schedules: List[Schedule]

  class States(StrEnum):
    LIST       = "schedule_manage_list"
    LIST_EMPTY = "schedule_manage_list_empty"
    VIEW       = "schedule_manage_view"

  @define(slots=False)
  class Data(AsDict):
    guild_name: str
    guild_icon: str
    total_schedules: int


  async def list(self):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    self.edit_origin = True
    await self.defer(ephemeral=True, suppress_error=True)

    create_btn = Button(
      style=ButtonStyle.GREEN,
      label="Create",
      custom_id=CreateSchedule.SCHEDULE_CREATE_BUTTON,
    )
    refresh_btn = Button(
      style=ButtonStyle.GRAY,
      label="Refresh",
      custom_id=self.SCHEDULE_MANAGE_BUTTON,
    )
    template_kwargs = {"escape_data_values": "guild_name"}

    schedules = await Schedule.fetch_many(guild=self.ctx.guild.id, sort="name")
    self.data = self.Data(
      guild_name=self.ctx.guild.name,
      guild_icon=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.bot.user.avatar_url,
      total_schedules=len(schedules)
    )

    if len(schedules) <= 0:
      await self.send(
        self.States.LIST_EMPTY,
        template_kwargs=template_kwargs,
        components=[create_btn, refresh_btn]
      )
    else:
      select_schedule = StringSelectMenu(
        *[
          StringSelectOption(
            label=schedule.title,
            value=schedule.title,
          )
          for schedule in schedules
        ],
        placeholder="Select a Schedule to manage",
        custom_id=self.SCHEDULE_MANAGE_SELECT
      )
      self.field_data = schedules
      await self.send_multifield_single(
        self.States.LIST,
        template_kwargs=template_kwargs,
        components=spread_to_rows(select_schedule, create_btn, refresh_btn)
      )

  async def view(self, schedule_title: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    schedule = await Schedule.fetch(self.ctx.guild.id, schedule_title)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    self.edit_origin = True
    await self.defer(ephemeral=True, suppress_error=True)

    return_btn = Button(
      style=ButtonStyle.GRAY,
      label="Back to Schedules",
      custom_id=self.SCHEDULE_MANAGE_BUTTON,
    )
    template_kwargs = {"escape_data_values": "guild_name"}
    self.data = self.Data(
      guild_name=self.ctx.guild.name,
      guild_icon=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.bot.user.avatar_url,
      total_schedules=0
    )
    await self.send(
      self.States.VIEW,
      other_data=schedule.asdict(),
      template_kwargs=template_kwargs,
      components=[return_btn]
    )


class AddMessage(WriterCommand):
  MESSAGE_ADD_MODAL: str = "schedule_add_modal"
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


  async def prompt(self, schedule_title: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()

    has_role  = False
    has_admin = await has_user_permissions(self.ctx, Permissions.ADMINISTRATOR)
    schedule  = await Schedule.fetch(self.ctx.guild.id, schedule_title)
    if schedule and schedule.manager_role_objects:
      has_role = await has_user_roles(self.ctx, schedule.manager_role_objects)
    if not has_role and not has_admin:
      raise UserDenied("Server admin or Schedule manager role(s)")

    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Schedule Name",
          custom_id="schedule",
          value=schedule_title,
          min_length=1,
        ),
        ParagraphText(
          label="Message",
          custom_id="message",
          placeholder="Which anime school uniform is your favorite?",
          min_length=1,
          max_length=2000
        ),
        title="Message",
        custom_id=self.MESSAGE_ADD_MODAL
      )
    )


  async def run(self, schedule_title: str, message: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin or Schedule manager role(s)"
    )
    await self.defer(ephemeral=True)

    schedule = await Schedule.fetch(self.ctx.guild.id, schedule_title)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    if schedule.type == ScheduleTypes.QUEUE:
      number = str(schedule.current_number + 1)
    else:
      number = "???"

    self.schedule = schedule
    self.schedule_message = schedule.create_message(self.caller_id, message)
    if len(schedule.assign(self.schedule_message)) >= 2000:
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
    self.schedule = await Schedule.fetch(self.ctx.guild.id, schedule_title)
    if not self.schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_title)

    self.schedule_messages = await ScheduleMessage.fetch(
      self.ctx.guild.id, schedule_title, discoverable=True, backlog=False
    )
    if len(self.schedule_messages) <= 0:
      await self.send(self.States.NO_LIST, other_data={"schedule_title": schedule_title})
      return

    self.field_data = self.schedule_messages
    await self.send_multifield(self.States.LIST, other_data={"schedule_title": schedule_title})