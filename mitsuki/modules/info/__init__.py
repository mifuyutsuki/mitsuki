# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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

from . import commands


class InfoModule(Extension):
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
    await commands.UserInfo.create(ctx).run(user)


  @info_cmd.subcommand(
    sub_cmd_name="avatar",
    sub_cmd_description="View avatar of user"
  )
  @cooldown(Buckets.USER, 1, 5.0)
  @slash_option(
    name="user",
    description="User to view, defaults to self",
    required=False,
    opt_type=OptionType.USER
  )
  async def avatar_cmd(self, ctx: SlashContext, user: BaseUser = None):
    await commands.AvatarInfo.create(ctx).run(user)