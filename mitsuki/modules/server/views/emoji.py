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
  SectionPaginatorNavPlaceholder,
)

from .. import customids


@attrs.define(slots=False)
class ServerEmojiView(SectionPaginatorMixin, View):
  guild: ipy.Guild
  emojis: list[ipy.CustomEmoji]
  sort: str
  animated: bool = attrs.field(default=False)


  def get_pages_context(self):
    return [
      {
        "emoji_id": e.id,
        "emoji_name": e.name,
        "emoji_url": e.url,
        "emoji_mention": e if e.available else get_emoji(AppEmoji.TIME),
        "emoji_created_at_f": e.id.created_at.format("f"),
        "emoji_created_at_r": e.id.created_at.format("R"),
        "emoji_available": "" if e.available else "(Unavailable)",
      }
      for e in self.emojis
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[
          ipy.TextDisplayComponent(
            "## ${emoji_name}\n"
            "ID: ${emoji_id}\n"
            "Created at ${emoji_created_at_f}"
          ),
        ],
        accessory=ipy.ThumbnailComponent(
          ipy.UnfurledMediaItem("${emoji_url}")
        )
      )
    ]


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ {}".format(escape_text(self.guild.name))),
            ipy.TextDisplayComponent(
              "# Emoji List: {} ({}/{})".format("Animated" if self.animated else "Static", "${page}", "${pages}")
            ),
            ipy.TextDisplayComponent(
              "**{}**/{} available (Level {})".format(len(self.emojis), self.guild.emoji_limit, self.guild.premium_tier or 0)
            )
          ],
          accessory=ipy.ThumbnailComponent(
            ipy.UnfurledMediaItem("{}".format(self.guild.icon.as_url() if self.guild.icon else ""))
          )
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# {}: /server emoji animated={} sort={}".format(self.caller.tag, self.animated, self.sort)
        )
      ),
      SectionPaginatorNavPlaceholder(),
    ]


  def components_on_empty(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ {}".format(escape_text(self.guild.name))),
            ipy.TextDisplayComponent("# Emoji List: {}".format("Animated" if self.animated else "Static")),
            ipy.TextDisplayComponent(
              "**{}**/{} available (Level {})".format(0, self.guild.emoji_limit, self.guild.premium_tier or 0)
            )
          ],
          accessory=ipy.ThumbnailComponent(
            ipy.UnfurledMediaItem("{}".format(self.guild.icon.as_url() if self.guild.icon else ""))
          )
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("This server has no emoji of this type."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /server emoji animated={} sort={}".format(self.caller.tag, self.animated, self.sort)
        )
      ),
    ]