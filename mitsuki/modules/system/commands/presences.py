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

from typing import Optional
from enum import StrEnum
from interactions.client.errors import HTTPException

from mitsuki import utils, settings
from mitsuki.settings2 import Settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks


from .. import customids, api


class SystemPresences(libcmd.SelectionMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    LIST  = "system_presences"
    EMPTY = "system_presences_empty"


  async def check(self):
    await checks.assert_user_owner(self.ctx)


  def components(self):
    return [
      ipy.Button(
        style=ipy.ButtonStyle.GREEN,
        emoji=settings.emoji.new,
        label="Add",
        custom_id=customids.SYSTEM_PRESENCES_ADD.prompt(),
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=settings.emoji.refresh,
        label="Refresh",
        custom_id=customids.SYSTEM_PRESENCES,
      ),
    ]


  async def run(self):
    await self.check()
    await self.defer(ephemeral=True)

    presences = await api.Presence.fetch_all()
    data = {
      "total_presences": len(presences),
      "cycle_time": await Settings.get(Settings.StatusCycle),
    }

    if len(presences) == 0:
      await self.send(self.Templates.EMPTY, other_data=data, components=self.components())
      return

    self.field_data = presences
    self.selection_per_page = 10
    self.selection_values = [
      ipy.StringSelectOption(
        label=utils.truncate(presence.name, 100),
        value=str(presence.id),
      ) for presence in presences
    ]
    self.selection_placeholder = "Delete a presence..."
    await self.send_selection_multiline(self.Templates.LIST, other_data=data, extra_components=self.components())


  async def selection_callback(self, ctx: ipy.ComponentContext):
    pass