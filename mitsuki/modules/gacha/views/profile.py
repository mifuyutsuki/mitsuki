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
  card_cache: CardCache
  target_user: ipy.Member
  gacha_user: GachaUser


  def get_context(self):
    now = ipy.Timestamp.now()
    result = {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.target_user.id,
      "user_mention": self.target_user.mention,
      "user_username": self.target_user.tag,
      "user_name": self.target_user.display_name,
      "user_name_esc": escape_text(self.target_user.display_name),
      "user_avatar_url": self.target_user.avatar_url,
      "user_shards": self.gacha_user.amount,
    }
    if self.gacha_user.user == self.caller.id:
      result |= {
        "user_can_daily": "— **Daily available!**" if (
          self.gacha_user.can_daily(now=now)
        ) else "— Next daily {}".format(self.gacha_user.next_daily(now=now).format("R")),
      }
    else:
      result |= {
        "user_can_daily": ""
      }
    return result


  def components(self):
    user     = self.gacha_user
    rarities = self.card_cache.rarities

    fields = []

    if len(user.pity_counters) > 0:
      fields.append(
        "**Pity counter**\n" + " ".join([
          "{} **{}**/{}".format(rarities[r].emoji_str, count, rarities[r].pity)
          for r, count in user.pity_counters.items()
        ])
      )
    if len(user.rolled_cards) > 0:
      fields.append(
        "**Rolled cards:** {} card(s)\n".format(user.total_rolled) + " ".join([
          "{} **{}**".format(rarities[r].emoji_str, count)
          for r, count in user.rolled_cards.items()
        ])
      )
    if len(user.obtained_cards) > 0:
      fields.append(
        "**Obtained cards:** {} card(s)\n".format(user.total_obtained) + " ".join([
          "{} **{}**".format(rarities[r].emoji_str, count)
          for r, count in user.obtained_cards.items()
        ])
      )
    if len(fields) == 0:
      fields = ["No information is available for this user."]
    else:
      fields.append(
        "**Latest rolled**\n" + "\n".join([
          "{} {} **{}**".format(rarities[c.rarity].emoji_str, c.time.format("R"), escape_text(c.name))
          for c in user.recent_rolls
        ])
      )

    info_components = [ipy.TextDisplayComponent(field) for field in fields]

    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("# ${user_username}"),
            ipy.TextDisplayComponent("${shard} **${user_shards}** ${user_can_daily}"),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem(self.target_user.avatar_url))
        ),
        ipy.SeparatorComponent(divider=True),
        *info_components,
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha profile".format(self.caller.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Cards",
          emoji=get_emoji(AppEmoji.LIST),
          custom_id=customids.CARDS.id(self.target_user.id),
          disabled=self.gacha_user.total_rolled <= 0,
        ),
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Gallery",
          emoji=get_emoji(AppEmoji.GALLERY),
          custom_id=customids.GALLERY.id(self.target_user.id),
          disabled=self.gacha_user.total_rolled <= 0,
        ),
      ),
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
      "user_shards": 0,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("# ${user_username}"),
            ipy.TextDisplayComponent("${shard} **${user_shards}**"),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem(self.target_user.avatar_url))
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("No information is available for this user."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha profile".format(self.caller.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      )
    ]