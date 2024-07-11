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
from . import commands

class ScheduleModule(Extension):
  tasks: Dict[str, Task] = {}

  @listen(Startup)
  async def on_startup(self):
    await init_event.wait()

    # WIP

    # scheds = await Schedule.fetch_active_crons()
    # if len(scheds) > 1:
    #   for sched_title, sched_cron in scheds.items():
    #     task = Task(self.post_message_task(sched_title), CronTrigger(sched_cron))
    #     task.start()
    #     self.tasks[sched_title] = task

  async def post_message_task(self, schedule_title: str):
    async def wrapper():
      message, schedule = await Message.fetch_next_backlog(schedule_title)

      channel = await bot.fetch_channel(schedule.channel)
      assigned_message = Template(schedule.format).safe_substitute(**message.asdict())
      posted_message = await channel.send(content=assigned_message)

      message.add_posted_message(posted_message)

    return wrapper

  # ===========================================================================
  # ===========================================================================

  @slash_command(
    name="schedule",
    description="Message scheduler"
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
  async def schedule_create(self, ctx: SlashContext, title: str):
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
    min_length=3,
  )
  @slash_option(
    name="message",
    description="Schedule message content",
    opt_type=OptionType.STRING,
    required=True,
    min_length=3,
  )
  async def message_add(self, ctx: SlashContext, schedule: str, message: str):
    return await commands.AddMessage.create(ctx).run(schedule, message)

