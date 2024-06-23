# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import User, Member, Button, ButtonStyle
from attrs import define, field
from enum import StrEnum
from typing import Optional, Union

from mitsuki.utils import is_caller, get_member_color_value
from mitsuki.lib.commands import AsDict, ReaderCommand, TargetMixin


class UserInfo(TargetMixin, ReaderCommand):
  state: "UserInfo.States"
  data: "UserInfo.Data"
  member_data: Optional["UserInfo.MemberData"] = None

  class States(StrEnum):
    USER = "info_user_user"
    MEMBER = "info_user_member"

  @define(slots=False)
  class Data(AsDict):
    target_globalname: str
    target_dispname: str
    target_userbanner: str
    created_at: str

  @define(slots=False)
  class MemberData(AsDict):
    guild_name: str
    guild_id: int
    joined_at: str
    target_nickname: str
    is_booster: str


  async def run(self, target: Optional[Union[User, Member]] = None):
    self.set_target(target := target or self.caller_user)
    await self.defer(suppress_error=True)

    escapes = [
      "target_globalname",
      "target_dispname",
      "target_nickname",
      "guild_name",
    ]

    try:
      fetched = await self.ctx.bot.fetch_user(self.target_user, force=True)
      banner = fetched.banner.url if fetched and fetched.banner else None
    except Exception:
      banner = None

    self.data = self.Data(
      target_globalname=target.global_name or target.username,
      target_dispname=target.display_name,
      target_userbanner=banner,
      created_at=target.created_at.format("f"),
    )
    if isinstance(target, Member):
      self.member_data = self.MemberData(
        guild_name=target.guild.name,
        guild_id=target.guild.id,
        joined_at=target.joined_at.format("f"),
        target_nickname=target.nick or "-",
        is_booster="Yes" if target.premium else "No",
      )
      self.set_state(self.States.MEMBER)
      await self.send(
        other_data=self.member_data.asdict(),
        template_kwargs=dict(escape_data_values=escapes, color=get_member_color_value(target)),
      )
    else:
      self.set_state(self.States.USER)
      await self.send(template_kwargs=dict(escape_data_values=escapes, color=None))


class AvatarInfo(TargetMixin, ReaderCommand):
  state: "AvatarInfo.States"

  class States(StrEnum):
    AVATAR = "info_avatar"


  async def run(self, target: Optional[Union[User, Member]] = None):
    self.set_target(target or self.caller_user)
    self.set_state(self.States.AVATAR)
    await self.defer(suppress_error=True)

    if isinstance(self.target_user, Member) and self.target_user.guild_avatar:
      await self._run_with_server_avatar()
    else:
      await self._run_without_server_avatar()


  async def _run_with_server_avatar(self):
    guild_name = self.target_user.guild.name
    view_global = False

    while True:
      if view_global:
        avatar = self.target_user.user.avatar.url
        btn = Button(label="Server Avatar", style=ButtonStyle.BLURPLE)
      else:
        avatar = self.target_user.guild_avatar.url
        btn = Button(label="Global Avatar", style=ButtonStyle.BLURPLE)

      _ = await self.send(
        other_data={
          "guild_name": guild_name,
          "target_avatar": avatar,
          "avatar_mode": "global" if view_global else "server"
        },
        edit_origin=True,
        components=btn
      )
      try:
        response = await self.ctx.bot.wait_for_component(components=btn, timeout=45, check=is_caller(self.ctx))
      except TimeoutError:
        if response.ctx.message:
          await response.ctx.message.edit(components=[])
        return
      else:
        self.set_ctx(response.ctx)
        view_global = not view_global


  async def _run_without_server_avatar(self):
    guild_name = self.target_user.guild.name
    avatar = self.target_user.avatar_url
    _ = await self.send(other_data={"guild_name": guild_name, "target_avatar": avatar, "avatar_mode": "global"})