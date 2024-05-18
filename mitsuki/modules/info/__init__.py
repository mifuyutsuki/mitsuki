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
  Client,
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
  MemberConverter,
)
from interactions.ext.prefixed_commands import (
  prefixed_command,
  PrefixedContext,
)
from interactions.client.errors import (
  BadArgument,
)

from . import commands

from typing import Optional


class InfoModule(Extension):
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
    await commands.UserInfo.create(ctx).run(user)


  @prefixed_command(
    name="user",
    aliases=["u"],
  )
  async def user_cmd_prefixed(self, ctx: PrefixedContext, *, user: Optional[str] = None):
    if user:
      try:
        select_user = await MemberConverter().convert(ctx, user)
      except BadArgument:
        return
    else:
      select_user = ctx.author
    await commands.UserInfo.create(ctx).run(select_user)