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
from mitsuki.lib.userdata import new_session


from .. import customids, api, presencer, commands


class SystemPresencesDelete(libcmd.WriterCommand):
  class Templates(StrEnum):
    CONFIRM = "system_presences_delete_confirm"


  async def check(self):
    await checks.assert_user_owner(self.ctx)


  def components(self, presence_id: int):
    return [
      ipy.Button(
        style=ipy.ButtonStyle.RED,
        label="Delete",
        emoji=settings.emoji.delete,
        custom_id=customids.SYSTEM_PRESENCES_DELETE.id(presence_id),
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        label="Cancel",
        emoji=settings.emoji.back,
        custom_id=customids.SYSTEM_PRESENCES,
      )
    ]


  async def confirm(self, presence_id: int):
    await self.check()
    await self.defer(ephemeral=True, edit_origin=self.has_origin, suppress_error=True)

    presence = await api.Presence.fetch(presence_id)
    if not presence:
      raise liberr.ObjectNotFound("Presence")

    data = {
      "presence_name": presence.name,
    }

    await self.send(self.Templates.CONFIRM, other_data=data, components=self.components(presence_id))


  async def delete(self, presence_id: int):
    await self.check()
    await self.defer(ephemeral=True, edit_origin=self.has_origin, suppress_error=True)

    async with new_session.begin() as session:
      _ = await api.Presence.delete_id(session, presence_id)

    await presencer.presencer().sync()
    await commands.SystemPresences.create(self.ctx).run()