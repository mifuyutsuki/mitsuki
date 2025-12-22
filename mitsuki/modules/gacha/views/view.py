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

from mitsuki.utils import escape_text, user_mention
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import (
  View,
  SectionPaginatorMixin,
  SectionPaginatorContentPlaceholder,
  PaginatorNavPlaceholder,
  DividerStyle,
)
from mitsuki.core.gacha import GachaUser, CardCache, Card, CardStats, UserCard
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaViewView(View):
  card_cache: CardCache
  global_card: CardStats
  user_card: Optional[UserCard] = None


  def get_context(self):
    result = {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "user_id": self.ctx.author.id,
      "user_mention": self.ctx.author.mention,
      "user_username": self.ctx.author.tag,
      "user_name": self.ctx.author.display_name,
      "user_name_esc": escape_text(self.ctx.author.display_name),
      "user_avatar_url": self.ctx.author.avatar_url,

      "card_id": self.global_card.id,
      "card_name": escape_text(self.global_card.name),
      "card_type": escape_text(self.global_card.type),
      "card_series": escape_text(self.global_card.series),
      "card_image": self.global_card.image,
      "card_star_s": self.card_cache.rarities[self.global_card.rarity].emoji_str,

      "global_rolled_count": self.global_card.rolled_count,
      "global_users_count": self.global_card.users_count,
      "global_first_rolled_f": self.global_card.first_rolled.format("f"),
      "global_first_rolled_by": user_mention(self.global_card.first_rolled_by),
      "global_last_rolled_f": self.global_card.last_rolled.format("f"),
      "global_last_rolled_by": user_mention(self.global_card.last_rolled_by),
    }
    if self.user_card:
      result |= {
        "user_rolled_count": self.user_card.rolled_count,
        "user_owned_count": self.user_card.count,
        "user_first_rolled_f": self.user_card.first_rolled.format("f"),
        "user_last_rolled_f": self.user_card.last_rolled.format("f"),
      }
    return result


  def components(self):
    user_components = [
      ipy.TextDisplayComponent(
        "**In your collection**: **${user_owned_count}** card(s)\n"
        "You first acquired this on ${user_first_rolled_f}"
      ),
    ] if self.user_card else [
      ipy.TextDisplayComponent(
        "Not yet acquired in your collection"
      ),
    ]
    buttons = [
      ipy.ActionRow(
        ipy.Button(style=ipy.ButtonStyle.LINK, label="Card Picture", url="${card_image}")
      )
    ] if self.global_card.image else []
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("## ${card_name}"),
            ipy.TextDisplayComponent("${card_star_s} • *${card_type}* • *${card_series}*"),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${card_image}"))
        ),
        ipy.SeparatorComponent(divider=True),
        *user_components,
        ipy.TextDisplayComponent(
          "**Global statistics:**\n"
          "Rolled **${global_rolled_count}** time(s) by **${global_users_count}** user(s)\n"
          "Last rolled by ${global_last_rolled_by} on ${global_last_rolled_f}"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha view".format(self.caller.tag)
        ),
        accent_color=self.card_cache.rarities[self.global_card.rarity].color
      ),
      *buttons
    ]


@attrs.define(slots=False)
class GachaViewResultsView(SectionPaginatorMixin, View):
  card_cache: CardCache
  search_key: str
  cards: list[Card]

  # Paginator parameters
  animated: bool = False
  entries_per_page: int = 5
  divider_style: DividerStyle = DividerStyle.SMALL


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "search_key": self.search_key,
      "search_results_count": len(self.cards),
      "user_id": self.ctx.author.id,
      "user_mention": self.ctx.author.mention,
      "user_username": self.ctx.author.tag,
      "user_name": self.ctx.author.display_name,
      "user_name_esc": escape_text(self.ctx.author.display_name),
      "user_avatar_url": self.ctx.author.avatar_url,
    }


  def get_pages_context(self):
    return [
      {
        "card_id": card.id,
        "card_name": escape_text(card.name),
        "card_type": escape_text(card.type),
        "card_series": escape_text(card.series),
        "card_image": card.image,
        "card_star_s": card.emoji_str,
      }
      for card in self.cards
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[      
          ipy.TextDisplayComponent(
            "### ${card_name}\n"
            "${card_star_s} • *${card_type}* • *${card_series}*"
          ),
        ],
        accessory=ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          emoji=get_emoji(AppEmoji.YES),
          custom_id=customids.VIEW.id("@${card_id}")
        ),
      )
    ]


  def components_on_empty(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
        ipy.TextDisplayComponent("## Searching: \"${search_key}\""),
        ipy.TextDisplayComponent(
          "Found **${search_results_count}** result(s)\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("No cards found."),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# If you can't find the card, the card might have not been acquired by a user or doesn't exist.\n"
          + "-# {}: /gacha view".format(self.caller.tag)
        ),
      ),
    ]


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
        ipy.TextDisplayComponent("## Searching: \"${search_key}\" (${page}/${pages})"),
        ipy.TextDisplayComponent(
          "Found **${search_results_count}** result(s)\n"
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# If you can't find the card, the card might have not been acquired by a user or doesn't exist.\n"
          + "-# {}: /gacha view".format(self.caller.tag)
        ),
      ),
      PaginatorNavPlaceholder(),
    ]