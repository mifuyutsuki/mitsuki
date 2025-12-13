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
from mitsuki.lib.commands import ReaderCommand
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

import mitsuki.core.gacha as core
import mitsuki.modules.gacha.views as views


class GachaDaily(ReaderCommand):
  async def run(self):
    await checks.assert_in_guild(self.ctx)
    await self.defer(ephemeral=False, edit_origin=False)

    cache = await core.CardCache.get_cache()
    user  = self.caller_user
    now   = self.ctx.id.created_at

    async with begin_session() as session:
      gacha_user = await core.GachaUser.daily(session, user, now=now)

      view = views.GachaDailyView(self.ctx, card_cache=cache, gacha_user=gacha_user, now=now)
      await view.send()