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
from mitsuki.lib.commands import ReaderCommand, userlock
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

from mitsuki.core.settings import Settings, get_setting
import mitsuki.core.gacha as core
import mitsuki.modules.gacha.errors as gacha_errors
import mitsuki.modules.gacha.views as views


class GachaRoll(ReaderCommand):
  @userlock(pre_defer=True, bucket="gacha")
  async def run(self, custom_id_user: Optional[ipy.Snowflake] = None):
    await checks.assert_in_guild(self.ctx)
    await self.defer(ephemeral=False, edit_origin=False)
    now = self.ctx.id.created_at

    if custom_id_user and custom_id_user != self.caller_id:
      raise errors.InteractionDenied()

    gacha_user = await core.GachaUser.fetch(self.caller_id)
    if not gacha_user:
      raise gacha_errors.UnregisteredGachaUser()

    shard_name = get_setting(Settings.ShardName)
    shard_icon = get_emoji(AppEmoji.ITEM_SHARD)
    roll_cost  = get_setting(Settings.RollShards)

    if gacha_user.amount < roll_cost:
      raise gacha_errors.InsufficientShards(shard_name, str(shard_icon), roll_cost, gacha_user.amount)

    pity_rarity = await core.GachaUser.fetch_guarantee(gacha_user.user)
    cache  = await core.CardCache.get_cache()
    rolled = await cache.roll(min_rarity=pity_rarity, now=now)

    async with begin_session() as session:
      await gacha_user.take_shards(session, get_setting(Settings.RollShards))
      await rolled.give_to(session, gacha_user.user, rolled=True)
      if not rolled.is_new_roll:
        _ = await gacha_user.give_shards(session, rolled.dupe_shards)

      view = views.GachaRollView(self.ctx, card_cache=cache, gacha_user=gacha_user, card=rolled)
      await view.send()