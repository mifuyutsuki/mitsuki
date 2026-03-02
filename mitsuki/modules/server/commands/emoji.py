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


  async def run(self, animated: bool = False, sort: str = "name"):
    await self.check()
    await self.defer(ephemeral=False, edit_origin=False)

    guild = self.ctx.guild

    emojis = await guild.fetch_all_custom_emojis()
    if animated:
      emojis = [e for e in emojis if e.animated]
    else:
      emojis = [e for e in emojis if not e.animated]

    match sort:
      case "name":
        emojis.sort(key=lambda e: e.name)
      case "name-i":
        emojis.sort(key=lambda e: e.name.lower())
      case "date":
        emojis.sort(key=lambda e: e.id, reverse=True)
      case _:
        raise ValueError(f"Unexpected sort option: {sort}")
    emojis.sort(key=lambda e: e.available, reverse=True)

    await views.ServerEmojiView(
      self.ctx, guild=guild, emojis=emojis, sort=sort, animated=animated,
    ).send(timeout=45, hide_on_timeout=True)