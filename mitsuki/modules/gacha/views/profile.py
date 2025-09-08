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
from mitsuki.core.gacha import GachaUser, CardCache
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaProfileView(View):
  target_user: ipy.Member
  gacha_user: GachaUser
  card_cache: CardCache


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.target_user.id,
      "user_mention": self.target_user.mention,
      "user_username": self.target_user.tag,
      "user_name": self.target_user.display_name,
      "user_name_esc": escape_text(self.target_user.display_name),
      "user_avatar_url": self.target_user.avatar_url,
      "user_shards": self.gacha_user.amount,
    }


  def components(self):
    user     = self.gacha_user
    rarities = self.card_cache.rarities

    counter_fields = []

    if len(user.pity_counters) > 0:
      counter_fields.append(
        "**Pity counter**\n" + " ".join([
          "{} **{}**/{}".format(rarities[r].emoji_str, count, rarities[r].pity)
          for r, count in user.pity_counters.items()
        ])
      )
    if len(user.rolled_cards) > 0:
      counter_fields.append(
        "**Rolled cards:** {} card(s)\n".format(user.total_rolled) + " ".join([
          "{} **{}**".format(rarities[r].emoji_str, count)
          for r, count in user.rolled_cards.items()
        ])
      )
    if len(user.obtained_cards) > 0:
      counter_fields.append(
        "**Obtained cards:** {} card(s)\n".format(user.total_obtained) + " ".join([
          "{} **{}**".format(rarities[r].emoji_str, count)
          for r, count in user.obtained_cards.items()
        ])
      )

    if len(counter_fields) == 0:
      counter_fields = ["No information is available for this user."]

    rolls_fields = [
      "{} {} **{}**".format(rarities[c.rarity].emoji_str, c.time.format("R"), escape_text(c.name))
      for c in user.recent_rolls
    ]

    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("## ${user_username}'s Gacha Profile"),
            ipy.TextDisplayComponent("${shard} **${user_shards}**"),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem(self.target_user.avatar_url))
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("\n\n".join(counter_fields)),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("### Latest Rolled\n" + "\n".join(rolls_fields)),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha profile user={}".format(self.caller.tag, self.target_user.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      )
    ]


@attrs.define(slots=False)
class GachaProfileEmptyView(View):
  target_user: ipy.Member


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.target_user.id,
      "user_mention": self.target_user.mention,
      "user_username": self.target_user.tag,
      "user_name": self.target_user.display_name,
      "user_name_esc": escape_text(self.target_user.display_name),
      "user_avatar_url": self.target_user.avatar_url,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ✦ ${guild_name_esc}"),
            ipy.TextDisplayComponent("## ${user_username}'s Gacha Profile"),
            ipy.TextDisplayComponent("${shard} **${user_shards}**"),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem(self.target_user.avatar_url))
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("No information is available for this user."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha profile user={}".format(self.caller.tag, self.target_user.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      )
    ]