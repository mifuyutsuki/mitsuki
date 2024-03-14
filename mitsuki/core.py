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
  SlashCommand,
  SlashContext,
  BaseContext
)
from interactions.api.events import Component
from mitsuki.messages import load_message
from mitsuki.version import __version__
from functools import partial

__all__ = (
  "help_command",
  "system_command",
)


help_command = SlashCommand(
  name="help",
  description="Help on available commands and other info"
)

system_command = partial(
  SlashCommand,
  name="system",
  description="System commands (bot owner only)"
)


# =============================================================================

class MitsukiCore(Extension):
  @help_command.subcommand(
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
  
  
  @help_command.subcommand(
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
