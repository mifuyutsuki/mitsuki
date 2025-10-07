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

from mitsuki.utils import escape_text, get_member_color_value
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import (
  View,
)
from mitsuki.core.gacha import GachaUser, CardCache, Card
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaRollView(View):
  cache: CardCache
  card: Card
  gacha_user: GachaUser


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_shards": self.gacha_user.amount,
      "card_name_esc": escape_text(self.card.name),
      "card_type_esc": escape_text(self.card.type),
      "card_series_esc": escape_text(self.card.series),
      "card_star_s": self.card.emoji_str,
      "card_new_or_dupe": (
        "✨ **New!**" if self.card.is_new_roll else
        "**{} +{}**".format(get_emoji(AppEmoji.ITEM_SHARD), self.card.dupe_shards)
      ),
      "card_image": self.card.image
    }


  def components(self):
    return [
      ipy.MediaGalleryComponent([
        ipy.MediaGalleryItem(
          ipy.UnfurledMediaItem("${card_image}")
        )
      ]),
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("${card_new_or_dupe}"),
        ipy.TextDisplayComponent("## ${card_name_esc}"),
        ipy.TextDisplayComponent("${card_star_s} • *${card_type_esc}* • *${card_series_esc}*"),
        ipy.TextDisplayComponent("You have ${shard} **${user_shards}**"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha roll".format(self.caller.tag)
        ),
        accent_color=self.card.color
      )
    ]