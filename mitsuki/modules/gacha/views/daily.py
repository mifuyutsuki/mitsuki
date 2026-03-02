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

from mitsuki.consts import AccentColors
from mitsuki.utils import escape_text, get_member_color_value
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import (
  View,
)
from mitsuki.core.settings import get_setting, Settings
from mitsuki.core.gacha import GachaUser, CardCache
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaDailyView(View):
  card_cache: CardCache
  gacha_user: GachaUser
  now: ipy.Timestamp


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.ctx.author.id,
      "user_mention": self.ctx.author.mention,
      "user_username": self.ctx.author.tag,
      "user_name": self.ctx.author.display_name,
      "user_name_esc": escape_text(self.ctx.author.display_name),
      "user_avatar_url": self.ctx.author.avatar_url,
      "user_shards": self.gacha_user.amount,
      "daily_shards": get_setting(Settings.DailyShards),
      "daily_next": self.gacha_user.next_daily(now=self.now).format("R"),
    }


  def components(self):
    if self.gacha_user.claimed_first_daily:
      return [
        ipy.ContainerComponent(
          ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
          ipy.TextDisplayComponent("## ✨ Claimed first-time daily! ${shard} **${daily_shards}**"),
          ipy.TextDisplayComponent(
            "You have ${shard} **${user_shards}**\n"
            "Claim again ${daily_next}"
          ),
          ipy.SeparatorComponent(divider=True),
          ipy.TextDisplayComponent(
            "-# {}: /gacha daily".format(self.caller.tag)
          ),
          accent_color=AccentColors.SPECIAL
        )
      ]

    elif self.gacha_user.claimed_daily:
      return [
        ipy.ContainerComponent(
          ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
          ipy.TextDisplayComponent("## Claimed daily! ${shard} **${daily_shards}**"),
          ipy.TextDisplayComponent(
            "You have ${shard} **${user_shards}**\n"
            "Claim again ${daily_next}"
          ),
          ipy.SeparatorComponent(divider=True),
          ipy.TextDisplayComponent(
            "-# {}: /gacha daily".format(self.caller.tag)
          ),
          accent_color=AccentColors.OK
        )
      ]

    else:
      return [
        ipy.ContainerComponent(
          ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
          ipy.TextDisplayComponent("## Already claimed for today"),
          ipy.TextDisplayComponent(
            "You have ${shard} **${user_shards}**\n"
            "Next daily ${daily_next}"
          ),
          ipy.SeparatorComponent(divider=True),
          ipy.TextDisplayComponent(
            "-# {}: /gacha daily".format(self.caller.tag)
          ),
          accent_color=AccentColors.ERROR
        )
      ]