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

from typing import Optional
from enum import StrEnum
from interactions.client.errors import HTTPException

from mitsuki import utils, settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks
from mitsuki.lib import view as view

from .. import customids


def banner_link(id: ipy.Snowflake, hash: Optional[str] = None):
  if not hash:
    return None
  return f"https://cdn.discordapp.com/banners/{id}/{hash}.webp?size=4096&animated=true"


@attrs.define(slots=False)
class ServerInfoView(view.View):
  guild: ipy.Guild
  owner: ipy.Member
  emojis: list[ipy.CustomEmoji]
  stickers: list[ipy.Sticker]


  @property
  def static_emojis(self):
    return [e for e in self.emojis if not e.animated]


  @property
  def animated_emojis(self):
    return [e for e in self.emojis if e.animated]


  def buttons(self):
    components = []

    if len(self.static_emojis) > 0:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Emojis",
        custom_id=customids.SERVER_EMOJIS_STATIC.id(self.ctx.guild_id),
      ))

    if len(self.animated_emojis) > 0:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Animated Emojis",
        custom_id=customids.SERVER_EMOJIS_ANIMATED.id(self.ctx.guild_id),
      ))

    if len(self.stickers) > 0:
      components.append(
      ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.gallery,
        label="Stickers",
        custom_id=customids.SERVER_STICKERS.id(self.ctx.guild_id),
      ))

    if self.guild.icon:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Icon",
        url=self.guild.icon.as_url(),
      ))

    if self.guild.banner:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Banner",
        url=banner_link(self.guild.id, self.guild.banner),
      ))

    return components


  def components(self):
    components = []
    guild = self.guild

    if self.guild.banner:
      components.append(ipy.MediaGalleryComponent([
        ipy.MediaGalleryItem(
          ipy.UnfurledMediaItem(banner_link(self.guild.id, self.guild.banner))
        )
      ]))

    if self.guild.icon:
      components.append(ipy.SectionComponent(
        components=[
          ipy.TextDisplayComponent(
            "# ✦ {}".format(utils.escape_text(guild.name))
          ),
          ipy.TextDisplayComponent(
            "ID: {}\nCreated at {}\nOwned by {} ({})".format(
              self.guild.id, self.guild.created_at.format("f"), self.owner.tag, self.owner.mention
            )
          ),
        ],
        accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem(self.guild.icon.as_url()))
      ))
    else:
      components.append(ipy.TextDisplayComponent(
        "# ✦ {}\nID: {}\nCreated at {}\nOwned by {} ({})".format(
          utils.escape_text(self.guild.name), self.guild.id, self.guild.created_at.format("f"),
          self.owner.tag, self.owner.mention
        )
      ))

    components.append(ipy.SeparatorComponent(divider=True))

    if self.guild.description:
      components.append(ipy.TextDisplayComponent("> {0}".format(utils.escape_text(self.guild.description))))

    components.append(ipy.TextDisplayComponent("\n".join([
      "**Boosts:** {} (Level {})".format(self.guild.premium_subscription_count, self.guild.premium_tier or 0),
      "**Emoji:** {0}/{2} static, {1}/{2} animated".format(
        len(self.static_emojis), len(self.animated_emojis), self.guild.emoji_limit
      ),
      "**Stickers:** {}/{}".format(len(self.stickers), self.guild.sticker_limit),
    ])))

    components.append(ipy.SeparatorComponent(divider=True))
    components.append(ipy.TextDisplayComponent("-# {0}: /{1}".format(self.caller.tag, self.ctx.invoke_target)))

    return [ipy.ContainerComponent(*components), ipy.ActionRow(*self.buttons())]


class ServerInfo(libcmd.ReaderCommand):
  class Templates(StrEnum):
    INFO = "server_info_info"


  async def check(self):
    await checks.assert_in_guild(self.ctx)


  def _components(
    self, emoji_static_count: int, emoji_animated_count: int, sticker_count: int,
    icon_url: Optional[str] = None, banner_url: Optional[str] = None
  ):
    components = []
    if emoji_static_count > 0:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Emojis",
        custom_id=customids.SERVER_EMOJIS_STATIC.id(self.ctx.guild_id),
      ))
    if emoji_animated_count > 0:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.list,
        label="Animated Emojis",
        custom_id=customids.SERVER_EMOJIS_ANIMATED.id(self.ctx.guild_id),
      ))
    if sticker_count > 0:
      components.append(
      ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=settings.emoji.gallery,
        label="Stickers",
        custom_id=customids.SERVER_STICKERS.id(self.ctx.guild_id),
      ))
    if icon_url:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Icon",
        url=icon_url,
      ))
    if banner_url:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Banner",
        url=banner_url,
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

    icon = guild.icon.as_url() if guild.icon else None
    banner = banner_link(guild.id, guild.banner)
    e_static_count = len([e for e in emojis if not e.animated])
    e_animated_count = len([e for e in emojis if e.animated])

    info = {
      "guild_id": guild.id,
      "guild_name": guild.name,
      "guild_name_esc": utils.escape_text(guild.name),
      "guild_description": guild.description or "No description set",
      "guild_description_esc": utils.escape_text(guild.description or "No description set"),
      "guild_created_at_f": guild.created_at.format("f"),
      "guild_icon_url": icon,
      "guild_banner_url": banner,
      "guild_owner": owner.tag,
      "guild_owner_mention": owner.mention,
      "guild_boost_level": guild.premium_tier or 0,
      "guild_boost_count": guild.premium_subscription_count,
      "guild_emoji_limit": guild.emoji_limit,
      "guild_emoji_count": len(emojis),
      "guild_emoji_static_count": e_static_count,
      "guild_emoji_animated_count": e_animated_count,
      "guild_sticker_limit": guild.sticker_limit,
      "guild_sticker_count": len(stickers),
      "guild_role_count": len(guild.roles),
    }

    await ServerInfoView(
      self.ctx, guild=guild, owner=owner, emojis=emojis, stickers=stickers
    ).send(timeout=45, hide_on_timeout=True)

    # components = self._components(e_static_count, e_animated_count, len(stickers),
    #                               icon_url=icon, banner_url=banner)
    # await self.send(self.Templates.INFO, components=components, other_data=info)