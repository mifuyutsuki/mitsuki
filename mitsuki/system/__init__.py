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
from typing import Optional

from . import commands


class SystemModule(Extension):  
  @slash_command(
    name="system",
    description="System commands",
  )
  async def system_cmd(self, ctx: SlashContext):
    pass

  @system_cmd.subcommand(
    sub_cmd_name="set-nickname",
    sub_cmd_description="Set bot nickname in the current server",
  )
  @slash_option(
    name="nickname",
    description="Nickname to be set (1-32 characters), leave unset to clear nickname",
    required=False,
    opt_type=OptionType.STRING,
    max_length=32,
  )
  async def set_nickname_cmd(self, ctx: SlashContext, nickname: Optional[str] = None):
    await commands.Nickname.create(ctx).run(nickname)