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
from typing import Optional

from mitsuki import utils
from mitsuki.lib.userdata import begin_session
from mitsuki.lib.emoji import get_emoji, AppEmoji
from mitsuki.lib.commands import ReaderCommand
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

import mitsuki.core.gacha as core
import mitsuki.modules.gacha.views as views


class GachaInfo(ReaderCommand):
  async def run(self, details: bool = False):
    await checks.assert_in_guild(self.ctx)
    await self.defer(ephemeral=False, edit_origin=False)

    cache = await core.CardCache.get_cache()
    if not details and cache.season:
      view = views.GachaInfoSeasonView(self.ctx, cache)
    else:
      view = views.GachaInfoDetailsView(self.ctx, cache)
    await view.send(timeout=180, hide_on_timeout=True)