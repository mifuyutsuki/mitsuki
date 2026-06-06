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

from mitsuki.utils import escape_text, user_mention, get_member_color_value
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import (
  View,
  SectionPaginatorMixin,
  SectionPaginatorContentPlaceholder,
  PaginatorNavPlaceholder,
  DividerStyle,
)
from mitsuki.core.gacha import GachaUser, CardCollection, CardCache
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaCollectionsView(SectionPaginatorMixin, View):
  card_cache: CardCache
  target_user: ipy.Member
  gacha_user: Optional[GachaUser]
  collections: list[CardCollection]

  # Paginator parameters
  entries_per_page: int = 5
  divider_style: DividerStyle = DividerStyle.SMALL


  @property
  def is_target_own_user(self):
    if not self.gacha_user:
      return False
    return self.gacha_user.user == self.caller.id


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
      }
      if self.is_target_own_user:
        now = self.ctx.id.created_at
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


  def get_pages_context(self):
    return [
      {
        "collection_id": collection.id,
        "collection_name": collection.name,
        "collection_description": collection.description,
        "collection_available_cards": collection.available_count,
        "collection_owned_cards": collection.user_obtained,
        "collection_rolled_cards": collection.user_rolled,
      }
      for collection in self.collections
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[
          ipy.TextDisplayComponent(
            "### ${collection_name}\n"
            "**${collection_owned_cards}/${collection_available_cards}** owned (${collection_rolled_cards} rolled)\n"
            "${collection_description}"
          ),
        ],
        accessory=ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          emoji=get_emoji(AppEmoji.LIST),
          custom_id=customids.COLLECTION_CARDS.id("${collection_id}"),
        )
      )
    ]


  def components_on_empty(self):
    own_user_info = "You have ${shard} **${user_shards}** ${user_can_daily}" if self.is_target_own_user else ""
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[      
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("## ${user_username}'s Card Collections"),
            ipy.TextDisplayComponent(own_user_info),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "No collections are available to view.\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha collection".format(self.caller.tag)
          + " • Page ${page}/${pages}"
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
    ]


  def components(self):
    own_user_info = "You have ${shard} **${user_shards}** ${user_can_daily}" if self.is_target_own_user else ""
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[      
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("## ${user_username}'s Card Collections"),
            ipy.TextDisplayComponent(own_user_info),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha collection".format(self.caller.tag)
          + " • Page ${page}/${pages}"
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      PaginatorNavPlaceholder(),
    ]