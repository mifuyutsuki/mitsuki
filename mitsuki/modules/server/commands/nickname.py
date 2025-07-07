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
from interactions.client.errors import HTTPException

from mitsuki import utils
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks


class ServerNickname(libcmd.ReaderCommand):
  data: "ServerNickname.Data"

  class Templates(StrEnum):
    OK           = "server_nickname_ok"
    ERROR        = "server_nickname_error"
    ERROR_SAME   = "server_nickname_error_same"


  async def check(self):
    await checks.assert_in_guild(self.ctx)
    await checks.assert_user_permissions(self.ctx, ipy.Permissions.MANAGE_NICKNAMES, "Manage Nickname")
    await checks.assert_bot_permissions(self.ctx, ipy.Permissions.CHANGE_NICKNAME, "Change Nickname")


  async def run(self, new_nickname: Optional[str] = None):
    await self.defer(ephemeral=True)
    await self.check()

    bot_member   = await self.ctx.guild.fetch_member(self.ctx.bot.user.id)
    old_nickname = bot_member.nick

    if old_nickname == new_nickname:
      await self.send(self.Templates.ERROR_SAME)
      return

    try:
      await bot_member.edit_nickname(new_nickname)
    except HTTPException as e:
      await self.send(self.Templates.ERROR, other_data={"error": e.text or str(e)})
    else:
      await self.send(
        self.Templates.OK,
        other_data={"old_nickname": old_nickname or "-", "new_nickname": new_nickname or "-"}
      )