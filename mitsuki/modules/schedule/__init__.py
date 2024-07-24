# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import (
  AllowedMentions,
  AutocompleteContext,
  Extension,
  slash_command,
  slash_option,
  slash_default_member_permission,
  SlashContext,
  SlashCommandChoice,
  StringSelectMenu,
  ContextType,
  component_callback,
  ComponentContext,
  modal_callback,
  ModalContext,
  OptionType,
  BaseUser,
  User,
  Member,
  Permissions,
  check,
  is_owner,
  auto_defer,
  listen,
  cooldown,
  Buckets,
  Task,
  CronTrigger,
)
from interactions.api.events import Startup
from typing import Optional, Dict
from string import Template

from mitsuki import init_event, bot
from mitsuki.utils import UserDenied

from .userdata import Schedule, Message
from .daemon import daemon
from . import commands


class ScheduleModule(Extension):
  @listen(Startup)
  async def on_startup(self):
    await init_event.wait()
    await daemon.init()

  @slash_command(
    name="schedule",
    description="Message scheduler",
    contexts=[ContextType.GUILD],
  )
  async def schedule_cmd(self, ctx: SlashContext):
    pass

  # ===========================================================================
  # Manage Schedule
  # ===========================================================================

  @schedule_cmd.subcommand(
    sub_cmd_name="manage",
    sub_cmd_description="Manage Schedules"
  )
  async def schedule_manage_cmd(self, ctx: SlashContext):
    return await commands.ManageSchedules.create(ctx).list()

  @component_callback(commands.CustomIDs.SCHEDULE_MANAGE)
  async def schedule_manage_btn(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).list()

  @component_callback(commands.CustomIDs.SCHEDULE_VIEW.select())
  async def schedule_view_select(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).view(ctx.values[0])

  @component_callback(commands.CustomIDs.SCHEDULE_VIEW.string_id_pattern())
  async def schedule_view_btn(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).view_from_button()

  # ===========================================================================
  # Create Schedule
  # ===========================================================================

  @schedule_cmd.subcommand(
    sub_cmd_name="create",
    sub_cmd_description="Create a Schedule"
  )
  @slash_option(
    name="title",
    description="Schedule name",
    opt_type=OptionType.STRING,
    required=True,
    min_length=3,
  )
  async def create_cmd(self, ctx: SlashContext, title: str):
    return await commands.CreateSchedule.create(ctx).run(title)

  @component_callback(commands.CustomIDs.SCHEDULE_CREATE.prompt())
  async def create_btn(self, ctx: ComponentContext):
    return await commands.CreateSchedule.create(ctx).prompt()

  @modal_callback(commands.CustomIDs.SCHEDULE_CREATE.response())
  async def create_response(self, ctx: ModalContext, title: str):
    return await commands.CreateSchedule.create(ctx).run(title)

  # ===========================================================================
  # Configure Schedule (FUTURE)
  # ===========================================================================

  # ===========================================================================
  # Manage Messages
  # ===========================================================================

  @component_callback(commands.CustomIDs.MESSAGE_LIST.string_id_pattern())
  async def message_manage_btn(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).list_from_button()

  @component_callback(commands.CustomIDs.MESSAGE_VIEW.string_id_pattern())
  async def message_manage_view_btn(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).view_from_button()

  # ===========================================================================
  # Add Message
  # ===========================================================================

  @schedule_cmd.subcommand(
    sub_cmd_name="add",
    sub_cmd_description="Add a message to a Schedule"
  )
  @slash_option(
    name="schedule",
    description="Target Schedule name",
    opt_type=OptionType.STRING,
    required=True,
    min_length=1,
  )
  async def message_add_cmd(self, ctx: SlashContext, schedule: str):
    return await commands.AddMessage.create(ctx).prompt(schedule)

  @component_callback(commands.CustomIDs.MESSAGE_ADD.prompt().string_id_pattern())
  async def message_add_btn(self, ctx: ComponentContext):
    return await commands.AddMessage.create(ctx).prompt_from_button()

  @modal_callback(commands.CustomIDs.MESSAGE_ADD.response().string_id_pattern())
  async def message_add_response(self, ctx: ModalContext, message: str, tags: Optional[str] = None):
    return await commands.AddMessage.create(ctx).run_from_prompt(message, tags)

  # ===========================================================================
  # Edit Message
  # ===========================================================================

  @component_callback(commands.CustomIDs.MESSAGE_EDIT.prompt().string_id_pattern())
  async def message_edit_btn(self, ctx: ComponentContext):
    return await commands.EditMessage.create(ctx).prompt()

  @modal_callback(commands.CustomIDs.MESSAGE_EDIT.response().string_id_pattern())
  async def message_edit_response(self, ctx: ModalContext, message: str, tags: Optional[str] = None):
    return await commands.EditMessage.create(ctx).response(message, tags)

  # ===========================================================================
  # Delete Message (FUTURE)
  # ===========================================================================

  # @component_callback(commands.CustomIDs.MESSAGE_DELETE.confirm().string_id_pattern())

  # @component_callback(commands.CustomIDs.MESSAGE_DELETE.string_id_pattern())