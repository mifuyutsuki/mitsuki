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
from mitsuki.lib.view import (
  View,
  SectionPaginatorMixin,
  SectionPaginatorContentPlaceholder,
  PaginatorNavPlaceholder,
)

from .. import customids


@attrs.define(slots=False)
class ServerEmojiView(SectionPaginatorMixin, View):
  guild: ipy.Guild
  emojis: list[ipy.CustomEmoji]
  sort: str
  animated: bool = False
  entries_per_page: int = 5


  def get_context(self):
    return {
      "guild_name": self.guild.name,
      "guild_name_esc": escape_text(self.guild.name),
      "guild_boost_level": self.guild.premium_tier or 0,
      "guild_boost_count": self.guild.premium_subscription_count,
      "guild_emoji_count": len(self.emojis),
      "guild_emoji_limit": self.guild.emoji_limit,
      "guild_avatar_url": self.guild.icon.as_url() if self.guild.icon else "-",
      "view_mode": "Animated" if self.animated else "Static",
    }


  def get_pages_context(self):
    return [
      {
        "emoji_id": e.id,
        "emoji_name": e.name,
        "emoji_url": e.url,
        "emoji_mention": e if e.available else get_emoji(AppEmoji.TIME),
        "emoji_created_at_f": e.id.created_at.format("f"),
        "emoji_created_at_r": e.id.created_at.format("R"),
        "emoji_availability": "" if e.available else "— *Unavailable*",
      }
      for e in self.emojis
    ]


  def section(self):
    return [
      ipy.TextDisplayComponent(
        "### ${emoji_mention} [${emoji_name}](<${emoji_url}>)\n"
        "`${emoji_id}` · Created at ${emoji_created_at_f} ${emoji_availability}"
      ),
    ]


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("# Emoji List: ${view_mode} (${page}/${pages})"),
            ipy.TextDisplayComponent(
              "**${guild_emoji_count}**/${guild_emoji_limit} available (Level ${guild_boost_level})"
            )
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${guild_avatar_url}"))
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# {}: /server emoji".format(self.caller.tag)
        ),
      ),
      PaginatorNavPlaceholder(),
    ]


  def components_on_empty(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("# Emoji List: ${view_mode} (${page}/${pages})"),
            ipy.TextDisplayComponent(
              "**{${guild_emoji_count}}**/${guild_emoji_limit} available (Level ${guild_boost_level})"
            )
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${guild_avatar_url}"))
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("This server has no emoji of this type."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /server emoji".format(self.caller.tag)
        ),
      ),
    ]