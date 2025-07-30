# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""
Mitsuki bot emoji finder.

On startup, Mitsuki fetches emoji by a predetermined set of emoji names, all
prefixed with `m_`. The following set of emoji are used, in order:

1. Application emoji;
2. System Guild emoji, if set; and
3. Default/fallback emoji.

If multiple emoji share a Mitsuki emoji name, the newer emoji is used.

Note:
  Added in version 5.0.
"""

import attrs
import interactions as ipy

import os
from typing import Optional, Union
from enum import Enum

from mitsuki import logger


class AppEmoji(Enum):
  YES     = ("m_yes", "✅")
  NO      = ("m_no", "❌")
  NEW     = ("m_new", "*️⃣")
  EDIT    = ("m_edit", "✏")
  DELETE  = ("m_delete", "🗑")
  REFRESH = ("m_refresh", "🔄")
  BACK    = ("m_back", "↩")

  LIST      = ("m_list", "🗒")
  GALLERY   = ("m_gallery", "🖼")
  CONFIGURE = ("m_configure", "⚙")

  ON  = ("m_on", "☀")
  OFF = ("m_off", "🌑")

  TEXT = ("m_text", "📝")
  TIME = ("m_time", "🕗")
  DATE = ("m_date", "📅")
  HASH = ("m_pg_goto", "#️⃣")

  PAGE_FIRST    = ("m_pg_first", "⏪")
  PAGE_PREVIOUS = ("m_pg_prev", "◀")
  PAGE_NEXT     = ("m_pg_next", "▶")
  PAGE_LAST     = ("m_pg_last", "⏩")
  PAGE_GOTO     = ("m_pg_goto", "#️⃣")

  GACHA_STAR_REGULAR = ("m_gc_star1", "⭐")
  GACHA_STAR_RAINBOW = ("m_gc_star2", "🌟")

  ITEM_SHARD = ("m_it_shard", "💠")

  @classmethod
  def count(cls):
    return len(cls)


@attrs.define(kw_only=False)
class EmojiFinder:
  bot: ipy.ClientT
  emoji: dict[str, Union[ipy.CustomEmoji, ipy.PartialEmoji]] = attrs.field(factory=dict)


  @classmethod
  def create(cls, bot: ipy.ClientT):
    return cls(bot=bot)


  def get(self, emoji: "AppEmoji") -> Union[ipy.CustomEmoji, ipy.PartialEmoji]:
    name, default = emoji.value
    return self.emoji.get(name, ipy.PartialEmoji.from_str(default))


  async def init(self) -> None:
    app_emoji = await self.bot.app.fetch_all_emoji()
    app_emoji.sort(key=lambda e: e.id)

    system_guild_emoji = []
    try:
      system_guild_id = ipy.Snowflake(os.environ.get("SYSTEM_GUILD_ID"))
      system_guild = await self.bot.fetch_guild(system_guild_id)
      system_guild_emoji = await system_guild.fetch_all_custom_emojis()
      system_guild_emoji.sort(key=lambda e: e.id)
    except Exception:
      pass

    app_emoji_use_count = 0
    system_guild_emoji_use_count = 0
    default_emoji_use_count = 0

    for en in AppEmoji:
      name, default = en.value
      if name in self.emoji:
        continue

      if this_emoji := next((e for e in app_emoji if e.name == name), None):
        app_emoji_use_count += 1
        self.emoji[name] = this_emoji
      elif this_emoji := next((e for e in system_guild_emoji if e.name == name), None):
        system_guild_emoji_use_count += 1
        self.emoji[name] = this_emoji
      else:
        default_emoji_use_count += 1
        self.emoji[name] = ipy.PartialEmoji.from_str(default)

    logger.info(
      f"Emoji Finder | Loaded {AppEmoji.count()} emoji - "
      f"{app_emoji_use_count} from app, "
      f"{system_guild_emoji_use_count} from system guild, "
      f"{default_emoji_use_count} from default"
    )


_finder: Optional["EmojiFinder"] = None


async def init_emoji(bot: ipy.ClientT) -> None:
  global _finder
  _finder = EmojiFinder.create(bot)
  await _finder.init()


def get_emoji(emoji: "AppEmoji") -> Union[ipy.CustomEmoji, ipy.PartialEmoji]:
  global _finder
  if not _finder:
    raise RuntimeError("Emoji finder is uninitialized")
  return _finder.get(emoji)