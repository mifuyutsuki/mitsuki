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
import aiohttp
import yaml
from typing import Optional

from mitsuki import utils
from mitsuki.lib.userdata import begin_session
from mitsuki.lib.emoji import get_emoji, AppEmoji
import mitsuki.lib.commands as libcmd
import mitsuki.lib.errors as errors
import mitsuki.lib.checks as checks

from mitsuki.core.submitter import CardSubmitter
from mitsuki.core.gacha import CardCache
from mitsuki.modules.gacha_admin import views


class RosterUpload(libcmd.ReaderCommand):
  async def check(self):
    await checks.assert_in_guild(self.ctx)
    await checks.assert_user_owner(self.ctx)


  async def run(self, file: ipy.Attachment):
    await self.defer(ephemeral=True, suppress_error=True)
    await self.check()

    if file.size > 8_000_000:
      raise errors.BadFileSize(size_mb=file.size / 1_000_000, max_size_mb=8.0)

    async with aiohttp.ClientSession() as session:
      async with session.get(file.url) as response:
        response.raise_for_status()
        f = await response.text()

    try:
      data = yaml.safe_load(f)
    except Exception:
      raise errors.BadFile(expect="Roster YAML file")

    submitter = await CardSubmitter.from_rosc2y_yaml(data)
    await views.RosterUploadPromptView(self.ctx, submitter).send(ephemeral=True)


  async def proceed(self, id: str):
    await self.defer(ephemeral=True, edit_origin=True, suppress_error=True)
    await self.check()

    submitter = await CardSubmitter.fetch(id)
    if not submitter:
      raise errors.ObjectNotFound("Roster Update")

    async with begin_session() as session:
      await submitter.execute(session)
      await views.RosterUploadDoneView(self.ctx, submitter).send(ephemeral=True)
    await CardCache.sync()