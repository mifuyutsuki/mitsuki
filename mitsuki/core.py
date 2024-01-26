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
  async def about(self, ctx: SlashContext):
    embed = ipy.Embed(
      title="About Mitsuki",
      description=(
        """\
        A little fun bot.

        Copyright (c) 2024 **Mifuyu** 
        Source code is available at <TBD>

        **Mitsuki** is available under the AGPL 3.0-or-later license. \
        This license does not extend to some assets, such as gacha cards. \
        All resources belong to their respective owners."""
      ),
      author=ipy.EmbedAuthor(
        name=ctx.user.display_name,
        icon_url=ctx.user.avatar_url
      ),
      color=0x237feb
    )

    await ctx.send(embed=embed)
  
  @help.subcommand(
    sub_cmd_name="license",
    sub_cmd_description="License information"
  )
  async def license_(self, ctx: SlashContext):
    embed = ipy.Embed(
      title="License",
      description=(
        """\
        Copyright (c) 2024 **Mifuyu** 
        Source code is available at <TBD>

        This program is free software: you can redistribute it and/or modify \
        it under the terms of the GNU Affero General Public License as \
        published by the Free Software Foundation, either version 3 of the \
        License, or (at your option) any later version.

        This program is distributed in the hope that it will be useful, \
        but WITHOUT ANY WARRANTY; without even the implied warranty of \
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the \
        GNU Affero General Public License for more details."""
      ),
      fields=[
        ipy.EmbedField(
          name="Additional Information",
          value=(
            """\
            **Mitsuki** uses art and data assets, such as gacha cards, which \
            are not covered by the above license. Contact the bot operator \
            for more information. All resources belong to their respective \
            owners."""
          )
        )
      ],
      author=ipy.EmbedAuthor(
        name=ctx.user.display_name,
        icon_url=ctx.user.avatar_url
      ),
      color=0x237feb
    )

    await ctx.send(embed=embed)
