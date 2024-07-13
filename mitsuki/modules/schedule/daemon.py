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
  Task,
  CronTrigger,
  Client,
  Permissions,
)
from attrs import define, field
from typing import Dict, Optional, Union
from croniter import croniter

from mitsuki.lib.userdata import new_session
from mitsuki.lib.checks import has_bot_channel_permissions
from .userdata import Schedule, Message as ScheduleMessage


class Daemon:
  active_schedules: Dict[str, Task] = {}

  def __init__(self, bot: Client):
    self.bot = bot


  async def init(self):
    active_crons = await Schedule.fetch_active_crons()
    if len(active_crons) > 0:
      for sched_title, sched_cron in active_crons.items():
        if not await self.is_valid_schedule(sched_title):
          continue
        task = Task(self.post_task(sched_title), CronTrigger(sched_cron))
        task.start()
        self.active_schedules[sched_title] = task


  async def activate(self, schedule_title: str):
    schedule = await Schedule.fetch(schedule_title)
    if not await self.is_valid_schedule(schedule):
      raise ValueError("Schedule not ready or doesn't exist")

    task = Task(self.post_task(schedule_title), CronTrigger(schedule.post_cron))
    task.start()
    self.active_schedules[schedule_title] = task


  async def deactivate(self, schedule_title: str):
    if post_task := self.active_schedules.get(schedule_title):
      if post_task.running:
        post_task.stop()
      self.active_schedules.pop(schedule_title)


  async def is_valid_schedule(self, schedule: Union[Schedule, str]):
    if isinstance(schedule, str):
      schedule = await Schedule.fetch(schedule)
    if not schedule:
      return False

    required_permissions = [Permissions.SEND_MESSAGES]
    if schedule.pin:
      required_permissions.append(Permissions.MANAGE_MESSAGES)

    return bool(
      schedule.channel
      and "${messages}" in schedule.format
      and await has_bot_channel_permissions(self.bot, schedule.channel, required_permissions)
    )


  async def post_task(self, schedule_title: str):
    async def wrapped():
      message = await ScheduleMessage.fetch_next_backlog(schedule_title)
      if not message:
        return

      channel = await self.bot.fetch_channel(message.channel)
      if not channel:
        return

      assigned_message = message.assign_to(message.schedule_object)
      async with new_session() as session:
        try:
          posted_message = await channel.send(assigned_message)
          if message.schedule_object.pin:
            await posted_message.pin()
          await message.add_posted_message(posted_message).update(session)
        except Exception:
          await session.rollback()
          raise
        else:
          await session.commit()

    return wrapped