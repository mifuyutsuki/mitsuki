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

from . import commands


class ServerModule(ipy.Extension):
  server_cmd: "ipy.SlashCommand" = ipy.SlashCommand(
    name="server",
    description="Server-level tools",
    contexts=[ipy.ContextType.GUILD]
  )

  # ===============================================================================================
  # Set Nickname
  # ===============================================================================================

  @server_cmd.subcommand(
    sub_cmd_name="set-nickname",
    sub_cmd_description="Set bot nickname in the current server (requires Manage Nickname)",
  )
  @ipy.slash_option(
    name="nickname",
    description="Nickname to be set (1-32 characters), leave unset to clear nickname",
    required=False,
    opt_type=ipy.OptionType.STRING,
    max_length=32,
  )
  async def server_nickname_cmd(self, ctx: ipy.SlashContext, nickname: Optional[str] = None):
    return await commands.ServerNickname.create(ctx).run(nickname)

  # ===============================================================================================
  # Server Info
  # ===============================================================================================

  @server_cmd.subcommand(
    sub_cmd_name="info",
    sub_cmd_description="View information about this server",
  )  
  async def server_info_cmd(self, ctx: ipy.SlashContext):
    return await commands.ServerInfo.create(ctx).run()