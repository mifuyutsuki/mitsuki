# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy
from interactions import Extension
from interactions import slash_command, SlashContext

from mitsuki.messages import load_message
from mitsuki.version import __version__


class MitsukiCore(Extension):
  @slash_command(
    name="help",
    description="Help on available commands and other info"
  )
  async def help(self, ctx: SlashContext):
    pass

  @help.subcommand(
    sub_cmd_name="about",
    sub_cmd_description="About this bot"
  )
  async def about_cmd(self, ctx: SlashContext):
    message = load_message(
      "help_about",
      data={"version": __version__},
      user=ctx.author
    )
    await ctx.send(**message.to_dict())
  
  @help.subcommand(
    sub_cmd_name="license",
    sub_cmd_description="License information"
  )
  async def license_cmd(self, ctx: SlashContext):
    message = load_message(
      "help_license",
      data={"version": __version__},
      user=ctx.author
    )
    await ctx.send(**message.to_dict())
