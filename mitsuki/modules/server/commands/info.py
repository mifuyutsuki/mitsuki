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
import attrs

from typing import Optional
from enum import StrEnum
from interactions.client.errors import HTTPException

from mitsuki import utils, settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks
from mitsuki.lib import view as view

from .. import customids, views


def banner_link(id: ipy.Snowflake, hash: Optional[str] = None):
  if not hash:
    return None
  return f"https://cdn.discordapp.com/banners/{id}/{hash}.webp?size=4096&animated=true"


class ServerInfo(libcmd.ReaderCommand):
  class Templates(StrEnum):
    INFO = "server_info_info"


  async def check(self):
    await checks.assert_in_guild(self.ctx)


  async def run(self):
    await self.defer(ephemeral=False)
    await self.check()

    # This should never be None due to above checks
    guild: ipy.Guild = self.ctx.guild

    owner = await guild.fetch_owner()
    emojis = await guild.fetch_all_custom_emojis()
    stickers = await guild.fetch_all_custom_stickers()

    await views.ServerInfoView(
      self.ctx, guild=guild, owner=owner, emojis=emojis, stickers=stickers
    ).send(timeout=45, hide_on_timeout=True)