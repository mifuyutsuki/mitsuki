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

from typing import Optional, Union
from enum import StrEnum

from mitsuki import utils, settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks

from ..customids import CustomIDs


class AvatarInfo(libcmd.TargetMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    AVATAR = "info_avatar"


  async def run(self, target: Optional[Union[ipy.User, ipy.Member]] = None):
    await self.defer(suppress_error=True)

    target = target or self.caller_user
    self.set_target(target)

    if isinstance(self.target_user, ipy.Member) and self.target_user.guild_avatar:
      await self._run_with_server_avatar()
    else:
      await self._run_without_server_avatar()


  async def _run_with_server_avatar(self):
    view_global = False

    while True:
      if view_global:
        avatar = self.target_user.user.avatar.url
        btn = ipy.Button(label="Server Avatar", style=ipy.ButtonStyle.BLURPLE)
      else:
        avatar = self.target_user.guild_avatar.url
        btn = ipy.Button(label="Global Avatar", style=ipy.ButtonStyle.BLURPLE)

      _ = await self.send(
        self.Templates.AVATAR,
        other_data={
          "target_avatar": avatar,
          "avatar_mode": "global" if view_global else "server"
        },
        edit_origin=True,
        components=btn
      )
      try:
        response = await self.ctx.bot.wait_for_component(components=btn, timeout=45, check=utils.is_caller(self.ctx))
      except TimeoutError:
        if response.ctx.message:
          await response.ctx.message.edit(components=[])
        return
      else:
        self.set_ctx(response.ctx)
        view_global = not view_global


  async def _run_without_server_avatar(self):
    avatar = self.target_user.avatar_url
    _ = await self.send(self.Templates.AVATAR, other_data={"target_avatar": avatar, "avatar_mode": "global"})