# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import (
  Extension,
  slash_command,
  slash_option,
  SlashContext,
  OptionType,
  BaseUser,
  Member,
  User,
  cooldown,
  Buckets,
)

from mitsuki import bot
from mitsuki.lib.commands import AsDict, ReaderCommand, TargetMixin
from attrs import define, field
from enum import StrEnum
from typing import Optional, Union


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
    color = None
    try:
      fetched = await bot.fetch_user(self.target_user, force=True)
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
      pos = 0
      for role in target.roles:
        if role.color != "#000000" and role.position > pos:
          color = role.color.value
          pos = role.position

      self.member_data = self.MemberData(
        guild_name=target.guild.name,
        guild_id=target.guild.id,
        joined_at=target.joined_at.format("f"),
        target_nickname=target.nick or "-",
        is_booster="Yes" if target.premium else "No",
      )
      self.set_state(self.States.MEMBER)
      await self.send(
        other_data=self.member_data.asdict(), template_kwargs=dict(escape_data_values=escapes), color=color
      )
    else:
      self.set_state(self.States.USER)
      await self.send(template_kwargs=dict(escape_data_values=escapes))


class MitsukiInfo(Extension):
  @slash_command(
    name="info",
    description="Informational commands"
  )
  async def info_cmd(self, ctx: SlashContext):
    pass


  @info_cmd.subcommand(
    sub_cmd_name="user",
    sub_cmd_description="Information about yourself or another user"
  )
  @cooldown(Buckets.USER, 1, 5.0)
  @slash_option(
    name="user",
    description="User to view, defaults to self",
    required=False,
    opt_type=OptionType.USER
  )
  async def user_cmd(self, ctx: SlashContext, user: BaseUser = None):
    await UserInfo.create(ctx).run(user)