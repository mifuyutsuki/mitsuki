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

from typing import Optional

from mitsuki import settings
from mitsuki.settings2 import Settings
from mitsuki.lib.userdata import new_session

from . import api


@attrs.define()
class Presencer:
  bot: ipy.Client               = attrs.field()
  presences: list[api.Presence] = attrs.field(factory=list)
  cycle_time: Optional[int]     = attrs.field(default=None)
  _task: Optional[ipy.Task]     = attrs.field(default=None)
  _prev: Optional[api.Presence] = attrs.field(default=None)


  async def cycle(self):
    presence = await api.Presence.fetch_next(prev=self._prev)
    if not presence:
      return

    await self.bot.change_presence(
      ipy.Status.ONLINE, activity=ipy.Activity(presence.name, ipy.ActivityType.PLAYING)
    )
    self._prev = presence


  async def init(self):
    # TODO: use new settings system (requires settings management commands)
    self.cycle_time = self.cycle_time or settings.mitsuki.status_cycle
    self.presences = await api.Presence.fetch_all()

    if len(self.presences) == 0:
      await self.bot.change_presence(ipy.Status.ONLINE, activity=None)
      return

    self._task = ipy.Task(self.cycle, ipy.IntervalTrigger(seconds=max(60, self.cycle_time)))
    self._task.start()
    await self.cycle()


  async def restart(self):
    if self._task and self._task.running:
      self._task.stop()
    self._task = None

    await self.init()


_presencer = None


def set_presencer(bot: ipy.Client):
  global _presencer
  _presencer = Presencer(bot)


def presencer():
  global _presencer
  if not _presencer:
    raise RuntimeError("Presencer is uninitialized")
  return _presencer