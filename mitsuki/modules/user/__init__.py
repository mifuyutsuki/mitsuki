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

from mitsuki.lib.commands import CustomID

from . import commands, customids


class UserModule(ipy.Extension):
  user_cmd = ipy.SlashCommand(
    name="user",
    description="User information and tools"
  )

  # ===============================================================================================
  # User Info
  # ===============================================================================================

  @user_cmd.subcommand(
    sub_cmd_name="info",
    sub_cmd_description="Information about yourself or another user"
  )
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  @ipy.slash_option(
    name="user",
    description="User to view, defaults to self",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def info_cmd(self, ctx: ipy.SlashContext, user: ipy.BaseUser = None):
    await commands.UserInfo.create(ctx).run(user)

  @ipy.component_callback(customids.USER_INFO.string_id_pattern())
  async def info_btn(self, ctx: ipy.ComponentContext):
    await commands.UserInfo.create(ctx).run(CustomID.get_snowflake_from(ctx))

  @ipy.component_callback(customids.USER_INFO_SERVER.string_id_pattern())
  async def info_server_btn(self, ctx: ipy.ComponentContext):
    await commands.UserInfo.create(ctx).run_member(CustomID.get_snowflake_from(ctx), view_global=False)

  @ipy.component_callback(customids.USER_INFO_GLOBAL.string_id_pattern())
  async def info_global_btn(self, ctx: ipy.ComponentContext):
    await commands.UserInfo.create(ctx).run_member(CustomID.get_snowflake_from(ctx), view_global=True)

  # ===============================================================================================
  # Avatar Info
  # ===============================================================================================

  @user_cmd.subcommand(
    sub_cmd_name="avatar",
    sub_cmd_description="View avatar of user"
  )
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  @ipy.slash_option(
    name="user",
    description="User to view, defaults to self",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def avatar_cmd(self, ctx: ipy.SlashContext, user: ipy.BaseUser = None):
    await commands.UserAvatar.create(ctx).run(user)

  @ipy.component_callback(customids.USER_AVATAR.string_id_pattern())
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  async def avatar_btn(self, ctx: "ipy.ComponentContext"):
    await commands.UserAvatar.create(ctx).run(CustomID.get_snowflake_from(ctx))

  @ipy.component_callback(customids.USER_AVATAR_GLOBAL.string_id_pattern())
  async def avatar_global_btn(self, ctx: "ipy.ComponentContext"):
    await commands.UserAvatar.create(ctx).run_global(CustomID.get_snowflake_from(ctx))

  @ipy.component_callback(customids.USER_AVATAR_SERVER.string_id_pattern())
  async def avatar_server_btn(self, ctx: "ipy.ComponentContext"):
    await commands.UserAvatar.create(ctx).run_server(CustomID.get_snowflake_from(ctx))