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
from enum import StrEnum
from sqlalchemy.ext.asyncio import AsyncSession
from interactions.client.errors import HTTPException

from mitsuki import utils, settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks


from .. import customids, api, presencer, commands


class SystemPresencesAdd(libcmd.WriterCommand):
  presence_name: str

  class Templates(StrEnum):
    SUCCESS = "system_presences_add_success"


  async def check(self):
    await checks.assert_user_owner(self.ctx)


  async def prompt(self):
    await self.check()
    await self.ctx.send_modal(
      modal=ipy.Modal(
        ipy.ShortText(
          label="Status Message",
          custom_id="name",
          placeholder="e.g. \"Connected Sky\"",
          required=True,
          min_length=1,
          max_length=64,
        ),
        title="Add Presence",
        custom_id=customids.SYSTEM_PRESENCES_ADD.response()
      )
    )


  async def response(self, name: str):
    await self.check()
    await self.defer(ephemeral=True, edit_origin=False, suppress_error=True)

    self.presence_name = name
    data = {
      "presence_name": name,
    }

    await self.send_commit(self.Templates.SUCCESS, other_data=data)


  async def transaction(self, session: AsyncSession):
    await api.Presence.create(self.presence_name).add(session)
    await presencer.presencer().sync()