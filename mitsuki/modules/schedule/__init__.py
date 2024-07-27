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

  @component_callback(commands.CustomIDs.SCHEDULE_CREATE.prompt())
  async def create_btn(self, ctx: ComponentContext):
    return await commands.CreateSchedule.create(ctx).prompt()

  @modal_callback(commands.CustomIDs.SCHEDULE_CREATE.response())
  async def create_response(self, ctx: ModalContext, title: str):
    return await commands.CreateSchedule.create(ctx).run(title)

  # ===========================================================================
  # Configure Schedule
  # ===========================================================================

  @component_callback(commands.CustomIDs.CONFIGURE.numeric_id_pattern())
  async def configure_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).main()

  @component_callback(commands.CustomIDs.CONFIGURE_TITLE.prompt().numeric_id_pattern())
  async def configure_title_prompt(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).prompt_title()

  @modal_callback(commands.CustomIDs.CONFIGURE_TITLE.response().numeric_id_pattern())
  async def configure_title_response(self, ctx: ModalContext, title: str):
    return await commands.ConfigureSchedule.create(ctx).set_title(title)

  @component_callback(commands.CustomIDs.CONFIGURE_FORMAT.prompt().numeric_id_pattern())
  async def configure_format_prompt(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).prompt_format()

  @modal_callback(commands.CustomIDs.CONFIGURE_FORMAT.response().numeric_id_pattern())
  async def configure_format_response(self, ctx: ModalContext, format: str):
    return await commands.ConfigureSchedule.create(ctx).set_format(format)

  @component_callback(commands.CustomIDs.CONFIGURE_ROUTINE.prompt().numeric_id_pattern())
  async def configure_routine_prompt(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).prompt_routine()

  @modal_callback(commands.CustomIDs.CONFIGURE_ROUTINE.response().numeric_id_pattern())
  async def configure_routine_response(self, ctx: ModalContext, format: str):
    return await commands.ConfigureSchedule.create(ctx).set_routine(format)

  @component_callback(commands.CustomIDs.CONFIGURE_ACTIVE.numeric_id_pattern())
  async def configure_active_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).toggle_active()

  @component_callback(commands.CustomIDs.CONFIGURE_PIN.numeric_id_pattern())
  async def configure_pin_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).toggle_pin()

  @component_callback(commands.CustomIDs.CONFIGURE_DISCOVERABLE.numeric_id_pattern())
  async def configure_discovery_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).toggle_discoverable()

  @component_callback(commands.CustomIDs.CONFIGURE_CHANNEL.prompt().numeric_id_pattern())
  async def configure_channel_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).select_channel()

  @component_callback(commands.CustomIDs.CONFIGURE_CHANNEL.select().numeric_id_pattern())
  async def configure_channel_select(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).set_channel(ctx.values[0])

  @component_callback(commands.CustomIDs.CONFIGURE_ROLES.prompt().numeric_id_pattern())
  async def configure_roles_btn(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).select_roles()

  @component_callback(commands.CustomIDs.CONFIGURE_ROLES.select().numeric_id_pattern())
  async def configure_roles_select(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).set_roles(ctx.values)

  @component_callback(commands.CustomIDs.CONFIGURE_ROLES_CLEAR.numeric_id_pattern())
  async def configure_roles_clear(self, ctx: ComponentContext):
    return await commands.ConfigureSchedule.create(ctx).set_roles([])

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
  # Delete Message
  # ===========================================================================

  @component_callback(commands.CustomIDs.MESSAGE_DELETE.confirm().string_id_pattern())
  async def message_delete_confirm(self, ctx: ComponentContext):
    return await commands.DeleteMessage.create(ctx).confirm()

  @component_callback(commands.CustomIDs.MESSAGE_DELETE.string_id_pattern())
  async def message_delete_run(self, ctx: ComponentContext):
    return await commands.DeleteMessage.create(ctx).run()