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
from typing import Optional

from mitsuki import utils
from mitsuki.lib.userdata import begin_session
from mitsuki.lib.emoji import get_emoji, AppEmoji
from mitsuki.lib.commands import ReaderCommand, AutocompleteMixin
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

import mitsuki.core.gacha as core
import mitsuki.modules.gacha.views as views


class GachaView(AutocompleteMixin, ReaderCommand):
  @staticmethod
  def search_entry(card: core.Card):
    return utils.truncate(
      (("★" * card.rarity) if card.rarity <= 6 else f"{card.rarity}★") + f" {card.name}"
    )


  async def autocomplete(self, input_text: str):
    # Short circuit on length < 1
    # TODO: Return your most recent rolls
    if len(input_text) < 1:
      return await self.send_autocomplete()

    # First entry is the search key itself (goes to search results message)
    options = [self.option(input_text, input_text)]

    # ID search (@card_id)
    if input_text.startswith("@"):
      if card_by_id := await core.Card.fetch(input_text[1:], unobtained=False):
        options.append(self.option(self.search_entry(card_by_id), input_text))

    # Short circuit on length < 3
    if len(input_text) < 3:
      return await self.send_autocomplete(options)

    options.extend([
      self.option(self.search_entry(card), f"@{card.id}")
      for card in await core.CardCache.search_fetch(input_text, limit=9-len(options))
    ])
    return await self.send_autocomplete(options)


  async def run(self, search_key: str, *, origin: bool = False):
    await checks.assert_in_guild(self.ctx)
    await self.defer(ephemeral=False, edit_origin=origin)

    if search_key.startswith("@"):
      if card := await core.CardStats.fetch(search_key[1:]):
        await self.run_view(card)
        return
    await self.run_prompt(search_key)


  async def run_view(self, card: core.CardStats):
    cache       = await core.CardCache.get_cache()
    user_card   = await core.UserCard.fetch(card.id, self.caller_user)

    view = views.GachaViewView(self.ctx, card_cache=cache, global_card=card, user_card=user_card)
    await view.send()


  async def run_prompt(self, search_key: str):
    cache   = await core.CardCache.get_cache()
    results = await core.CardCache.search_fetch(search_key, unobtained=False)

    view = views.GachaViewResultsView(self.ctx, card_cache=cache, search_key=search_key, cards=results)
    await view.send(timeout=45, hide_on_timeout=True)