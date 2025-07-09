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
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks

from .. import customids


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
    data = {
      "guild_name": guild.name,
      "guild_boost_level": guild.premium_tier or 0,
      "guild_boost_count": guild.premium_subscription_count,
      "guild_sticker_count": len(stickers),
      "guild_sticker_limit": guild.sticker_limit,
    }

    if len(stickers) == 0:
      await self.send(self.Templates.EMPTY, other_data=data)
      return

    stickers.sort(key=lambda e: e.id, reverse=True)
    stickers.sort(key=lambda e: e.available, reverse=True)

    self.field_data = [
      {
        "sticker_id": s.id,
        "sticker_name": s.name,
        "sticker_name_esc": utils.escape_text(s.name),
        "sticker_description": s.description or "No description set",
        "sticker_description_esc": utils.escape_text(s.description or "No description set"),
        "sticker_url": f"{s.url}?size=4096&quality=lossless",
        "sticker_created_at_f": s.id.created_at.format("f"),
        "sticker_created_at_r": s.id.created_at.format("R"),
        "sticker_available": "" if s.available else "(Unavailable)",
        "sticker_format": s.format_type.name,
      } for s in stickers
    ]

    await self.send_multipage(self.Templates.STICKERS, other_data=data, timeout=45)