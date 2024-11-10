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

from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes
from .daemon import daemon


class CustomIDs:
  SCHEDULE_MANAGE = CustomID("schedule_manage")
  """Manage Schedules. (no args)"""

  SCHEDULE_CREATE = CustomID("schedule_create")
  """Create a Schedule. (no args; modal)"""

  SCHEDULE_VIEW = CustomID("schedule_view")
  """View a Schedule. (id: Schedule ID/key; select)"""

  CONFIGURE = CustomID("schedule_configure")
  """Configure a Schedule. (id: Schedule ID)"""

  CONFIGURE_TITLE = CustomID("schedule_configure_title")
  """Rename the title of a Schedule. (id: Schedule ID; modal)"""

  CONFIGURE_FORMAT = CustomID("schedule_configure_format")
  """Set the posting format text of a Schedule. (id: Schedule ID; modal)"""

  CONFIGURE_ACTIVE = CustomID("schedule_configure_active")
  """Activate or deactivate a Schedule. (id: Schedule ID)"""

  CONFIGURE_PIN = CustomID("schedule_configure_pin")
  """Enable or disable pinning the latest message (requires extra permissions). (id: Schedule ID)"""

  CONFIGURE_DISCOVERABLE = CustomID("schedule_configure_discoverable")
  """[FUTURE] Show or hide messages in this Schedule to publicly accessible /schedule view. (id: Schedule ID)"""

  CONFIGURE_CHANNEL = CustomID("schedule_configure_channel")
  """Set where the Schedule should be posted. (id: Schedule ID; select)"""

  CONFIGURE_ROLES = CustomID("schedule_configure_roles")
  """Set roles other than admins that can manage messages in a Schedule. (id: Schedule ID; select [multiple])"""

  CONFIGURE_ROLES_CLEAR = CustomID("schedule_configure_roles|clear")
  """Clear manager roles of a Schedule. (id: Schedule ID)"""

  # TODO: Non-daily routines
  CONFIGURE_ROUTINE = CustomID("schedule_configure_routine")
  """Set the posting time of a Schedule. (id: Schedule ID; modal)"""

  MESSAGE_ADD = CustomID("schedule_message_add")
  """Add a message to a Schedule. (id: Schedule ID/key; modal)"""

  MESSAGE_LIST = CustomID("schedule_message_list")
  """View list of messages in a Schedule. (id: Schedule ID/key)"""

  MESSAGE_VIEW = CustomID("schedule_message_view")
  """View a message in a Schedule. (id: Message ID; select)"""

  MESSAGE_EDIT = CustomID("schedule_message_edit")
  """Edit a message in a Schedule. (id: Message ID; modal)"""

  MESSAGE_DELETE = CustomID("schedule_message_delete")
  """Delete a message in a Schedule. (id: Message ID; confirm)"""

  MESSAGE_REORDER = CustomID("schedule_message_reorder")
  """Reorder a message in a queue-type Schedule. (id: Message ID; modal)"""

  MESSAGE_REORDER_FRONT = CustomID("schedule_message_reorder|front")
  """Reorder a message to front of a queue-type Schedule. (id: Message ID)"""
  
  MESSAGE_REORDER_BACK = CustomID("schedule_message_reorder|back")
  """Reorder a message to back of a queue-type Schedule. (id: Message ID)"""


class Templates(StrEnum):
  # List Messages (/schedule list)
  LIST             = "schedule_list"
  LIST_NO_MESSAGES = "schedule_list_no_messages"

  # View Message (/schedule view)
  VIEW_SEARCH_RESULTS = "schedule_view_search_results"
  VIEW_NO_RESULTS     = "schedule_view_no_results"
  VIEW_NO_MESSAGES    = "schedule_view_no_messages"
  VIEW_MESSAGE        = "schedule_view"

  # Manage Schedules
  SCHEDULES_LIST             = "schedule_manage_list" # Multifield/Selection
  SCHEDULES_LIST_EMPTY       = "schedule_manage_list_empty"
  SCHEDULES_LIST_UNAVAILABLE = "schedule_manage_list_unavailable"
  SCHEDULES_VIEW             = "schedule_manage_view"

  # Create Schedule
  SCHEDULES_CREATE_SUCCESS        = "schedule_manage_create_success"
  SCHEDULES_CREATE_ALREADY_EXISTS = "schedule_manage_create_already_exists"  

  # Configure Schedule (Select)
  CONFIGURE_MENU    = "schedule_configure"
  CONFIGURE_CHANNEL = "schedule_configure_select_channel"
  CONFIGURE_ROLES   = "schedule_configure_select_roles"
  CONFIGURE_ROUTINE = "schedule_configure_select_routine" # Future

  # Configure Schedule (Response)
  CONFIGURE_TITLE_SUCCESS   = "schedule_configure_edit_title_success"
  CONFIGURE_FORMAT_SUCCESS  = "schedule_configure_edit_format_success"
  CONFIGURE_ROUTINE_SUCCESS = "schedule_configure_edit_routine_success"

  # Configure Schedule (Errors)
  CONFIGURE_ERROR_NOT_READY                = "schedule_configure_not_ready"
  CONFIGURE_ERROR_TITLE_ALREADY_EXISTS     = "schedule_configure_title_already_exists"
  CONFIGURE_ERROR_SEND_PERMISSION_REQUIRED = "schedule_configure_requires_send_permissions"
  CONFIGURE_ERROR_PIN_PERMISSION_REQUIRED  = "schedule_configure_requires_pin_permissions"

  # Manage Messages (Select)
  MESSAGES_LIST           = "schedule_message_list"
  MESSAGES_LIST_EMPTY     = "schedule_message_list_empty"
  MESSAGES_VIEW           = "schedule_message_view"

  # Add Message
  MESSAGE_ADD_SUCCESS     = "schedule_message_add_success"

  # Edit Message
  MESSAGE_EDIT_SUCCESS    = "schedule_message_edit_success"

  # Reorder Message
  MESSAGE_REORDER_SELECT  = "schedule_message_reorder_select"
  MESSAGE_REORDER_SUCCESS = "schedule_message_reorder_success"

  # Delete Message
  MESSAGE_DELETE_CONFIRM  = "schedule_message_delete_confirm"
  MESSAGE_DELETE_SUCCESS  = "schedule_message_delete_success"


class ScheduleException(MitsukiSoftException):
  """Base class for Schedule exceptions."""


class ScheduleNotFound(ScheduleException):
  TEMPLATE: str = "schedule_error_schedule_not_found"

  def __init__(self, schedule_key: Optional[str] = None):
    self.data = {"schedule_title": escape_text(schedule_key or "-")}    


class MessageTooLong(ScheduleException):
  TEMPLATE: str = "schedule_error_message_too_long"

  def __init__(self, length: int):
    self.data = {"length": length}


class MessageNotFound(ScheduleException):
  TEMPLATE: str = "schedule_error_message_not_found"


async def fetch_schedule(ctx: InteractionContext, schedule_key: str):
  # ID search
  schedule = None
  if schedule_key.isnumeric():
    id = int(schedule_key)
    schedule = await Schedule.fetch_by_id(id, guild=ctx.guild.id)
  elif schedule_key.startswith("@") and schedule_key[1:].isnumeric():
    id = int(schedule_key[1:])
    schedule = await Schedule.fetch_by_id(id, guild=ctx.guild.id)

  # If ID search fails, fallback here
  if not schedule:
    schedule = await Schedule.fetch(ctx.guild.id, schedule_key)

  return schedule


async def check_fetch_schedule(ctx: InteractionContext, schedule_key: str):
  # Search
  schedule = await fetch_schedule(ctx, schedule_key)

  # Deny if no role and no admin
  if not await has_schedule_permissions(ctx, schedule):
    raise UserDenied("Server admin or Schedule manager role(s)")

  # Throw error on no Schedule
  if not schedule:
    raise ScheduleNotFound(schedule_key=schedule_key)

  # Schedule found (or no Schedule)
  return schedule


async def check_fetch_message(message_id: int, guild: Optional[Snowflake] = None):
  message = await ScheduleMessage.fetch(message_id, guild=guild)
  if not message:
    raise MessageNotFound()
  return message


async def has_schedule_permissions(ctx: InteractionContext, schedule: Optional[Schedule] = None):
  has_role  = False
  has_admin = await has_user_permissions(ctx, Permissions.ADMINISTRATOR)

  # Role check
  if schedule and schedule.manager_role_objects:
    has_role = await has_user_roles(ctx, schedule.manager_role_objects)

  return has_role or has_admin


class ManageSchedules(SelectionMixin, ReaderCommand):
  data: "ManageSchedules.Data"
  schedules: List[Schedule]

  @define(slots=False)
  class Data(AsDict):
    total_schedules: int


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
      return await self.send(Templates.SCHEDULES_LIST_UNAVAILABLE, components=[])
    if len(allowed_schedules) <= 0:
      return await self.send(Templates.SCHEDULES_LIST_EMPTY, components=buttons)

    self.selection_values = [schedule.title for schedule in allowed_schedules]
    self.selection_placeholder = "Select a Schedule to manage..."

    self.field_data = allowed_schedules
    await self.send_selection(Templates.SCHEDULES_LIST, extra_components=buttons)


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
      Templates.SCHEDULES_VIEW,
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


class ManageMessages(SelectionMixin, ReaderCommand):
  data: "ManageMessages.Data"

  @define(slots=False)
  class Data(AsDict):
    total_messages: int


  async def list_from_button(self):
    return await self.list(CustomID.get_id_from(self.ctx))


  async def list(self, schedule_key: str):
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
        Templates.MESSAGES_LIST_EMPTY,
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
      Templates.MESSAGES_LIST,
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
      Templates.MESSAGES_VIEW,
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


class CreateSchedule(WriterCommand):
  schedule: Schedule


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
      return await self.send(Templates.SCHEDULES_CREATE_ALREADY_EXISTS)

    self.schedule = Schedule.create(self.ctx, schedule_title)
    await self.send_commit(Templates.SCHEDULES_CREATE_SUCCESS, other_data={"schedule_title": schedule_title})


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)


class ConfigureSchedule(WriterCommand):
  async def main(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    await self.send(
      Templates.CONFIGURE_MENU,
      other_data=schedule.asdict(),
      components=[
        ActionRow(
          Button(
            style=ButtonStyle.BLURPLE,
            label="Title...",
            custom_id=CustomIDs.CONFIGURE_TITLE.prompt().id(schedule_id)
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Format...",
            custom_id=CustomIDs.CONFIGURE_FORMAT.prompt().id(schedule_id)
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Roles...",
            custom_id=CustomIDs.CONFIGURE_ROLES.prompt().id(schedule_id)
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Channel...",
            custom_id=CustomIDs.CONFIGURE_CHANNEL.prompt().id(schedule_id),
            disabled=schedule.active
          ),
          Button(
            style=ButtonStyle.BLURPLE,
            label="Routine...",
            custom_id=CustomIDs.CONFIGURE_ROUTINE.prompt().id(schedule_id),
            disabled=schedule.active
          ),
        ),
        ActionRow(
          Button(
            style=ButtonStyle.RED if schedule.active else ButtonStyle.GREEN,
            label="Deactivate" if schedule.active else "Activate",
            custom_id=CustomIDs.CONFIGURE_ACTIVE.id(schedule_id),
            disabled=not schedule.active and not await schedule.is_valid()
          ),
          Button(
            style=ButtonStyle.RED if schedule.pin else ButtonStyle.GREEN,
            label="Disable Pin" if schedule.pin else "Enable Pin",
            custom_id=CustomIDs.CONFIGURE_PIN.id(schedule_id),
            disabled=schedule.post_channel is None
          ),
          Button(
            style=ButtonStyle.RED if schedule.discoverable else ButtonStyle.GREEN,
            label="Disable Discovery" if schedule.discoverable else "Enable Discovery",
            custom_id=CustomIDs.CONFIGURE_DISCOVERABLE.id(schedule_id)
          ),
        ),
        ActionRow(
          Button(
            style=ButtonStyle.GRAY,
            label="Refresh",
            custom_id=CustomIDs.CONFIGURE.id(schedule_id)
          ),
          Button(
            style=ButtonStyle.GRAY,
            label="Back to Schedule",
            custom_id=CustomIDs.SCHEDULE_VIEW.id(schedule_id)
          ),
        ),
      ]
    )


  async def prompt_title(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Title",
          custom_id="title",
          placeholder="e.g. \"Daily Questions\"",
          value=schedule.title,
          min_length=3,
          max_length=64,
        ),
        title="Edit Schedule",
        custom_id=CustomIDs.CONFIGURE_TITLE.response().id(schedule_id)
      )
    )


  async def set_title(self, title: str):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    title = title.strip()

    # Length check
    if len(title) <= 0:
      raise BadInput(field="Schedule title")

    # Same title check
    if title == schedule.title:
      return await self.send(Templates.CONFIGURE_TITLE_SUCCESS)

    # Duplicate check
    guild_schedules = await Schedule.fetch_many(guild=self.ctx.guild.id)
    if title in (s.title for s in guild_schedules):
      return await self.send(Templates.CONFIGURE_ERROR_TITLE_ALREADY_EXISTS)

    schedule.title = title

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(Templates.CONFIGURE_TITLE_SUCCESS)


  async def prompt_format(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label="Format",
          custom_id="format",
          placeholder="e.g. \"Today's Question: ${message}\"",
          value=schedule.format,
          min_length=3,
          max_length=1800,
        ),
        title="Edit Schedule",
        custom_id=CustomIDs.CONFIGURE_FORMAT.response().id(schedule_id)
      )
    )


  async def set_format(self, format: str):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    format = format.strip()

    # Length check
    if len(format) <= 0:
      raise BadInput(field="Schedule format")

    # Same format check
    if format == schedule.format:
      return await self.send(Templates.CONFIGURE_FORMAT_SUCCESS)

    schedule.format = format

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(Templates.CONFIGURE_FORMAT_SUCCESS)


  # async def select_routine(self):
  #   await assert_in_guild(self.ctx)
  #   await assert_user_permissions(
  #     self.ctx, Permissions.ADMINISTRATOR,
  #     "Server admin"
  #   )

  #   # TODO: Routine options other than daily
  #   return await self.prompt_daily_routine()


  async def prompt_routine(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    # Schedule existence check
    _ = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Post Time (UTC)",
          custom_id="format",
          placeholder="24-hour UTC time as HH:MM, e.g. \"7:00\"",
          min_length=1,
          max_length=5,
        ),
        title="Edit Schedule",
        custom_id=CustomIDs.CONFIGURE_ROUTINE.response().id(schedule_id)
      )
    )


  # TODO: Custom routines
  async def set_routine(self, time: str):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    # HH:MM validation
    if not re.match(r"^[0-9]{1,2}:[0-9]{1,2}$", time):
      raise BadInput(field="daily post time")

    # 00:00-24:00 validation (regex already ensures numeric)
    hour, minute = int(time.split(":")[0]), int(time.split(":")[1])
    if (hour, minute) == (24, 00):
      hour, minute = 0, 0
    if not (0 <= hour < 24) or not (0 <= minute < 60):
      raise BadInput(field="daily post time")

    # Set routine
    if f"{minute} {hour} * * *" == schedule.post_routine:
      next_fire = f"<t:{int(schedule.cron().next(float))}:f>"
      return await self.send(Templates.CONFIGURE_ROUTINE_SUCCESS, other_data={"next_fire_f": next_fire})

    schedule.post_routine = f"{minute} {hour} * * *"
    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    next_fire = f"<t:{int(schedule.cron().next(float))}:f>"
    return await self.send(Templates.CONFIGURE_ROUTINE_SUCCESS, other_data={"next_fire_f": next_fire})


  async def toggle_active(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    if schedule.active:
      await daemon.deactivate(schedule)
      schedule.deactivate()
    elif not await schedule.is_valid():
      return await self.send(Templates.CONFIGURE_ERROR_NOT_READY, ephemeral=True)
    else:
      await daemon.activate(schedule)
      schedule.activate()

    # Activation toggles don't modify the schedule itself
    async with new_session() as session:
      await schedule.update(session)
      await session.commit()
    return await self.main()


  async def toggle_pin(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    if schedule.pin and schedule.current_pin and schedule.post_channel:
      with suppress(Forbidden, NotFound):
        pinned_channel = await self.ctx.guild.fetch_channel(schedule.post_channel)
        if pinned_channel and (pinned_message := await pinned_channel.fetch_message(schedule.current_pin)):
          await pinned_message.unpin()
      schedule.current_pin = None
    elif not await has_bot_channel_permissions(
      self.ctx.bot,
      schedule.post_channel,
      [
        Permissions.MANAGE_MESSAGES,
        Permissions.VIEW_CHANNEL,
        Permissions.READ_MESSAGE_HISTORY,
        Permissions.SEND_MESSAGES
      ]
    ):
      return await self.send(Templates.CONFIGURE_ERROR_PIN_PERMISSION_REQUIRED, ephemeral=True)

    schedule.pin = not schedule.pin

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


  async def toggle_discoverable(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    schedule.discoverable = not schedule.discoverable

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


  async def select_channel(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    current_channel = None
    if schedule.post_channel:
      current_channel = await self.ctx.guild.fetch_channel(schedule.post_channel)

    return await self.send(
      Templates.CONFIGURE_CHANNEL,
      other_data=schedule.asdict(),
      components=[
        ActionRow(
          ChannelSelectMenu(
            channel_types=[ChannelType.GUILD_TEXT],
            placeholder="Select post channel",
            default_values=[current_channel] if current_channel else None,
            custom_id=CustomIDs.CONFIGURE_CHANNEL.select().id(schedule_id)
          )
        ),
        ActionRow(
          Button(
            style=ButtonStyle.RED,
            label="Cancel",
            custom_id=CustomIDs.CONFIGURE.id(schedule_id)
          ),
        ),
      ]
    )


  async def set_channel(self, channel: TYPE_ALL_CHANNEL):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    # Permission check - Send Messages
    if not await has_bot_channel_permissions(self.ctx.bot, channel.id, Permissions.SEND_MESSAGES):
      return await self.send(Templates.CONFIGURE_ERROR_SEND_PERMISSION_REQUIRED, ephemeral=True)

    # Don't modify if the current channel is selected
    if channel.id == schedule.post_channel:
      return await self.main()

    # Changing channel resets the pin status
    if schedule.pin and schedule.post_channel and schedule.current_pin:
      with suppress(Forbidden, NotFound):
        pinned_channel = await self.ctx.guild.fetch_channel(schedule.post_channel)
        if pinned_channel and (pinned_message := await pinned_channel.fetch_message(schedule.current_pin)):
          await pinned_message.unpin()
      schedule.current_pin = None
    schedule.pin = False

    # Set post channel
    schedule.post_channel = channel.id

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


  async def select_roles(self):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    current_roles = []
    if schedule.manager_roles:
      for role_id in schedule.manager_role_objects:
        if role := await self.ctx.guild.fetch_role(role_id):
          current_roles.append(role)

    return await self.send(
      Templates.CONFIGURE_ROLES,
      other_data=schedule.asdict(),
      components=[
        ActionRow(
          RoleSelectMenu(
            placeholder="Select Schedule manager roles",
            default_values=current_roles if len(current_roles) > 0 else None,
            custom_id=CustomIDs.CONFIGURE_ROLES.select().id(schedule_id),
            min_values=1,
            max_values=25,
          )
        ),
        ActionRow(
          Button(
            style=ButtonStyle.RED,
            label="Clear Roles",
            custom_id=CustomIDs.CONFIGURE_ROLES_CLEAR.id(schedule_id)
          ),
          Button(
            style=ButtonStyle.RED,
            label="Cancel",
            custom_id=CustomIDs.CONFIGURE.id(schedule_id)
          ),
        ),
      ]
    )


  async def set_roles(self, roles: List[Role]):
    await assert_in_guild(self.ctx)
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule    = await check_fetch_schedule(self.ctx, f"@{schedule_id}")

    current_roles = schedule.manager_role_objects
    target_roles = [role.id for role in roles]

    # Don't modify if there are no change in roles
    if current_roles and (set(current_roles) == set(target_roles)):
      return await self.main()

    if len(roles) > 0:
      schedule.manager_roles = " ".join(sorted([str(role.id) for role in roles]))
    else:
      schedule.manager_roles = None

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


class AddMessage(WriterCommand):
  schedule: Schedule
  schedule_message: ScheduleMessage


  async def prompt_from_button(self):
    return await self.prompt(CustomID.get_id_from(self.ctx))


  async def prompt(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
  
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
        ShortText(
          label=f"Tags (Optional)",
          custom_id="tags",
          placeholder="Space-separated e.g. \"anime apparel favorite\"",
          required=False,
        ),
        title=f"Add Message",
        custom_id=CustomIDs.MESSAGE_ADD.response().id(schedule.id)
      )
    )


  async def response_from_prompt(self, message: str, tags: Optional[str] = None):
    return await self.response(CustomID.get_id_from(self.ctx), message, tags)


  async def response(self, schedule_key: str, message: str, tags: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)

    message = message.strip()

    # Length check
    if len(message) <= 0:
      raise BadInput(field="Schedule message")

    # Create message
    self.schedule_message = schedule.create_message(self.caller_id, message)
    assigned_len = len(schedule.assign(self.schedule_message))
    if assigned_len > 2000:
      raise MessageTooLong(assigned_len)
    if tags:
      self.schedule_message.set_tags(tags)

    m = await self.send_commit(Templates.MESSAGE_ADD_SUCCESS, other_data=self.schedule_message.asdict(), components=[])

    # Delayed action to fetch message id
    if m and self.schedule_message.id:
      await self.ctx.edit(m, components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Go to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(self.schedule_message.id)
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Reorder...",
          custom_id=CustomIDs.MESSAGE_REORDER.id(self.schedule_message.id),
          disabled=schedule.backlog_number <= 0
        ),
      ])


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.add(session)


class EditMessage(WriterCommand):
  state: "EditMessage.States"
  data: "EditMessage.Data"

  schedule_message: ScheduleMessage

  class States(StrEnum):
    SUCCESS = "schedule_message_edit_success"

  @define(slots=False)
  class Data(AsDict):
    pass


  async def prompt(self):
    await assert_in_guild(self.ctx)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    # Schedule existence check
    _ = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label="Message",
          custom_id="message",
          placeholder="e.g. \"Which anime school uniform is your favorite?\"",
          value=message.message,
          min_length=1,
          max_length=1800
        ),
        ShortText(
          label="Tags",
          custom_id="tags",
          placeholder="Space-separated e.g. \"anime apparel favorite\"",
          value=message.tags,
          required=False,
        ),
        title=f"Edit Message",
        custom_id=CustomIDs.MESSAGE_EDIT.response().id(message_id)
      )
    )


  async def response(self, message: str, tags: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    message_id     = int(CustomID.get_id_from(self.ctx))
    message_object = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule       = await check_fetch_schedule(self.ctx, f"{message_object.schedule_id}")

    message = message.strip()

    # Length check
    if len(message) <= 0:
      raise BadInput(field="Schedule message")
    if tags and len(tags.strip()) <= 0:
      raise BadInput(field="Schedule message tags")

    message_object.message = message
    assigned_len = len(schedule.assign(message_object))
    if assigned_len > 2000:
      raise MessageTooLong(assigned_len)

    if tags:
      message_object.set_tags(tags)
    else:
      message_object.tags = None

    self.schedule_message = message_object
    return await self.send_commit(Templates.MESSAGE_EDIT_SUCCESS, other_data=message_object.asdict(), components=[])


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.update_modify(session, self.ctx.author.id)


class ReorderMessage(WriterCommand):
  schedule_message: ScheduleMessage
  new_number: int


  def new_number_dict(self):
    return {
      "old_number": self.schedule_message.number,
      "old_number_s": f"{self.schedule_message.number}",
      "number": self.new_number,
      "number_s": f"{self.new_number}"
    }


  async def select(self):
    """
    Open the reorder menu for a given message. Schedule type QUEUE only.

    Inputs:
      Message ID from component Custom ID

    Buttons:
      To Front  : Move message to front of queue
      Custom... : Select a number (prompt)
      To Back   : Move message to back of queue
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    components = [
      ActionRow(
        Button(
          style=ButtonStyle.BLURPLE,
          label="To Front",
          custom_id=CustomIDs.MESSAGE_REORDER_FRONT.id(message_id),
          disabled=message.number <= schedule.posted_number + 1
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Custom...",
          custom_id=CustomIDs.MESSAGE_REORDER.prompt().id(message_id),
          disabled=schedule.backlog_number < 2
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="To Back",
          custom_id=CustomIDs.MESSAGE_REORDER_BACK.id(message_id),
          disabled=message.number == schedule.current_number
        )
      ),
      ActionRow(
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      )
    ]
    sent = await self.send(
      Templates.MESSAGE_REORDER_SELECT,
      other_data=schedule.asdict() | message.asdict(),
      components=components,
    )

    try:
      _ = await self.ctx.bot.wait_for_component(sent, components, timeout=30)
    except TimeoutError:
      if sent:
        await self.ctx.edit(sent, components=[
          ActionRow(
            Button(
              style=ButtonStyle.GRAY,
              label="Refresh",
              custom_id=CustomIDs.MESSAGE_REORDER.id(message_id),
            ),
            Button(
              style=ButtonStyle.GRAY,
              label="Back to Message",
              custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
            )
          )
        ])


  async def to_front(self):
    """
    Move message to front of queue.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    self.schedule_message = message
    self.new_number       = schedule.posted_number + 1
    return await self.send_commit(
      Templates.MESSAGE_REORDER_SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      ]
    )


  async def to_back(self):
    """
    Move message to back of queue.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    self.schedule_message = message
    self.new_number       = schedule.current_number
    return await self.send_commit(
      Templates.MESSAGE_REORDER_SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      ]
    )


  async def prompt(self):
    """
    [Prompt] Move message to a specified valid number.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Number",
          custom_id="number",
          placeholder=f"Number from {schedule.posted_number + 1} to {schedule.current_number}",
          required=True,
        ),
        title=f"Reorder Message",
        custom_id=CustomIDs.MESSAGE_REORDER.response().id(message_id)
      )
    )


  async def response(self, number_s: str):
    """
    [Response] Move message to a specified valid number.
  
    Inputs:
      Message ID from component Custom ID
      New number from prompt
    """
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    # Number check
    if not number_s.isnumeric():
      raise BadInput(field="Schedule message number")
    number = int(number_s)
    if not (schedule.posted_number < number <= schedule.current_number):
      raise BadInputRange(field="Schedule message number")

    # Reorder
    self.schedule_message = message
    self.new_number       = number
    return await self.send_commit(
      Templates.MESSAGE_REORDER_SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[]
    )


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.update_reorder(session, self.new_number, author=self.ctx.author.id)


class DeleteMessage(WriterCommand):
  schedule_message: ScheduleMessage


  async def confirm(self):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id     = int(CustomID.get_id_from(self.ctx))
    message_object = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    # Schedule existence check
    _ = await check_fetch_schedule(self.ctx, f"{message_object.schedule_id}")

    return await self.send(
      Templates.MESSAGE_DELETE_CONFIRM,
      other_data=message_object.asdict(),
      components=[
        Button(
          style=ButtonStyle.GREEN,
          label="Delete",
          custom_id=CustomIDs.MESSAGE_DELETE.id(message_id)
        ),
        Button(
          style=ButtonStyle.RED,
          label="Cancel",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id)
        )
      ]
    )


  async def run(self):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id     = int(CustomID.get_id_from(self.ctx))
    message_object = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    # Schedule existence check
    _ = await check_fetch_schedule(self.ctx, f"{message_object.schedule_id}")

    self.schedule_message = message_object
    return await self.send_commit(Templates.MESSAGE_DELETE_SUCCESS, other_data=message_object.asdict(), components=[])


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.delete(session)