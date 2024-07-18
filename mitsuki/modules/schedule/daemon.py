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

from mitsuki import logger
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
    self.task     = Task(self.post_task(bot, schedule), CronTrigger(schedule.post_routine))


  @property
  def running(self):
    return self.task.running


  def start(self):
    if not self.running:
      self.task.start()
      logger.info(f"Schedule Daemon | Started schedule '{self.schedule.title}' in {self.schedule.guild}")


  def stop(self):
    if self.running:
      self.task.stop()
      logger.info(f"Schedule Daemon | Stopped schedule '{self.schedule.title}' in {self.schedule.guild}")


  @staticmethod
  def post_task(bot: Client, schedule: Schedule):
    async def post():
      # Validation: schedule is active and valid
      if not schedule.active or not await schedule.is_valid():
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
      if schedule.current_pin:
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
        logger.info(f"Schedule Daemon | Posted '{schedule.title}' {number} in {schedule.guild}")
      elif formatted_message:
        logger.info(f"Schedule Daemon | Posted '{schedule.title}' in {schedule.guild}")
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
      if not schedule.active or not await schedule.is_valid():
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
    if not schedule or not await schedule.is_valid():
      raise ValueError("Schedule not ready or doesn't exist")

    if active_schedule := self.active_schedules.get(schedule.title):
      if active_schedule.running:
        active_schedule.stop()
      self.active_schedules.pop(schedule.title)

    task = DaemonTask(self.bot, schedule)
    task.start()
    self.active_schedules[schedule.title] = task
    logger.info(f"Schedule Daemon | Activated schedule '{schedule.title}' in {schedule.guild}")


  async def deactivate(self, schedule: Union[Schedule, str]):
    schedule_title = schedule if isinstance(schedule, str) else schedule.title
    if post_task := self.active_schedules.get(schedule_title):
      if post_task.running:
        post_task.stop()
      self.active_schedules.pop(schedule_title)