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
class GachaShardsView(View):
  target_user: ipy.Member
  gacha_user: Optional[GachaUser] = None


  def get_context(self):
    result = {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.target_user.id,
      "user_mention": self.target_user.mention,
      "user_username": self.target_user.tag,
      "user_name": self.target_user.display_name,
      "user_name_esc": escape_text(self.target_user.display_name),
      "user_avatar_url": self.target_user.avatar_url,
    }
    if self.gacha_user:
      result |= {
        "user_shards": self.gacha_user.amount,
        "user_can_daily": "— **Daily available!**" if (
          self.gacha_user.user == self.caller.id
          and self.gacha_user.can_daily()
        ) else "",
      }
    else:
      result |= {
        "user_shards": 0,
        "user_can_daily": "",
      }
    return result


  def components(self):
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
        ipy.TextDisplayComponent(
          "-# {}: /gacha shards".format(self.caller.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      )
    ]