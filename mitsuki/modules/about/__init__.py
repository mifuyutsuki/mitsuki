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
  SlashContext,
)

from mitsuki import __version__
from mitsuki.lib.messages import load_message


class AboutModule(Extension):
  @slash_command(
    name="about",
    description="About this bot"
  )
  async def about_cmd(self, ctx: SlashContext):
    message = load_message(
      "help_about",
      data={"version": __version__},
      user=ctx.author
    )
    await ctx.send(**message.to_dict())


  @slash_command(
    name="license",
    description="License information of this bot"
  )
  async def license_cmd(self, ctx: SlashContext):
    message = load_message(
      "help_license",
      data={"version": __version__},
      user=ctx.author
    )
    await ctx.send(**message.to_dict())