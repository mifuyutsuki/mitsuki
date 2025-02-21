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


class ConfigureSchedule(WriterCommand):
  class Templates(StrEnum):
    # Configure Schedule (Select)
    MENU    = "schedule_configure"
    CHANNEL = "schedule_configure_select_channel"
    ROLES   = "schedule_configure_select_roles"
    ROUTINE = "schedule_configure_select_routine" # Future

    # Configure Schedule (Response)
    TITLE_SUCCESS   = "schedule_configure_edit_title_success"
    FORMAT_SUCCESS  = "schedule_configure_edit_format_success"
    ROUTINE_SUCCESS = "schedule_configure_edit_routine_success"

    # Configure Schedule (Errors)
    ERROR_NOT_READY                = "schedule_configure_not_ready"
    ERROR_TITLE_ALREADY_EXISTS     = "schedule_configure_title_already_exists"
    ERROR_SEND_PERMISSION_REQUIRED = "schedule_configure_requires_send_permissions"
    ERROR_PIN_PERMISSION_REQUIRED  = "schedule_configure_requires_pin_permissions"


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
      self.Templates.MENU,
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
      return await self.send(self.Templates.TITLE_SUCCESS)

    # Duplicate check
    guild_schedules = await Schedule.fetch_many(guild=self.ctx.guild.id)
    if title in (s.title for s in guild_schedules):
      return await self.send(self.Templates.ERROR_TITLE_ALREADY_EXISTS)

    schedule.title = title

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(self.Templates.TITLE_SUCCESS)


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
      return await self.send(self.Templates.FORMAT_SUCCESS)

    schedule.format = format

    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    return await self.send(self.Templates.FORMAT_SUCCESS)


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
      return await self.send(self.Templates.ROUTINE_SUCCESS, other_data={"next_fire_f": next_fire})

    schedule.post_routine = f"{minute} {hour} * * *"
    async with new_session() as session:
      await schedule.update_modify(session, self.ctx.author.id)
      await session.commit()

    next_fire = f"<t:{int(schedule.cron().next(float))}:f>"
    return await self.send(self.Templates.ROUTINE_SUCCESS, other_data={"next_fire_f": next_fire})


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
      return await self.send(self.Templates.ERROR_NOT_READY, ephemeral=True)
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
      return await self.send(self.Templates.ERROR_PIN_PERMISSION_REQUIRED, ephemeral=True)

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
      self.Templates.CHANNEL,
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
      return await self.send(self.Templates.ERROR_SEND_PERMISSION_REQUIRED, ephemeral=True)

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
      self.Templates.ROLES,
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