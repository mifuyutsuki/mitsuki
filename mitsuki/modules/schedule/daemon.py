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
  CronTrigger as _CronTrigger,
  Client,
)
from interactions.client.errors import Forbidden, NotFound
from croniter import croniter
from typing import Dict, List, Optional, Union
from datetime import datetime

from mitsuki import bot, logger
from mitsuki.lib.userdata import new_session
from .userdata import Schedule, Message as ScheduleMessage, ScheduleTypes, timestamp_now


# Fix for double calls
class CronTrigger(_CronTrigger):
  def next_fire(self):
    return croniter(self.cron, self.last_call_time.astimezone(self.tz)).next(datetime)


class DaemonTask:
  def __init__(self, bot: Client, schedule: Schedule):
    self.bot      = bot
    self.schedule = schedule
    self.task     = self.create_task()


  @property
  def running(self):
    return self.task.running


  def start(self):
    if not self.running:
      self.task.start()
      logger.info(
        f"Schedule Daemon | Started schedule {self.schedule.id}: '{self.schedule.title}' "
        f"- Channel {self.schedule.post_channel} - Guild {self.schedule.guild}"
      )


  def stop(self):
    if self.running:
      self.task.stop()
      logger.info(
        f"Schedule Daemon | Stopped schedule {self.schedule.id}: '{self.schedule.title}' "
        f"- Channel {self.schedule.post_channel} - Guild {self.schedule.guild}"
      )


  def refresh(self, schedule: Schedule):
    if self.running():
      self.task.stop()
    self.schedule = schedule
    self.task     = self.create_task()
    self.task.start()
    logger.info(
      f"Schedule Daemon | Refreshed schedule {self.schedule.id}: '{self.schedule.title}' "
      f"- channel {self.schedule.post_channel} - guild {self.schedule.guild}"
    )


  def create_task(self):
    return Task(self.post_task(), CronTrigger(self.schedule.post_routine))


  def post_task(self):
    async def post():
      # Validation: schedule exists
      schedule = await Schedule.fetch_by_id(self.schedule.id)
      if not schedule:
        return
      self.schedule = schedule

      return await self.post(self.bot, self.schedule)
    return post


  @staticmethod
  async def post(bot: Client, schedule: Schedule, force: bool = False):
    # Validation: schedule is active unless force-posted
    if not force and not schedule.active:
      return

    # Validation: schedule is valid (channel exists, perms check, etc.)
    if not await schedule.is_valid():
      return

    # Validation: channel exists (also caught by is_valid())
    channel = await bot.fetch_channel(schedule.post_channel)
    if not channel:
      return

    # Processing: obtain formatted message
    message = None
    formatted_message = None
    if schedule.type == ScheduleTypes.ONE_MESSAGE:
      formatted_message = schedule.format
    elif message := await schedule.next():
      formatted_message = schedule.assign(message)
    is_ready = formatted_message is not None

    # Execution: Unpin current message
    if schedule.current_pin and is_ready:
      if current_pin := await channel.fetch_message(schedule.current_pin):
        try:
          if current_pin.pinned:
            await current_pin.unpin()
        except (Forbidden, NotFound):
          pass
        else:
          schedule.current_pin = None

    # Execution: Post current message
    posted_message = None
    if is_ready and formatted_message:
      posted_message = await channel.send(formatted_message)
      if schedule.pin and posted_message:
        try:
          await posted_message.pin()
        except (Forbidden, NotFound):
          pass
        else:
          schedule.current_pin = posted_message.id

    # Save: Update database
    schedule.last_fire = timestamp_now()
    async with new_session() as session:
      try:
        if is_ready and message and posted_message:
          schedule.posted_number += 1
          await message.add_posted_message(posted_message).update(session)
        await schedule.update(session)
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()

    # Log post
    if message and formatted_message:
      number = f"#{message.number}" if message.number else "#???"
      logger.info(
        f"Schedule Daemon | Posted '{schedule.title}' {number} "
        f"- Channel {schedule.post_channel} - Guild {schedule.guild}"
      )
    elif formatted_message:
      logger.info(
        f"Schedule Daemon | Posted '{schedule.title}' "
        f"- Channel {schedule.post_channel} - Guild {schedule.guild}"
      )


class Daemon:
  active_schedules: Dict[int, DaemonTask] = {}

  def __init__(self, bot: Client):
    self.bot = bot


  async def init(self):
    active_schedules = await Schedule.fetch_many(active=True)
    if len(active_schedules) <= 0:
      return

    for schedule in active_schedules:
      if not schedule.active or not await schedule.is_valid():
        continue

      # post unsent backlog
      if schedule.has_unsent():
        await DaemonTask.post(self.bot, schedule)

      # post task
      task = DaemonTask(self.bot, schedule)
      task.start()
      self.active_schedules[schedule.id] = task


  async def force_post(self, schedule: Union[Schedule, int]):
    if isinstance(schedule, int):
      schedule = await Schedule.fetch_by_id(schedule)
    if not schedule or not await schedule.is_valid():
      raise ValueError("Schedule not ready or doesn't exist")

    if schedule.has_unsent():
      await DaemonTask.post(self.bot, schedule, force=True)


  async def activate(self, schedule: Union[Schedule, int]):
    if isinstance(schedule, int):
      schedule = await Schedule.fetch_by_id(schedule)
    if not schedule or not await schedule.is_valid():
      raise ValueError("Schedule not ready or doesn't exist")

    if active_schedule := self.active_schedules.get(schedule.id):
      if active_schedule.running:
        active_schedule.stop()
      self.active_schedules.pop(schedule.id)

    task = DaemonTask(self.bot, schedule)
    task.start()
    self.active_schedules[schedule.id] = task


  async def deactivate(self, schedule: Union[Schedule, int]):
    schedule_id = schedule if isinstance(schedule, int) else schedule.id
    if post_task := self.active_schedules.get(schedule_id):
      if post_task.running:
        post_task.stop()
      self.active_schedules.pop(schedule_id)


  async def reactivate(self, schedule: Union[Schedule, int]):
    if isinstance(schedule, int):
      schedule = await Schedule.fetch_by_id(schedule)
    if not schedule or not await schedule.is_valid():
      raise ValueError("Schedule not ready or doesn't exist")

    if schedule_task := self.active_schedules.get(schedule.id):
      schedule_task.refresh(schedule)


daemon = Daemon(bot)