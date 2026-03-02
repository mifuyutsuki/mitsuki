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
import aiohttp
import yaml
from typing import Optional

from mitsuki import utils
from mitsuki.lib.userdata import begin_session
from mitsuki.lib.emoji import get_emoji, AppEmoji
import mitsuki.lib.commands as libcmd
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

from mitsuki.core.gacha import CardCache
from mitsuki.modules.gacha_admin import views


class GachaSync(libcmd.ReaderCommand):
  async def check(self):
    await checks.assert_in_guild(self.ctx)
    await checks.assert_user_owner(self.ctx)


  async def run(self):
    await self.defer(ephemeral=True, suppress_error=True)
    await self.check()

    await CardCache.sync()
    await views.GachaSyncView(self.ctx).send(ephemeral=True)
