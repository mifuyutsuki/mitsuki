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
  SlashContext,
  component_callback,
  Button,
  ButtonStyle,
  ComponentContext,
  InteractionContext,
)
from interactions.client.errors import HTTPException

from mitsuki import __version__
from mitsuki.lib.messages import load_message


class AboutModule(Extension):
  @slash_command(
    name="about",
    description="About this bot"
  )
  async def about_cmd(self, ctx: SlashContext):
    await self.view_about.callback(ctx)


  @component_callback("about")
  async def view_about(self, ctx: InteractionContext):
    message = load_message(
      "help_about",
      data={"version": __version__},
      user=ctx.author
    )
    license_btn = Button(label="AGPL-3.0", style=ButtonStyle.BLURPLE, custom_id="license")

    if hasattr(ctx, "edit_origin"):
      m = await ctx.edit_origin(**message.to_dict(), components=license_btn)
    else:
      m = await ctx.send(**message.to_dict(), components=license_btn)

    try:
      _ = await ctx.bot.wait_for_component(components=license_btn, timeout=45)
    except TimeoutError:
      if m:
        await m.edit(components=[])


  @component_callback("license")
  async def view_license(self, ctx: InteractionContext):
    message = load_message(
      "help_license",
      data={"version": __version__},
      user=ctx.author
    )

    about_btn = Button(label="About the bot", style=ButtonStyle.BLURPLE, custom_id="about")
    if hasattr(ctx, "edit_origin"):
      m = await ctx.edit_origin(**message.to_dict(), components=about_btn)
    else:
      m = await ctx.send(**message.to_dict(), components=about_btn)

    try:
      _ = await ctx.bot.wait_for_component(components=about_btn, timeout=45)
    except TimeoutError:
      if m:
        await m.edit(components=[])