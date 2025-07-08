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


def banner_link(id: ipy.Snowflake, hash: Optional[str] = None):
  if not hash:
    return None
  return f"https://cdn.discordapp.com/banners/{id}/{hash}.webp?size=4096&animated=true"


class ServerInfo(libcmd.ReaderCommand):
  class Templates(StrEnum):
    INFO = "server_info_info"


  async def check(self):
    await checks.assert_in_guild(self.ctx)


  def _components(self, emoji_count: int, sticker_count: int, icon_url: Optional[str] = None):
    components = [
      ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Emojis",
        custom_id=customids.SERVER_EMOJIS_STATIC.id(self.ctx.guild_id),
        disabled=emoji_count == 0
      ),
      ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Emojis (animated)",
        custom_id=customids.SERVER_EMOJIS_ANIMATED.id(self.ctx.guild_id),
        disabled=emoji_count == 0
      ),
      # ipy.Button(
      #   style=ipy.ButtonStyle.BLURPLE,
      #   emoji=settings.emoji.gallery,
      #   label="Stickers",
      #   custom_id=customids.SERVER_STICKERS.id(self.ctx.guild_id),
      #   disabled=sticker_count == 0
      # ),
    ]
    if icon_url:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Icon",
        url=icon_url,
      ))
    return components


  async def run(self):
    await self.defer(ephemeral=False)
    await self.check()

    # This should never be None due to above checks
    guild: ipy.Guild = self.ctx.guild
  
    owner = await guild.fetch_owner()
    emojis = await guild.fetch_all_custom_emojis()
    stickers = await guild.fetch_all_custom_stickers()

    info = {
      "guild_id": guild.id,
      "guild_name": guild.name,
      "guild_name_esc": utils.escape_text(guild.name),
      "guild_description": guild.description or "No description set",
      "guild_description_esc": utils.escape_text(guild.description or "No description set"),
      "guild_created_at_f": guild.created_at.format("f"),
      "guild_icon_url": guild.icon.as_url() if guild.icon else None,
      "guild_banner_url": banner_link(guild.banner) or None,
      "guild_owner": owner.tag,
      "guild_owner_mention": owner.mention,
      "guild_boost_level": guild.premium_tier or 0,
      "guild_boost_count": guild.premium_subscription_count,
      "guild_emoji_limit": guild.emoji_limit,
      "guild_emoji_count": len(emojis),
      "guild_emoji_static_count": len([e for e in emojis if not e.animated]),
      "guild_emoji_animated_count": len([e for e in emojis if e.animated]),
      "guild_sticker_limit": guild.sticker_limit,
      "guild_sticker_count": len(stickers),
      "guild_role_count": len(guild.roles),
    }

    components = self._components(
      len(emojis), len(stickers), guild.icon.as_url() if guild.icon else None
    )

    await self.send(self.Templates.INFO, components=components, other_data=info)