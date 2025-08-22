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
class ServerStickersView(SectionPaginatorMixin, View):
  guild: ipy.Guild
  stickers: list[ipy.Sticker]
  entries_per_page: int = 3


  def get_context(self):
    return {
      "guild_name": self.guild.name,
      "guild_name_esc": escape_text(self.guild.name),
      "guild_boost_level": self.guild.premium_tier or 0,
      "guild_boost_count": self.guild.premium_subscription_count,
      "guild_sticker_count": len(self.stickers),
      "guild_sticker_limit": self.guild.sticker_limit,
      "guild_avatar_url": self.guild.icon.as_url() if self.guild.icon else "-",
    }


  def get_pages_context(self):
    return [
      {
        "sticker_id": s.id,
        "sticker_name": s.name,
        "sticker_name_esc": escape_text(s.name),
        "sticker_tags": s.tags,
        "sticker_description": s.description or "No description set",
        "sticker_description_esc": escape_text(s.description or "No description set"),
        "sticker_url": "{}?size=4096&quality=lossless".format(s.url),
        "sticker_created_at_f": s.id.created_at.format("f"),
        "sticker_created_at_r": s.id.created_at.format("R"),
        "sticker_availability": "" if s.available else "*Unavailable*",
        "sticker_format": s.format_type.name,
      } for s in self.stickers
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[
          ipy.TextDisplayComponent(
            "## ${sticker_name_esc}\n"
            "> ${sticker_description_esc}\n"
            "ID: ${sticker_id} ${sticker_availability}\n"
            "${sticker_format} Created at ${sticker_created_at_f} - [**Link**](<${sticker_url}>)"
          ),
        ],
        accessory=ipy.ThumbnailComponent(
          ipy.UnfurledMediaItem("${sticker_url}")
        )
      )
    ]


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("# Sticker List (${page}/${pages})"),
            ipy.TextDisplayComponent(
              "**${guild_sticker_count}**/${guild_sticker_limit} available (Level ${guild_boost_level})"
            )
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${guild_avatar_url}"))
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# {}: /server stickers".format(self.caller.tag)
        )
      ),
      PaginatorNavPlaceholder(),
    ]


  def components_on_empty(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("# Sticker List (${page}/${pages})"),
            ipy.TextDisplayComponent(
              "**${guild_sticker_count}**/${guild_sticker_limit} available (Level ${guild_boost_level})"
            )
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${guild_avatar_url}"))
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("This server has no stickers."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /server stickers".format(self.caller.tag)
        )
      ),
    ]