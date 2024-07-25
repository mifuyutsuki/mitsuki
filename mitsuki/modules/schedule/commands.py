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
  assert_bot_permissions,
  assert_user_permissions,
  assert_user_roles,
  has_user_permissions,
  has_user_roles,
  has_bot_channel_permissions,
  UserDenied,
)
from mitsuki.lib.userdata import new_session

from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes
from .daemon import daemon


async def fetch_schedule(ctx: InteractionContext, schedule_key: str):
  # ID search
  schedule = None
  if schedule_key.isnumeric():
    id = int(schedule_key)
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

  # Schedule found (or no Schedule)
  return schedule


async def has_schedule_permissions(ctx: InteractionContext, schedule: Optional[Schedule] = None):
  has_role  = False
  has_admin = await has_user_permissions(ctx, Permissions.ADMINISTRATOR)

  # Role check
  if schedule and schedule.manager_role_objects:
    has_role = await has_user_roles(ctx, schedule.manager_role_objects)

  return has_role or has_admin


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

  CONFIGURE_ROUTINE = CustomID("schedule_configure_routine")
  """[FUTURE] Set the posting time of a Schedule. (id: Schedule ID; select; modal)"""

  MESSAGE_ADD = CustomID("schedule_message_add")
  """Add a message to a Schedule. (id: Schedule ID/key; modal)"""

  MESSAGE_LIST = CustomID("schedule_message_list")
  """View list of messages in a Schedule. (id: Schedule ID/key)"""

  MESSAGE_VIEW = CustomID("schedule_message_view")
  """View a message in a Schedule. (id: Message ID; select)"""

  MESSAGE_EDIT = CustomID("schedule_message_edit")
  """Edit a message in a Schedule. (id: Message ID; modal)"""


class Errors(ReaderCommand):
  async def not_in_guild(self):
    await self.send("schedule_error_not_in_guild", ephemeral=True)

  async def schedule_not_found(self, schedule_key: Optional[str] = None):
    await self.send(
      "schedule_error_schedule_not_found",
      other_data={"schedule_title": escape_text(schedule_key or "-")},
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


class ManageSchedules(SelectionMixin, ReaderCommand):
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
      return await Errors.create(self.ctx).not_in_guild()

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

    schedules = await Schedule.fetch_many(guild=self.ctx.guild.id, sort="name")
    self.data = self.Data(
      guild_name=self.ctx.guild.name,
      guild_icon=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.bot.user.avatar_url,
      total_schedules=len(schedules)
    )

    if len(schedules) <= 0:
      await self.send(
        self.States.LIST_EMPTY,
        template_kwargs={"escape_data_values": "guild_name"},
        components=buttons,
      )
    else:
      self.selection_values = [schedule.title for schedule in schedules]
      self.selection_placeholder = "Select a Schedule to manage..."

      self.field_data = schedules
      await self.send_selection(
        self.States.LIST,
        template_kwargs={"escape_data_values": "guild_name"},
        extra_components=buttons,
      )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.view_from_select(ctx)


  async def view_from_select(self, ctx: ComponentContext):
    return await self.create(ctx).view(ctx.values[0])


  async def view_from_button(self):
    return await self.view(CustomID.get_id_from(self.ctx))


  async def view(self, schedule_key: str):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule = await fetch_schedule(self.ctx, schedule_key)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(schedule_key)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    self.data = self.Data(
      guild_name=self.ctx.guild.name,
      guild_icon=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.bot.user.avatar_url,
      total_schedules=0
    )
    await self.send(
      self.States.VIEW,
      other_data=schedule.asdict(),
      template_kwargs={
        "escape_data_values": "guild_name"
      },
      components=[
         Button(
          style=ButtonStyle.GREEN,
          label="Add...",
          custom_id=CustomIDs.MESSAGE_ADD.prompt().id(schedule.id)
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Configure",
          custom_id=CustomIDs.CONFIGURE.id(schedule.id)
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Messages",
          custom_id=CustomIDs.MESSAGE_LIST.id(schedule.id)
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Schedules",
          custom_id=CustomIDs.SCHEDULE_MANAGE,
        ),
      ]
    )


class ManageMessages(SelectionMixin, ReaderCommand):
  state: "ManageMessages.States"
  data: "ManageMessages.Data"

  class States(StrEnum):
    LIST         = "schedule_message_list"
    NO_LIST      = "schedule_message_list_empty"
    VIEW         = "schedule_message_view"

  @define(slots=False)
  class Data(AsDict):
    guild_name: str
    total_messages: int


  async def list_from_button(self):
    return await self.list(CustomID.get_id_from(self.ctx))


  async def list(self, schedule_key: str):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    self.edit_origin = True
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(schedule_key)

    schedule_messages = await ScheduleMessage.fetch_by_schedule(
      self.ctx.guild.id, schedule.title
    )
    self.data = self.Data(guild_name=self.ctx.guild.name, total_messages=len(schedule_messages))

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

    if len(schedule_messages) <= 0:
      await self.send(
        self.States.NO_LIST,
        other_data={"schedule_title": schedule.title},
        components=buttons
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
      extra_components=buttons
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.create(ctx).view(int(ctx.values[0]))


  async def view_from_select(self):
    return await self.view(int(self.ctx.values[0]), edit_origin=True)


  async def view_from_button(self):
    return await self.view(int(CustomID.get_id_from(self.ctx)), edit_origin=True)


  async def view(self, message_id: int, edit_origin: bool = False):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()

    if not self.ctx.deferred:
      if edit_origin and self.has_origin:
        await self.defer(edit_origin=True)
      else:
        await self.defer(ephemeral=True)

    message = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message:
      return await Errors.create(self.ctx).message_not_found()

    string_templates = []
    if message.message_id:
      string_templates.append("schedule_message_message_link")

    await self.send(
      self.States.VIEW,
      other_data=message.asdict(),
      template_kwargs=dict(use_string_templates=string_templates),
      components=[
        Button(
          style=ButtonStyle.BLURPLE,
          label="Edit...",
          custom_id=CustomIDs.MESSAGE_EDIT.prompt().id(message_id)
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Refresh",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id)
        )
      ]
    )


class CreateSchedule(WriterCommand):
  state: "CreateSchedule.States"
  data: "CreateSchedule.Data"
  schedule: Schedule

  class States(StrEnum):
    SUCCESS = "schedule_manage_create_success"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    guild_name: str


  async def prompt(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
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


  async def run(self, schedule_title: str):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    self.data = self.Data(schedule_title=schedule_title, guild_name=self.ctx.guild.name)
    self.schedule = Schedule.create(self.ctx, schedule_title)

    await self.send_commit(self.States.SUCCESS)


  async def transaction(self, session: AsyncSession):
    await self.schedule.add(session)


class ConfigureSchedule(WriterCommand):
  state: "ConfigureSchedule.States"
  data: "ConfigureSchedule.Data"

  class States(StrEnum):
    MAIN           = "schedule_configure"
    SELECT_CHANNEL = "schedule_configure_select_channel"
    SELECT_ROLES   = "schedule_configure_select_roles"

    EDIT_TITLE_SUCCESS = "schedule_configure_edit_title_success"
    EDIT_FORMAT_SUCCESS = "schedule_configure_edit_format_success"

    # Errors
    SEND_PERMISSION_REQUIRED = "schedule_configure_requires_send_permissions"
    PIN_PERMISSION_REQUIRED  = "schedule_configure_requires_pin_permissions"

    # Future
    SELECT_ROUTINE = "schedule_configure_select_routine"

  @define(slots=False)
  class Data(AsDict):
    guild_name: str
    guild_icon: str


  async def main(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    self.data = self.Data(
      guild_name=self.ctx.guild.name,
      guild_icon=self.ctx.guild.icon.url if self.ctx.guild.icon else self.ctx.bot.user.avatar_url,
    )
    await self.send(
      self.States.MAIN,
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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    schedule.title = title

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(self.States.EDIT_TITLE_SUCCESS)


  async def prompt_format(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )
    await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    schedule.format = format

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(self.States.EDIT_FORMAT_SUCCESS)


  async def toggle_active(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    if schedule.active:
      await daemon.deactivate(schedule)
      schedule.deactivate()
    else:
      await daemon.activate(schedule)
      schedule.activate()

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.main()


  async def toggle_pin(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    if schedule.pin and schedule.current_pin and schedule.post_channel:
      with suppress(Forbidden, NotFound):
        pinned_channel = await self.ctx.guild.fetch_channel(schedule.post_channel)
        if pinned_channel and (pinned_message := await pinned_channel.fetch_message(schedule.current_pin)):
          await pinned_message.unpin()
      schedule.current_pin = None
    else:
      if not await has_bot_channel_permissions(
        self.ctx.bot,
        schedule.post_channel,
        [
          Permissions.MANAGE_MESSAGES,
          Permissions.VIEW_CHANNEL,
          Permissions.READ_MESSAGE_HISTORY,
          Permissions.SEND_MESSAGES
        ]
      ):
        return await self.send(self.States.PIN_PERMISSION_REQUIRED, ephemeral=True)

    schedule.pin = not schedule.pin

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


  async def toggle_discoverable(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    schedule.discoverable = not schedule.discoverable

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()
    return await self.main()


  async def select_channel(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    current_channel = None
    if schedule.post_channel:
      current_channel = await self.ctx.guild.fetch_channel(schedule.post_channel)

    return await self.send(
      self.States.SELECT_CHANNEL,
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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    # Permission check - Send Messages
    if not await has_bot_channel_permissions(self.ctx.bot, channel.id, Permissions.SEND_MESSAGES):
      return await self.send(self.States.SEND_PERMISSION_REQUIRED, ephemeral=True)

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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

    current_roles = []
    if schedule.manager_roles:
      for role_id in schedule.manager_role_objects:
        if role := await self.ctx.guild.fetch_role(role_id):
          current_roles.append(role)

    return await self.send(
      self.States.SELECT_ROLES,
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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await assert_user_permissions(
      self.ctx, Permissions.ADMINISTRATOR,
      "Server admin"
    )

    schedule_id = int(CustomID.get_id_from(self.ctx))
    schedule = await Schedule.fetch_by_id(schedule_id, guild=self.ctx.guild.id)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(f"@{schedule_id}")

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
  state: "AddMessage.States"
  data: "AddMessage.Data"
  schedule: Schedule
  schedule_message: ScheduleMessage

  class States(StrEnum):
    SUCCESS = "schedule_message_add_success"

  @define(slots=False)
  class Data(AsDict):
    schedule_title: str
    guild_name: str
    message: str
    number: str
    tags: Optional[str] = None


  async def prompt_from_button(self):
    return await self.prompt(CustomID.get_id_from(self.ctx))


  async def prompt(self, schedule_key: str):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(schedule_key)
  
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


  async def run_from_prompt(self, message: str, tags: Optional[str] = None):
    return await self.run(CustomID.get_id_from(self.ctx), message, tags)


  async def run(self, schedule_key: str, message: str, tags: Optional[str] = None):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
    if not schedule:
      return await Errors.create(self.ctx).schedule_not_found(schedule_key)

    # Actual addition goes here
    if schedule.type == ScheduleTypes.QUEUE:
      number = str(schedule.current_number + 1)
    else:
      number = "???"

    self.schedule_message = schedule.create_message(self.caller_id, message)
    if len(schedule.assign(self.schedule_message)) >= 2000:
      return await Errors.create(self.ctx).message_too_long()
    if tags:
      tags = re.sub(r"[\s]+", " ", tags).strip().lower()
      self.schedule_message.tags = " ".join(sorted(set(tags.split())))

    self.data = self.Data(
      schedule_title=escape_text(schedule.title),
      guild_name=self.ctx.guild.name,
      message=message,
      number=number,
      tags=self.schedule_message.tags
    )
    await self.send_commit(self.States.SUCCESS)


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
    schedule_title: str
    guild_name: str
    message: str
    number: str
    tags: Optional[str] = None


  async def prompt(self):
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()

    message_id = int(CustomID.get_id_from(self.ctx))
    message = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message:
      return await Errors.create(self.ctx).message_not_found()

    schedule = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")
    if not schedule:
      return await Errors.create(self.ctx).message_not_found()

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
    if not self.ctx.guild:
      return await Errors.create(self.ctx).not_in_guild()
    await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message_object = await ScheduleMessage.fetch(message_id, guild=self.ctx.guild.id)
    if not message_object:
      return await Errors.create(self.ctx).message_not_found()

    schedule = await check_fetch_schedule(self.ctx, f"{message_object.schedule_id}")
    if not schedule:
      return await Errors.create(self.ctx).message_not_found()

    message_object.message = message
    if tags:
      tags = re.sub(r"[\s]+", " ", tags).strip().lower()
      message_object.tags = " ".join(sorted(set(tags.split())))
    else:
      message_object.tags = None

    if len(schedule.assign(message_object)) > 2000:
      return await Errors.create(self.ctx).message_too_long()

    self.schedule_message = message_object
    self.data = self.Data(
      schedule_title=escape_text(schedule.title),
      guild_name=self.ctx.guild.name,
      message=self.schedule_message.message,
      number=self.schedule_message.number_s,
      tags=self.schedule_message.tags
    )

    return await self.send_commit(self.States.SUCCESS, other_data=message_object.asdict())


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.update_modify(session, self.ctx.author.id)