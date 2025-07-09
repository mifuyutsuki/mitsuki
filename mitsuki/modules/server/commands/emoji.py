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


class ServerEmoji(libcmd.MultifieldMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    EMOJI_STATIC = "server_emoji_static"
    EMOJI_ANIMATED = "server_emoji_animated"
    EMPTY = "server_emoji_empty"


  def components(self, from_animated: bool = False):
    components = []
    # if from_animated:
    #   components.append(ipy.Button(
    #     style=ipy.ButtonStyle.BLURPLE,
    #     label="View static",
    #     emoji=settings.emoji.list,
    #     custom_id=customids.SERVER_EMOJIS_STATIC.id(self.ctx.guild_id),
    #   ))
    # else:
    #   components.append(ipy.Button(
    #     style=ipy.ButtonStyle.BLURPLE,
    #     label="View animated",
    #     emoji=settings.emoji.list,
    #     custom_id=customids.SERVER_EMOJIS_ANIMATED.id(self.ctx.guild_id),
    #   ))
    # components.append(ipy.Button(
    #   style=ipy.ButtonStyle.BLURPLE,
    #   label="Stickers",
    #   emoji=settings.emoji.gallery,
    #   custom_id=customids.SERVER_STICKERS.id(self.ctx.guild_id),
    # ))
    # components.append(ipy.Button(
    #   style=ipy.ButtonStyle.BLURPLE,
    #   label="Server info",
    #   emoji=settings.emoji.back,
    #   custom_id=customids.SERVER_INFO.id(self.ctx.guild_id)
    # ))
    return components


  async def check(self):
    await checks.assert_in_guild(self.ctx)


  async def run(self, animated: bool = False):
    await self.check()
    await self.defer(ephemeral=False, edit_origin=False)

    guild = self.ctx.guild
    emojis = await guild.fetch_all_custom_emojis()
    data = {
      "guild_name": guild.name,
      "guild_boost_level": guild.premium_tier or 0,
      "guild_boost_count": guild.premium_subscription_count,
      "guild_emoji_count": 0,
      "guild_emoji_limit": guild.emoji_limit,
    }
    components = self.components(from_animated=animated)

    if animated:
      emojis = [e for e in emojis if e.animated]
    else:
      emojis = [e for e in emojis if not e.animated]

    if len(emojis) == 0:
      await self.send(self.Templates.EMPTY, other_data=data, components=components)
      return

    emojis.sort(key=lambda e: e.id, reverse=True)
    emojis.sort(key=lambda e: e.available, reverse=True)

    data |= {
      "guild_emoji_count": len(emojis),
    }

    self.field_data = [
      {
        "emoji_id": e.id,
        "emoji_name": e.name,
        "emoji_url": e.url,
        "emoji_mention": e if e.available else settings.emoji.time,
        "emoji_created_at_f": e.id.created_at.format("f"),
        "emoji_created_at_r": e.id.created_at.format("R"),
        "emoji_available": "" if e.available else "(Unavailable)",
      } for e in emojis
    ]

    await self.send_multifield(
      self.Templates.EMOJI_ANIMATED if animated else self.Templates.EMOJI_STATIC,
      other_data=data, per_page=6, timeout=45, extra_components=components
    )