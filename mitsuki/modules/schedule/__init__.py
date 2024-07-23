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
from .daemon import Daemon
from . import commands

class ScheduleModule(Extension):
  daemon: Daemon

  @listen(Startup)
  async def on_startup(self):
    await init_event.wait()
    self.daemon = Daemon(self.bot)
    await self.daemon.init()

  # ===========================================================================
  # ===========================================================================

  @slash_command(
    name="schedule",
    description="Message scheduler",
    dm_permission=False
  )
  async def schedule_cmd(self, ctx: SlashContext):
    pass

  # ===========================================================================
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

  @component_callback(commands.CreateSchedule.SCHEDULE_CREATE_BUTTON)
  async def create_btn(self, ctx: ComponentContext):
    return await commands.CreateSchedule.create(ctx).prompt()

  @modal_callback(commands.CreateSchedule.SCHEDULE_CREATE_MODAL)
  async def create_response(self, ctx: ModalContext, title: str):
    return await commands.CreateSchedule.create(ctx).run(title)

  # ===========================================================================
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

  @component_callback(commands.AddMessage.MESSAGE_ADD_BUTTON_RE)
  async def message_add_btn(self, ctx: ComponentContext):
    return await commands.AddMessage.create(ctx).prompt_from_button(ctx.custom_id)

  @modal_callback(commands.AddMessage.MESSAGE_ADD_MODAL_RE)
  async def message_add_response(self, ctx: ModalContext, message: str):
    return await commands.AddMessage.create(ctx).run_from_prompt(ctx.custom_id, message)

  # ===========================================================================
  # ===========================================================================

  @schedule_cmd.subcommand(
    sub_cmd_name="manage",
    sub_cmd_description="Manage Schedules"
  )
  async def schedule_manage_cmd(self, ctx: SlashContext):
    return await commands.ManageSchedules.create(ctx).list()

  @component_callback(commands.ManageSchedules.SCHEDULE_MANAGE_BUTTON)
  async def schedule_manage_btn(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).list()

  @component_callback(commands.ManageSchedules.SCHEDULE_VIEW_SELECT)
  async def schedule_view_select(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).view(ctx.values[0])

  @component_callback(commands.ManageSchedules.SCHEDULE_VIEW_BUTTON_RE)
  async def schedule_view_btn(self, ctx: ComponentContext):
    return await commands.ManageSchedules.create(ctx).view_from_button(ctx.custom_id)

  # ===========================================================================
  # ===========================================================================

  @component_callback(commands.ManageMessages.LIST_BUTTON_RE)
  async def schedule_messages_btn(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).list_from_button(ctx.custom_id)

  @component_callback(commands.ManageMessages.LIST_REFRESH_RE)
  async def schedule_messages_refresh_btn(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).list_from_button(ctx.custom_id)

  @component_callback(commands.ManageMessages.VIEW_RE)
  async def schedule_messages_view_btn(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).view_from_button(ctx.custom_id)

  @component_callback(commands.ManageMessages.EDIT_PROMPT_RE)
  async def schedule_messages_edit_prompt(self, ctx: ComponentContext):
    return await commands.ManageMessages.create(ctx).edit_message_prompt(ctx.custom_id)

  @modal_callback(commands.ManageMessages.EDIT_MESSAGE_RE)
  async def schedule_messages_edit_response(self, ctx: ModalContext, message: str):
    return await commands.ManageMessages.create(ctx).edit_message_response(ctx.custom_id, message)

  # @component_callback(commands.ManageMessages.MESSAGES_DELETE_CONFIRM_BUTTON_RE)

  # @component_callback(commands.ManageMessages.MESSAGES_DELETE_BUTTON_RE)