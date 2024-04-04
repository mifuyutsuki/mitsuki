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

from mitsuki import bot
from mitsuki.messages import load_message


class MitsukiInfo(Extension):
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
    await ctx.defer()
    user = user or ctx.author

    # Obtaining the user banner is not stable, skipping relevant exception
    # Currently, there's no known way to fetch a user's server profile banner.
    try:
      fetched = await bot.fetch_user(user.id, force=True)
      banner = fetched.banner.url if fetched and fetched.banner else None
    except Exception:
      banner = None
    
    escapes = [
      "target_globalname",
      "target_dispname",
      "target_nickname",
      "target_username",
      "guild_name",
    ]

    data = {
      "target_globalname": user.global_name or "-",
      "target_dispname": user.display_name,
      "target_username": user.tag,
      "target_usericon": user.display_avatar.url,
      "target_user_id": user.id,
      "target_userbanner": banner,
      "created_at": user.created_at.format("f")
    }
    if isinstance(user, Member):
      data |= {
        "guild_name": user.guild.name,
        "guild_id": user.guild.id,
        "target_nickname": user.nickname or "-",
        "joined_at": user.joined_at.format("f"),
        "is_booster": "Yes" if user.premium else "No"
      }
      color = None
      pos = 0
      for role in user.roles:
        if role.color != "#000000" and role.position > pos:
          color = role.color.value
          pos = role.position
      
      message = load_message(
        "info_user_member",
        data=data,
        user=ctx.author,
        escape_data_values=escapes,
        color=color
      )
    else:
      message = load_message(
        "info_user_user",
        data=data,
        user=ctx.author,
        escape_data_values=escapes
      )
    
    await ctx.send(**message.to_dict())