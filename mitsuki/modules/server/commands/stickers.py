# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

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
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks

from .. import customids, views


class ServerStickers(libcmd.MultifieldMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    STICKERS = "server_stickers_stickers"
    EMPTY = "server_stickers_empty"


  async def check(self):
    await checks.assert_in_guild(self.ctx)


  async def run(self):
    await self.check()
    await self.defer(ephemeral=False, edit_origin=False)

    guild = self.ctx.guild
    stickers = await guild.fetch_all_custom_stickers()
    stickers.sort(key=lambda e: e.id, reverse=True)
    stickers.sort(key=lambda e: e.available, reverse=True)

    await views.ServerStickersView(self.ctx, guild=guild, stickers=stickers).send(timeout=45, hide_on_timeout=True)