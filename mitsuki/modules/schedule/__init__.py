# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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

from mitsuki import init_event

from .daemon import daemon
from .customids import CustomIDs
from .commands import *


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
    return await ManageSchedules.create(ctx).list()

  @component_callback(CustomIDs.SCHEDULE_MANAGE)
  async def schedule_manage_btn(self, ctx: ComponentContext):
    return await ManageSchedules.create(ctx).list()

  @component_callback(CustomIDs.SCHEDULE_VIEW.select())
  async def schedule_view_select(self, ctx: ComponentContext):
    return await ManageSchedules.create(ctx).view(ctx.values[0])

  @component_callback(CustomIDs.SCHEDULE_VIEW.string_id_pattern())
  async def schedule_view_btn(self, ctx: ComponentContext):
    return await ManageSchedules.create(ctx).view_from_button()

  # ===========================================================================
  # Create Schedule
  # ===========================================================================

  @component_callback(CustomIDs.SCHEDULE_CREATE.prompt())
  async def create_btn(self, ctx: ComponentContext):
    return await CreateSchedule.create(ctx).prompt()

  @modal_callback(CustomIDs.SCHEDULE_CREATE.response())
  async def create_response(self, ctx: ModalContext, title: str):
    return await CreateSchedule.create(ctx).response(title)

  # ===========================================================================
  # Configure Schedule
  # ===========================================================================

  @component_callback(CustomIDs.CONFIGURE.numeric_id_pattern())
  async def configure_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).main()

  @component_callback(CustomIDs.CONFIGURE_TITLE.prompt().numeric_id_pattern())
  async def configure_title_prompt(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).prompt_title()

  @modal_callback(CustomIDs.CONFIGURE_TITLE.response().numeric_id_pattern())
  async def configure_title_response(self, ctx: ModalContext, title: str):
    return await ConfigureSchedule.create(ctx).set_title(title)

  @component_callback(CustomIDs.CONFIGURE_FORMAT.prompt().numeric_id_pattern())
  async def configure_format_prompt(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).prompt_format()

  @modal_callback(CustomIDs.CONFIGURE_FORMAT.response().numeric_id_pattern())
  async def configure_format_response(self, ctx: ModalContext, format: str):
    return await ConfigureSchedule.create(ctx).set_format(format)

  @component_callback(CustomIDs.CONFIGURE_ROUTINE.prompt().numeric_id_pattern())
  async def configure_routine_prompt(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).prompt_routine()

  @modal_callback(CustomIDs.CONFIGURE_ROUTINE.response().numeric_id_pattern())
  async def configure_routine_response(self, ctx: ModalContext, format: str):
    return await ConfigureSchedule.create(ctx).set_routine(format)

  @component_callback(CustomIDs.CONFIGURE_ACTIVE.numeric_id_pattern())
  async def configure_active_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).toggle_active()

  @component_callback(CustomIDs.CONFIGURE_PIN.numeric_id_pattern())
  async def configure_pin_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).toggle_pin()

  @component_callback(CustomIDs.CONFIGURE_DISCOVERABLE.numeric_id_pattern())
  async def configure_discovery_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).toggle_discoverable()

  @component_callback(CustomIDs.CONFIGURE_CHANNEL.prompt().numeric_id_pattern())
  async def configure_channel_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).select_channel()

  @component_callback(CustomIDs.CONFIGURE_CHANNEL.select().numeric_id_pattern())
  async def configure_channel_select(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).set_channel(ctx.values[0])

  @component_callback(CustomIDs.CONFIGURE_ROLES.prompt().numeric_id_pattern())
  async def configure_roles_btn(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).select_roles()

  @component_callback(CustomIDs.CONFIGURE_ROLES.select().numeric_id_pattern())
  async def configure_roles_select(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).set_roles(ctx.values)

  @component_callback(CustomIDs.CONFIGURE_ROLES_CLEAR.numeric_id_pattern())
  async def configure_roles_clear(self, ctx: ComponentContext):
    return await ConfigureSchedule.create(ctx).set_roles([])

  # ===========================================================================
  # Manage Messages
  # ===========================================================================

  @component_callback(CustomIDs.MESSAGE_LIST.string_id_pattern())
  async def message_manage_btn(self, ctx: ComponentContext):
    return await ManageMessages.create(ctx).list_from_button()

  @component_callback(CustomIDs.MESSAGE_LIST_BACKLOG.string_id_pattern())
  async def message_manage_backlog_btn(self, ctx: ComponentContext):
    return await ManageMessages.create(ctx).list_backlog_from_button()

  @component_callback(CustomIDs.MESSAGE_LIST_POSTED.string_id_pattern())
  async def message_manage_posted_btn(self, ctx: ComponentContext):
    return await ManageMessages.create(ctx).list_posted_from_button()

  @component_callback(CustomIDs.MESSAGE_VIEW.string_id_pattern())
  async def message_manage_view_btn(self, ctx: ComponentContext):
    return await ManageMessages.create(ctx).view_from_button()

  # ===========================================================================
  # Add Message
  # ===========================================================================

  @component_callback(CustomIDs.MESSAGE_ADD.prompt().string_id_pattern())
  async def message_add_btn(self, ctx: ComponentContext):
    return await AddMessage.create(ctx).prompt_from_button()

  @modal_callback(CustomIDs.MESSAGE_ADD.response().string_id_pattern())
  async def message_add_response(self, ctx: ModalContext, message: str, tags: Optional[str] = None):
    return await AddMessage.create(ctx).response_from_prompt(message, tags)

  # ===========================================================================
  # Edit Message
  # ===========================================================================

  @component_callback(CustomIDs.MESSAGE_EDIT.prompt().string_id_pattern())
  async def message_edit_btn(self, ctx: ComponentContext):
    return await EditMessage.create(ctx).prompt()

  @modal_callback(CustomIDs.MESSAGE_EDIT.response().string_id_pattern())
  async def message_edit_response(self, ctx: ModalContext, message: str, tags: Optional[str] = None):
    return await EditMessage.create(ctx).response(message, tags)

  # ===========================================================================
  # Reorder Message
  # ===========================================================================

  @component_callback(CustomIDs.MESSAGE_REORDER.string_id_pattern())
  async def message_reorder_menu_btn(self, ctx: ComponentContext):
    return await ReorderMessage.create(ctx).select()

  @component_callback(CustomIDs.MESSAGE_REORDER_FRONT.string_id_pattern())
  async def message_reorder_front_btn(self, ctx: ComponentContext):
    return await ReorderMessage.create(ctx).to_front()

  @component_callback(CustomIDs.MESSAGE_REORDER_BACK.string_id_pattern())
  async def message_reorder_back_btn(self, ctx: ComponentContext):
    return await ReorderMessage.create(ctx).to_back()

  @component_callback(CustomIDs.MESSAGE_REORDER.prompt().string_id_pattern())
  async def message_reorder_prompt_btn(self, ctx: ComponentContext):
    return await ReorderMessage.create(ctx).prompt()

  @modal_callback(CustomIDs.MESSAGE_REORDER.response().string_id_pattern())
  async def message_reorder_response_btn(self, ctx: ModalContext, number: str):
    return await ReorderMessage.create(ctx).response(number)

  # ===========================================================================
  # Delete Message
  # ===========================================================================

  @component_callback(CustomIDs.MESSAGE_DELETE.confirm().string_id_pattern())
  async def message_delete_confirm(self, ctx: ComponentContext):
    return await DeleteMessage.create(ctx).confirm()

  @component_callback(CustomIDs.MESSAGE_DELETE.string_id_pattern())
  async def message_delete_run(self, ctx: ComponentContext):
    return await DeleteMessage.create(ctx).run()