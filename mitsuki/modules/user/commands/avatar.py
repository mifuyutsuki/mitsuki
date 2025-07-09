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

from .. import customids


class UserAvatar(libcmd.TargetMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    AVATAR = "user_avatar"


  async def run(self, target: Optional[Union[ipy.User, ipy.Member, ipy.Snowflake]] = None):
    target = target or self.caller_user

    if isinstance(target, ipy.Member) and target.guild_avatar:
      await self.run_server(target)
    else:
      await self.run_global(target)


  async def run_server(self, target: Optional[Union[ipy.User, ipy.Member, ipy.Snowflake]] = None):
    await self.defer(suppress_error=True, edit_origin=self.has_origin)

    if isinstance(target, ipy.Snowflake):
      _target = await self.ctx.guild.fetch_member(target)
      if not _target:
        return await self.run_global(target)
      target = _target
    else:
      target = target or self.caller_user

    self.set_target(target)

    data = {
      "target_avatar": target.guild_avatar.as_url(),
      "avatar_mode": "server",
    }
    btn = ipy.Button(
      label="Global Avatar",
      emoji=settings.emoji.gallery,
      style=ipy.ButtonStyle.BLURPLE,
      custom_id=customids.USER_AVATAR_GLOBAL.id(target.id),
    )

    m = await self.send(self.Templates.AVATAR, other_data=data, edit_origin=self.has_origin, components=btn)

    try:
      _ = await self.ctx.bot.wait_for_component(components=btn, timeout=45)
    except TimeoutError:
      if m:
        await m.edit(components=[])


  async def run_global(self, target: Optional[Union[ipy.User, ipy.Member, ipy.Snowflake]] = None):
    await self.defer(suppress_error=True, edit_origin=self.has_origin)

    if isinstance(target, ipy.Snowflake):
      target = await self.ctx.guild.fetch_member(target) or await self.ctx.bot.fetch_user(target)
    else:
      target = target or self.caller_user

    has_server_avatar = isinstance(target, ipy.Member) and target.guild_avatar

    if isinstance(target, ipy.Member):
      target = target.user
    self.set_target(target)

    data = {
      "target_avatar": target.avatar.as_url(),
      "avatar_mode": "global",
    }
    btn = ipy.Button(
      label="Server Avatar",
      emoji=settings.emoji.gallery,
      style=ipy.ButtonStyle.BLURPLE,
      custom_id=customids.USER_AVATAR_SERVER.id(target.id),
    ) if has_server_avatar else None

    m = await self.send(self.Templates.AVATAR, other_data=data, edit_origin=self.has_origin, components=btn)

    if btn:
      try:
        _ = await self.ctx.bot.wait_for_component(components=btn, timeout=45)
      except TimeoutError:
        if m:
          await m.edit(components=[])