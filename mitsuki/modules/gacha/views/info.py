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
from mitsuki.core.settings import Settings, get_setting
from mitsuki.core.gacha import CardCache, GachaSeason
from mitsuki.modules.gacha import customids


@attrs.define(slots=False)
class GachaInfoSeasonView(View):
  card_cache: CardCache


  def get_context(self):
    result = {}
    if season := self.card_cache.season:
      result |= {
        "season_name": season.name,
        "season_description": season.description or "",
        "season_image": season.image,
        "season_starts_f": ipy.Timestamp.fromtimestamp(season.start_time).format("f"),
        "season_ends_f": ipy.Timestamp.fromtimestamp(season.end_time).format("f"),
        "season_ends_r": ipy.Timestamp.fromtimestamp(season.end_time).format("R"),
        "season_rate_s": "{:.2f}%".format(season.pickup_rate * 100.0)
      }
    return result


  def components(self):
    return [
      ipy.MediaGalleryComponent([
        ipy.MediaGalleryItem(ipy.UnfurledMediaItem("${season_image}"))
      ]),
      ipy.ContainerComponent(
        ipy.SectionComponent(
          components=[
            ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
            ipy.TextDisplayComponent("# ${season_name}"),
            ipy.TextDisplayComponent(
              "**Season in progress!** Ends ${season_ends_r}\n"
              "Pickup chance: ${season_rate_s}"
            ),
          ],
          accessory=ipy.ThumbnailComponent(ipy.UnfurledMediaItem("${guild_avatar_url}")),
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("${season_description}"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Viewing current season info, tap \"Guide\" to view game details\n"
          "-# {}: /gacha info".format(self.caller.tag)
        ),
      ),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.BLURPLE,
          label="Guide",
          emoji=get_emoji(AppEmoji.GACHA_STAR_REGULAR),
          custom_id=customids.INFO_DETAILS,
        )
      )
    ]


@attrs.define(slots=False)
class GachaInfoDetailsView(View):
  card_cache: CardCache


  def get_context(self):
    return {
      "shard": get_emoji(AppEmoji.ITEM_SHARD),
      "shard_name": get_setting(Settings.ShardName),
      "shard_daily_reset": get_setting(Settings.DailyResetTime),
      "shard_daily_reset_tz": get_setting(Settings.DailyResetTimeZone),
      "shard_daily_amount": get_setting(Settings.DailyShards),
      "shard_daily_amount_first": get_setting(Settings.FirstTimeShards),
      "roll_cost": get_setting(Settings.RollShards),
    }

  def components(self):
    rarities = self.card_cache.rarities
    rates = [
      (
        ("{} **{:.2f}%**".format(r.emoji_str, r.rate * 100.0)) +
        (" (guaranteed in {} rolls)".format(r.pity) if r.pity else "") +
        (" - {} **{}** per duplicate".format("${shard}", r.dupe_shards))
      )
      for r in rarities.values()
    ]

    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("-# ❖ Mitsuki Gacha"),
        ipy.TextDisplayComponent("# Mitsuki Gacha Guide"),
        ipy.TextDisplayComponent(
          "Get ${shard} **${shard_daily_amount}** daily using `/gacha daily`!\n" +
          ("*New players get* ${shard} **${shard_daily_amount_first}** *when claiming daily for the first time!*\n"
            if get_setting(Settings.FirstTimeShards) != get_setting(Settings.DailyShards) else "") + 
          "Spend ${shard} **${roll_cost}** to roll a card using `/gacha roll`!"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "### Rates\n" +
          "While a season is ongoing, featured seasonal cards enjoy increased rates based on their pickup chance. " +
          "The pickup chance is the rate you obtain any featured seasonal card, as opposed to non-seasonal, " +
          "standard cards."
        ),
        ipy.SeparatorComponent(divider=False),
        ipy.TextDisplayComponent("\n".join(rates)),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "### Commands\n"
          "* `/gacha daily`: Claim daily ${shard} **${shard_name}**\n"
          "* `/gacha roll`: Roll for cards using ${shard} **${shard_name}**\n"
          "* `/gacha profile`: View your or someone's gacha profile\n"
          "* `/gacha cards`: View your or someone's card collection (list view)\n"
          "* `/gacha gallery`: View your or someone's card collection (gallery view)\n"
          "* `/gacha view`: Search for cards someone has rolled"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {}: /gacha info".format(self.caller.tag)
        ),
      )
    ]