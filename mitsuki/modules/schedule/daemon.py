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
from croniter import croniter
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
from contextlib import suppress

from mitsuki.lib.userdata import new_session
from mitsuki.lib.checks import has_bot_channel_permissions
from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes


class DaemonTask:
  def __init__(self, bot: Client, schedule: Schedule):
    self.bot      = bot
    self.schedule = schedule
    self.task     = Task(self.post_task(bot, schedule), CronTrigger(schedule.post_routine))


  @property
  def running(self):
    return self.task.running


  def start(self):
    if not self.running:
      self.task.start()


  def stop(self):
    if self.running:
      self.task.stop()


  @staticmethod
  def post_task(bot: Client, schedule: Schedule):
    async def post():
      if not await schedule.is_valid() or not schedule.active:
        return
      channel = await bot.fetch_channel(schedule.post_channel)
      if not channel:
        return

      if schedule.type == ScheduleTypes.ONE_MESSAGE:
        assigned_message = schedule.format
      else:
        message = await schedule.next()
        if not message:
          return
        assigned_message = schedule.assign(message)

      async with new_session() as session:
        try:
          current_pin = None
          if schedule.current_pin:
            current_pin = await channel.fetch_message(schedule.current_pin)

          if current_pin:
            with suppress(Exception):
              await current_pin.unpin()

          posted_message = await channel.send(assigned_message)
          if schedule.pin:
            await posted_message.pin()
          await message.add_posted_message(posted_message).update(session)

          schedule.last_fire = posted_message.timestamp.timestamp()
          await schedule.update(session)
        except Exception:
          await session.rollback()
          raise
        else:
          await session.commit()
    return post


class Daemon:
  active_schedules: Dict[str, DaemonTask] = {}

  def __init__(self, bot: Client):
    self.bot = bot


  async def init(self):
    active_schedules = await Schedule.fetch_many(active=True)
    if len(active_schedules) <= 0:
      return

    for schedule in active_schedules:
      if not await schedule.is_valid() or not schedule.active:
        continue

      # post unsent backlog
      if schedule.has_unsent():
        await DaemonTask.post_task(self.bot, schedule)()

      # post task
      task = DaemonTask(self.bot, schedule)
      task.start()
      self.active_schedules[schedule.title] = task


  async def activate(self, schedule: Union[Schedule, str]):
    if isinstance(schedule, str):
      schedule = await Schedule.fetch(schedule)
    if not await schedule.is_valid():
      raise ValueError("Schedule not ready or doesn't exist")

    if active_schedule := self.active_schedules.get(schedule.title):
      if active_schedule.running:
        return

    task = DaemonTask(self.bot, schedule)
    task.start()
    self.active_schedules[schedule.title] = task


  async def deactivate(self, schedule: Union[Schedule, str]):
    schedule_title = schedule if isinstance(schedule, str) else schedule.title
    if post_task := self.active_schedules.get(schedule_title):
      if post_task.running:
        post_task.stop()
      self.active_schedules.pop(schedule_title)