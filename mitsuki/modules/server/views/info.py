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

from mitsuki.utils import escape_text
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import View

from .. import customids


def banner_link(id: ipy.Snowflake, hash: Optional[str] = None):
  if not hash:
    return None
  return f"https://cdn.discordapp.com/banners/{id}/{hash}.webp?size=4096&animated=true"


@attrs.define(slots=False)
class ServerInfoView(View):
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
        emoji=get_emoji(AppEmoji.LIST),
        label="Emojis",
        custom_id=customids.SERVER_EMOJIS_STATIC.id(self.ctx.guild_id),
      ))

    if len(self.animated_emojis) > 0:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=get_emoji(AppEmoji.LIST),
        label="Animated Emojis",
        custom_id=customids.SERVER_EMOJIS_ANIMATED.id(self.ctx.guild_id),
      ))

    if len(self.stickers) > 0:
      components.append(
      ipy.Button(
        style=ipy.ButtonStyle.BLURPLE,
        emoji=get_emoji(AppEmoji.GALLERY),
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
            "# ✦ {}".format(escape_text(guild.name))
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
          escape_text(self.guild.name), self.guild.id, self.guild.created_at.format("f"),
          self.owner.tag, self.owner.mention
        )
      ))

    components.append(ipy.SeparatorComponent(divider=True))

    if self.guild.description:
      components.append(ipy.TextDisplayComponent("> {0}".format(escape_text(self.guild.description))))

    components.append(ipy.TextDisplayComponent("\n".join([
      "**Boosts:** {} (Level {})".format(self.guild.premium_subscription_count, self.guild.premium_tier or 0),
      "**Emoji:** {0}/{2} static, {1}/{2} animated".format(
        len(self.static_emojis), len(self.animated_emojis), self.guild.emoji_limit
      ),
      "**Stickers:** {}/{}".format(len(self.stickers), self.guild.sticker_limit),
    ])))

    components.append(ipy.SeparatorComponent(divider=True))
    components.append(ipy.TextDisplayComponent("-# {0}: /server info".format(self.caller.tag)))

    return [ipy.ContainerComponent(*components), ipy.ActionRow(*self.buttons())]