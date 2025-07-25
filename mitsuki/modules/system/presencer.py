# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.


import interactions as ipy
import attrs
import asyncio
import random

from typing import Optional

from mitsuki import settings
from mitsuki.settings2 import Settings
from mitsuki.lib.userdata import new_session

from . import api


@attrs.define()
class Presencer:
  bot: ipy.Client                  = attrs.field()
  presences: list[api.Presence]    = attrs.field(factory=list)
  cycle_time: Optional[int]        = attrs.field(default=None)
  _task: Optional[ipy.Task]        = attrs.field(default=None)
  _current: Optional[api.Presence] = attrs.field(default=None)
  _random: random.Random           = attrs.field(default=random.Random())


  @property
  def current(self):
    return self._current


  def get_next(self, prev: Optional[api.Presence] = None):
    if prev:
      ps = [p for p in self.presences if p.id != prev.id]
      if len(ps) == 0:
        return None
      return self._random.choice(ps)
    return self._random.choice(self.presences)


  async def init(self):
    # TODO: use new settings system (requires settings management commands)
    self.cycle_time = self.cycle_time or settings.mitsuki.status_cycle
    self.presences = await api.Presence.fetch_all()
    self._current = None

    if len(self.presences) == 0:
      await self.bot.change_presence(ipy.Status.ONLINE, activity=None)
    else:
      await self.start()


  async def start(self):
    self._task = ipy.Task(self.cycle, ipy.IntervalTrigger(seconds=max(60, self.cycle_time)))
    self._task.start()
    await self.cycle()


  async def cycle(self):
    presence = self.get_next(prev=self._current)
    if not presence:
      return

    await self.bot.change_presence(
      ipy.Status.ONLINE, activity=ipy.Activity(presence.name, ipy.ActivityType.PLAYING)
    )
    self._current = presence


  async def stop(self):
    if self._task and self._task.running:
      self._task.stop()
    self._task = None


  async def restart(self):
    await self.stop()
    await self.start()


  async def sync(self):
    self.presences = await api.Presence.fetch_all()

    if len(self.presences) == 0:
      # Presences list is empty, stop rotation
      self._current = None
      await self.bot.change_presence(ipy.Status.ONLINE, activity=None)
      await self.stop()

    elif self.current is None:
      # Presences list was empty, begin rotation
      await self.restart()

    elif self.current.id not in (p.id for p in self.presences):
      # Current presence is deleted, restart rotation
      await self.restart()


_presencer = None


def set_presencer(bot: ipy.Client, cycle_time: Optional[int] = None):
  global _presencer
  _presencer = Presencer(bot, cycle_time=cycle_time)


def presencer():
  global _presencer
  if not _presencer:
    raise RuntimeError("Presencer is uninitialized")
  return _presencer