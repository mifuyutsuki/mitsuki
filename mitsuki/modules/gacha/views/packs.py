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
from mitsuki.core.gacha import GachaUser, CardCollection, CardCache, UserCard, CardCollectionCategory
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaPackSetsView(SectionPaginatorMixin, View):
  card_cache: CardCache
  target_user: ipy.Member
  gacha_user: Optional[GachaUser]
  categories: list[CardCollectionCategory]

  # Paginator parameters
  entries_per_page: int = 8
  divider_style: DividerStyle = DividerStyle.NONE


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
        "category_id": category.id,
        "category_name": category.name,
        "category_description": category.description,
        "category_entries": category.count,
      }
      for category in self.categories
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[
          ipy.TextDisplayComponent(
            "### ${category_name}\n"
            "*${category_description}*\n"
            "**${category_entries}** packs available"
          ),
        ],
        accessory=ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          emoji=get_emoji(AppEmoji.LIST),
          custom_id=customids.PACK_LIST.id("${category_id}").id("${user_id}"),
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
            ipy.TextDisplayComponent("## Card Pack Sets - ${user_username}\n" + own_user_info),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "No card pack sets available to view.\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
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
            ipy.TextDisplayComponent("## Card Pack Sets - ${user_username}\n" + own_user_info),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
          + " • Page ${page}/${pages}"
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      PaginatorNavPlaceholder(),
    ]


@attrs.define(slots=False)
class GachaPacksView(SectionPaginatorMixin, View):
  card_cache: CardCache
  target_user: ipy.Member
  gacha_user: Optional[GachaUser]
  collections: list[CardCollection]
  category: CardCollectionCategory

  # Paginator parameters
  entries_per_page: int = 5
  divider_style: DividerStyle = DividerStyle.NONE


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

    result |= {
      "category_id": self.category.id,
      "category_name": self.category.name,
      "category_description": self.category.description,
      "category_description_s": f"\n> {self.category.description}" if self.category.description else "",
      "category_entries": len(self.collections),
    }
    return result


  def get_pages_context(self):
    return [
      {
        "collection_id": collection.id,
        "collection_name": collection.name,
        "collection_description": collection.description,
        "collection_available_cards": collection.available_count if collection.show_counts else "-",
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
            "*${collection_description}*\n"
            "**${collection_owned_cards}/${collection_available_cards}** owned (${collection_rolled_cards} rolled)"
          ),
        ],
        accessory=ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          emoji=get_emoji(AppEmoji.LIST),
          custom_id=customids.PACK_CARDS.id("${category_id}").id("${collection_id}").id("${user_id}"),
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
            ipy.TextDisplayComponent(
              "## ${category_name} - ${user_username} ${category_description_s}\n" + own_user_info
            ),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "No card packs available to view.\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Back to Sets",
          emoji=get_emoji(AppEmoji.BACK),
          custom_id=customids.PACK_CATEGORY.id("${user_id}"),
        )
      ),
    ]


  def components(self):
    own_user_info = "You have ${shard} **${user_shards}** ${user_can_daily}" if self.is_target_own_user else ""
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent(
              "## ${category_name} - ${user_username} ${category_description_s}\n"
              "**${category_entries}** card packs available\n"
              + own_user_info
            ),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
          + " • Page ${page}/${pages}"
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      PaginatorNavPlaceholder(),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Back to Sets",
          emoji=get_emoji(AppEmoji.BACK),
          custom_id=customids.PACK_CATEGORY.id("${user_id}"),
        )
      ),
    ]


@attrs.define(slots=False)
class GachaPackCardsView(SectionPaginatorMixin, View):
  card_cache: CardCache
  target_user: ipy.Member
  gacha_user: Optional[GachaUser]
  collection: CardCollection
  cards: list[UserCard]
  source_category: str

  # Paginator parameters
  entries_per_page: int = 5
  divider_style: DividerStyle = DividerStyle.NONE


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

    # if self.collection:
    result |= {
      "collection_id": self.collection.id,
      "collection_name": self.collection.name,
      "collection_description": self.collection.description,
      "collection_available_cards": self.collection.available_count if self.collection.show_counts else "-",
      "collection_owned_cards": self.collection.user_obtained,
      "collection_rolled_cards": self.collection.user_rolled,
    }
    return result


  def get_pages_context(self):
    return [
      {
        "card_id": card.id,
        "card_name": escape_text(card.name),
        "card_type": escape_text(card.type),
        "card_series": escape_text(card.series),
        "card_image": card.image,
        "card_star_s": self.card_cache.rarities[card.rarity].emoji_str,
        "card_owned_count": card.count,
        "card_rolled_count": card.rolled_count,
        "card_first_rolled_f": card.first_rolled.format("f"),
        "card_last_rolled_f": card.last_rolled.format("f"),
      }
      for card in self.cards
    ]


  def section(self):
    return [
      ipy.SectionComponent(
        components=[      
          ipy.TextDisplayComponent(
            "### ${card_name}\n"
            "${card_star_s} • *${card_type}* • *${card_series}*\n"
          ),
          ipy.TextDisplayComponent(
            "**${card_owned_count}** card(s) in collection\n"
            "First acquired: ${card_first_rolled_f}"
          )
        ],
        accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${card_image}")),
      )
    ]


  def components_on_empty(self):
    own_user_info = "You have ${shard} **${user_shards}** ${user_can_daily}" if self.is_target_own_user else ""
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent(
              "## ${collection_name}\n"
              "> ${collection_description}"
            ),
            ipy.TextDisplayComponent(
              "**${collection_owned_cards}/${collection_available_cards}** owned (**${collection_rolled_cards}** rolled) "
              "by ${user_mention}\n"
              + own_user_info
            ),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "No cards have been acquired by this user in this card pack.\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Back to Packs",
          emoji=get_emoji(AppEmoji.BACK),
          custom_id=customids.PACK_LIST.id(self.source_category).id("${user_id}"),
        )
      ),
    ]


  def components(self):
    own_user_info = "You have ${shard} **${user_shards}** ${user_can_daily}" if self.is_target_own_user else ""
    return [
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent(
              "## ${collection_name} - ${user_username}\n"
              "> ${collection_description}"
            ),
            ipy.TextDisplayComponent(
              "**${collection_owned_cards}/${collection_available_cards}** owned (**${collection_rolled_cards}** rolled) "
              "by ${user_mention}\n"
              + own_user_info
            ),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${user_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        SectionPaginatorContentPlaceholder(),
        ipy.TextDisplayComponent(
          "-# Tap the thumbnail to view the card picture\n"
          "-# Viewing ${user_username}'s (${user_mention}) card collection\n"
          + "-# {}: /gacha packs".format(self.caller.tag)
          + " • Page ${page}/${pages}"
        ),
        accent_color=get_member_color_value(self.target_user)
      ),
      PaginatorNavPlaceholder(),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GRAY,
          label="Back to Packs",
          emoji=get_emoji(AppEmoji.BACK),
          custom_id=customids.PACK_LIST.id(self.source_category).id("${user_id}"),
        )
      ),
    ]