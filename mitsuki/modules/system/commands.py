# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import User, Member, Permissions, is_owner
from interactions.client.errors import HTTPException
from attrs import define, field
from enum import StrEnum
from typing import Optional, Union

from mitsuki.lib.commands import AsDict, ReaderCommand
from mitsuki.lib.checks import assert_bot_permissions, assert_user_permissions


class Nickname(ReaderCommand):
  states: "Nickname.States"
  data: "Nickname.Data"

  class States(StrEnum):
    OK           = "system_nickname_ok"
    ERROR        = "system_nickname_error"
    ERROR_SAME   = "system_nickname_error_same"
    USER_DENIED  = "system_nickname_denied_user"
    BOT_DENIED   = "system_nickname_denied_bot"
    NOT_IN_GUILD = "system_nickname_not_in_guild"

  @define(slots=False)
  class Data(AsDict):
    old_nickname: str
    new_nickname: str


  async def run(self, new_nickname: Optional[str] = None):
    await self.defer(ephemeral=True)
    if not self.ctx.guild:
      return await self.send(self.States.NOT_IN_GUILD)

    await assert_bot_permissions(self.ctx, Permissions.CHANGE_NICKNAME, "Change Nickname")
    await assert_user_permissions(self.ctx, Permissions.MANAGE_NICKNAMES, "Manage Nickname")

    bot_member = await self.ctx.guild.fetch_member(self.ctx.bot.user.id)
    old_nickname = bot_member.nick

    if old_nickname == new_nickname:
      return await self.send(self.States.ERROR_SAME)

    try:
      await bot_member.edit_nickname(new_nickname)
    except HTTPException as e:
      return await self.send(self.States.ERROR, other_data={"error": e.text or str(e)})

    return await self.send(
      self.States.OK,
      other_data={"old_nickname": old_nickname or "-", "new_nickname": new_nickname or "-"}
    )