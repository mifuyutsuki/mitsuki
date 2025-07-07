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

from . import commands
from .customids import CustomIDs


class InfoModule(ipy.Extension):
  info_cmd = ipy.SlashCommand(
    name="info",
    description="Informational commands"
  )

  # ===============================================================================================
  # User Info
  # ===============================================================================================

  @info_cmd.subcommand(
    sub_cmd_name="user",
    sub_cmd_description="Information about yourself or another user"
  )
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  @ipy.slash_option(
    name="user",
    description="User to view, defaults to self",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def user_cmd(self, ctx: "ipy.SlashContext", user: "ipy.BaseUser" = None):
    await commands.UserInfo.create(ctx).run(user)

  # ===============================================================================================
  # Avatar Info
  # ===============================================================================================

  @info_cmd.subcommand(
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
  async def avatar_cmd(self, ctx: "ipy.SlashContext", user: "ipy.BaseUser" = None):
    await commands.AvatarInfo.create(ctx).run(user)

  @ipy.component_callback(CustomIDs.INFO_AVATAR_GLOBAL.string_id_pattern())
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  async def avatar_global_btn(self, ctx: "ipy.ComponentContext"):
    await commands.AvatarInfo.create(ctx).run_global(CustomID.get_snowflake_from(ctx))

  @ipy.component_callback(CustomIDs.INFO_AVATAR_SERVER.string_id_pattern())
  @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  async def avatar_server_btn(self, ctx: "ipy.ComponentContext"):
    await commands.AvatarInfo.create(ctx).run_server(CustomID.get_snowflake_from(ctx))