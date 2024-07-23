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
  ComponentContext,
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
  AutocompleteMixin,
  SelectionMixin,
)
from mitsuki.lib.checks import (
  assert_bot_permissions,
  assert_user_permissions,
  assert_user_roles,
  has_user_permissions,
  has_user_roles,
  UserDenied,
)
from mitsuki.lib.userdata import new_session

from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes


async def _check_schedule(ctx: InteractionContext, schedule_key: str):
  has_role  = False
  has_admin = await has_user_permissions(ctx, Permissions.ADMINISTRATOR)
  schedule  = None

  # ID search
  if schedule_key.startswith("@"):
    if schedule_key[1:].isnumeric():
      id = int(schedule_key[1:])
      schedule = await Schedule.fetch_by_id(id, guild=ctx.guild.id)

  # If ID search fails, fallback here
  if not schedule:
    schedule = await Schedule.fetch(ctx.guild.id, schedule_key)

  # Role check
  if schedule and schedule.manager_role_objects:
    has_role = await has_user_roles(ctx, schedule.manager_role_objects)

  # Deny if no role and no admin
  if not has_role and not has_admin:
    raise UserDenied("Server admin or Schedule manager role(s)")

  # Schedule found (or no Schedule)
  return schedule


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

  async def message_not_found(self):
    await self.send("schedule_error_message_not_found", ephemeral=True)


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
          placeholder="e.g. 'Daily Questions'",
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
  SCHEDULE_VIEW_BUTTON_RE: re.Pattern = re.compile(r"schedule_manage_view\|@[0-9]")
  SCHEDULE_MANAGE_BUTTON: str = "schedule_manage_button"
  SCHEDULE_VIEW_SELECT: str = "schedule_manage_select"
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

  @staticmethod
  def view_custom_id(schedule_id: int):
    return f"schedule_manage_view|@{schedule_id}"

  @staticmethod
  def id_from_custom_id(custom_id: str):
    return custom_id.split("|")[-1]


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
      label="Create...",
      custom_id=CreateSchedule.SCHEDULE_CREATE_BUTTON,
    )
    refresh_btn = Button(
      style=ButtonStyle.GRAY,
      label="Refresh",
      custom_id=self.SCHEDULE_MANAGE_BUTTON,
    )
    template_kwargs = {"fields_per_page": 25, "escape_data_values": "guild_name"}

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
        custom_id=self.SCHEDULE_VIEW_SELECT
      )
      self.field_data = schedules
      await self.send_multifield_single(
        self.States.LIST,
        template_kwargs=template_kwargs,
        components=spread_to_rows(select_schedule, create_btn, refresh_btn)
      )


  async def view_from_button(self, custom_id: str):
    return await self.view(self.id_from_custom_id(custom_id))


  async def view(self, schedule_key: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    schedule = await _check_schedule(self.ctx, schedule_key)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_key)

    self.edit_origin = True
    await self.defer(ephemeral=True, suppress_error=True)

    add_message_btn = Button(
      style=ButtonStyle.GREEN,
      label="Add...",
      custom_id=AddMessage.button_custom_id(schedule.id)
    )
    messages_btn = Button(
      style=ButtonStyle.BLURPLE,
      label="Messages",
      custom_id=ManageMessages.button_custom_id(schedule.id)
    )
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
      components=[add_message_btn, messages_btn, return_btn]
    )


class AddMessage(WriterCommand):
  MESSAGE_ADD_BUTTON_RE: re.Pattern = re.compile(r"schedule_add_button\|@[0-9]+")
  MESSAGE_ADD_MODAL_RE: re.Pattern = re.compile(r"schedule_add_modal\|.+")
  MESSAGE_ADD_BUTTON: str = "schedule_add_button"
  MESSAGE_ADD_MODAL: str  = "schedule_add_modal"
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

  @staticmethod
  def button_custom_id(schedule_id: int):
    return f"schedule_add_button|@{schedule_id}"

  @staticmethod
  def modal_custom_id(schedule: Union[str, int]):
    if isinstance(schedule, int):
      return f"schedule_add_modal|@{schedule}"
    return f"schedule_add_modal|{schedule}"

  @staticmethod
  def id_from_custom_id(custom_id: str):
    return custom_id.split("|")[-1]


  async def _check_schedule(self, schedule_key: str):
    has_role  = False
    has_admin = await has_user_permissions(self.ctx, Permissions.ADMINISTRATOR)
    schedule  = None

    # ID search
    if schedule_key.startswith("@"):
      if schedule_key[1:].isnumeric():
        id = int(schedule_key[1:])
        schedule = await Schedule.fetch_by_id(id, guild=self.ctx.guild.id)

    # If ID search fails, fallback here
    if not schedule:
      schedule = await Schedule.fetch(self.ctx.guild.id, schedule_key)

    # Role check
    if schedule and schedule.manager_role_objects:
      has_role = await has_user_roles(self.ctx, schedule.manager_role_objects)

    # Deny if no role and no admin
    if not has_role and not has_admin:
      raise UserDenied("Server admin or Schedule manager role(s)")

    # Schedule found (or no Schedule)
    return schedule


  async def prompt_from_button(self, custom_id: str):
    return await self.prompt(self.id_from_custom_id(custom_id))


  async def prompt(self, schedule_key: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()

    schedule = await self._check_schedule(schedule_key)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_key)
  
    schedule_title = schedule.title if len(schedule.title) <= 32 else schedule.title[:30].strip() + "..."
    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label=f"Message in \"{schedule_title}\"",
          custom_id="message",
          placeholder="e.g. \"Which anime school uniform is your favorite?\"",
          min_length=1,
          max_length=1800
        ),
        title=f"Add Message",
        custom_id=self.modal_custom_id(schedule.id)
      )
    )


  async def run_from_prompt(self, custom_id: str, message: str):
    return await self.run(self.id_from_custom_id(custom_id), message)


  async def run(self, schedule_key: str, message: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await self.defer(ephemeral=True)

    schedule = await self._check_schedule(schedule_key)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_key)

    # Actual addition goes here
    if schedule.type == ScheduleTypes.QUEUE:
      number = str(schedule.current_number + 1)
    else:
      number = "???"

    self.schedule = schedule
    self.schedule_message = schedule.create_message(self.caller_id, message)
    if len(schedule.assign(self.schedule_message)) >= 2000:
      return await _Errors.create(self.ctx).message_too_long()

    message_data = {"message_" + k: v for k, v in self.schedule_message.asdict().items()}
    self.data = self.Data(
      schedule_title=escape_text(schedule.title),
      guild_name=self.ctx.guild.name,
      message=message,
      number=number,
    )
    await self.send_commit(self.States.SUCCESS, other_data=message_data)


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.add(session)


class ManageMessages(SelectionMixin, ReaderCommand):
  LIST_REFRESH_RE: re.Pattern = re.compile(r"schedule_messages_refresh\|@[0-9]")
  LIST_BUTTON_RE: re.Pattern = re.compile(r"schedule_messages_button\|@[0-9]+")
  LIST_BUTTON: str = "schedule_messages_btn"

  VIEW_RE: re.Pattern = re.compile(r"schedule_messages_view\|[0-9]+$")

  EDIT_PROMPT_RE: re.Pattern = re.compile(r"schedule_messages_edit\|[0-9]+$")
  # EDIT_ACTION_RE: re.Pattern = re.compile(r"schedule_messages_edit\|@[0-9]+\|[a-z]+$")
  EDIT_MESSAGE_RE: re.Pattern = re.compile(r"schedule_messages_edit\|[0-9]+\|message")

  state: "ManageMessages.States"
  data: "ManageMessages.Data"
  schedule: Schedule
  schedule_messages: List[ScheduleMessage]

  class States(StrEnum):
    LIST         = "schedule_messages_list"
    NO_LIST      = "schedule_messages_list_no_messages"
    VIEW         = "schedule_messages_view"
    EDIT_SUCCESS = "schedule_messages_edit"

  @define(slots=False)
  class Data(AsDict):
    guild_name: str
    total_messages: int

  @staticmethod
  def id_from_custom_id(custom_id: str):
    return custom_id.split("|")[-1]

  @staticmethod
  def button_custom_id(schedule_id: int):
    return f"schedule_messages_button|@{schedule_id}"

  @staticmethod
  def refresh_custom_id(schedule_id: int):
    return f"schedule_messages_refresh|@{schedule_id}"

  @staticmethod
  def view_custom_id(message_id: int):
    return f"schedule_messages_view|{message_id}"

  @staticmethod
  def edit_custom_id(message_id: int, action: Optional[str] = None):
    if action:
      return f"schedule_messages_edit|{message_id}|{action}"
    return f"schedule_messages_edit|{message_id}"

  @staticmethod
  def edit_action_from_custom_id(custom_id: str):
    r = custom_id.split("|")
    return int(r[1]), r[2]


  async def list_from_button(self, custom_id: str):
    return await self.list_(self.id_from_custom_id(custom_id))


  async def list_(self, schedule_key: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    self.edit_origin = True
    await self.defer(ephemeral=True)

    schedule = await _check_schedule(self.ctx, schedule_key)
    if not schedule:
      return await _Errors.create(self.ctx).schedule_not_found(schedule_key)

    schedule_messages = await ScheduleMessage.fetch_by_schedule(
      self.ctx.guild.id, schedule.title
    )
    self.data = self.Data(guild_name=self.ctx.guild.name, total_messages=len(schedule_messages))

    add_message_btn = Button(
      style=ButtonStyle.GREEN,
      label="Add...",
      custom_id=AddMessage.button_custom_id(schedule.id)
    )
    refresh_btn = Button(
      style=ButtonStyle.GRAY,
      label="Refresh",
      custom_id=self.refresh_custom_id(schedule.id),
    )
    return_btn = Button(
      style=ButtonStyle.GRAY,
      label="Back to Schedule",
      custom_id=ManageSchedules.view_custom_id(schedule.id)
      
    )
    if len(schedule_messages) <= 0:
      await self.send(
        self.States.NO_LIST,
        other_data={"schedule_title": schedule.title},
        components=[add_message_btn, refresh_btn, return_btn]
      )
      return

    self.field_data = schedule_messages
    self.selection_values = [
      StringSelectOption(
        label=f"{schedule.title} #{schedule_message.number or '???'} ",
        value=str(schedule_message.id),
        description=schedule_message.partial_message
      )
      for schedule_message in schedule_messages
      if schedule_message.id
    ]
    self.selection_placeholder = "Message to view or edit..."
    await self.send_selection(
      self.States.LIST,
      other_data={"schedule_title": schedule.title},
      extra_components=[add_message_btn, refresh_btn, return_btn]
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.create(ctx).view(int(ctx.values[0]))


  async def edit_action(self, custom_id: str):
    message_id, action = self.edit_action_from_custom_id(custom_id)

    if action == "message":
      return await self.edit_message_prompt(message_id)


  async def view_from_button(self, custom_id: str):
    message_id = int(self.id_from_custom_id(custom_id))
    return await self.view(message_id, edit_origin=True)


  async def view(self, message_id: int, edit_origin: bool = False):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()

    self.edit_origin = edit_origin
    await self.defer(ephemeral=True)

    message = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message:
      return await _Errors.create(self.ctx).message_not_found()

    buttons = []
    buttons.append(Button(
      style=ButtonStyle.BLURPLE,
      label="Edit...",
      custom_id=self.edit_custom_id(message_id)
    ))
    string_templates = []
    if message.message_id:
      string_templates.append("schedule_messages_message_link")
      # buttons.append(Button(
      #   style=ButtonStyle.GRAY,
      #   label="Post",
      #   url=message.message_link
      # ))

    buttons.append(Button(
      style=ButtonStyle.GRAY,
      label="Refresh",
      custom_id=self.view_custom_id(message_id)
    ))

    await self.send(
      self.States.VIEW,
      other_data=message.asdict(),
      template_kwargs=dict(use_string_templates=string_templates),
      components=buttons
    )


  async def edit_message_prompt(self, custom_id: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()

    message_id = int(self.id_from_custom_id(custom_id))
    message = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message:
      return await _Errors.create(self.ctx).message_not_found()

    schedule = await _check_schedule(self.ctx, f"@{message.schedule_id}")
    if not schedule:
      return await _Errors.create(self.ctx).message_not_found()

    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label=f"Message",
          custom_id="message",
          value=message.message,
          min_length=1,
          max_length=1800
        ),
        title=f"Edit Message",
        custom_id=self.edit_custom_id(message.id, "message")
      )
    )


  async def edit_message_response(self, custom_id: str, message: str):
    if not self.ctx.guild:
      return await _Errors.create(self.ctx).not_in_guild()
    await self.defer(ephemeral=True)

    message_id, _ = self.edit_action_from_custom_id(custom_id)
    message_object = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message_object:
      return await _Errors.create(self.ctx).message_not_found()

    schedule = await _check_schedule(self.ctx, f"@{message_object.schedule_id}")
    if not schedule:
      return await _Errors.create(self.ctx).message_not_found()

    message_object.message = message

    if len(schedule.assign(message_object)) > 2000:
      return await _Errors.create(self.ctx).message_too_long()

    async with new_session() as session:
      await message_object.update_modify(session, self.ctx.author.id)
      await session.commit()

    message_data = message_object.asdict()
    return await self.send(self.States.EDIT_SUCCESS, other_data=message_data)