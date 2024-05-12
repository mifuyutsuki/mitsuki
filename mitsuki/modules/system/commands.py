# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

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
from mitsuki.utils import UserDenied, BotDenied


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


  async def run(self, nickname: Optional[str] = None):
    await self.defer(ephemeral=True)
    if not self.ctx.guild:
      self.set_state(self.States.NOT_IN_GUILD)
      await self.send()
      return

    err_text = "-"
    bot_member = await self.ctx.bot.fetch_member(self.ctx.bot.user.id, self.ctx.guild.id)
    prev_nick  = bot_member.nick
    if not bot_member.has_permission(Permissions.CHANGE_NICKNAME):
      raise BotDenied(requires="Change Nickname")
    if not self.caller_user.has_permission(Permissions.MANAGE_NICKNAMES) and not await is_owner()(self.ctx):
      raise UserDenied(requires="Manage Nickname")
    if bot_member.nick == nickname:
      self.set_state(self.States.ERROR_SAME)
    else:
      try:
        await bot_member.edit_nickname(nickname)
      except HTTPException as e:
        self.set_state(self.States.ERROR)
        err_text = e.text
      else:
        self.set_state(self.States.OK)

    self.data = self.Data(old_nickname=prev_nick or "-", new_nickname=nickname or "-")
    await self.send(other_data=dict(error=err_text))