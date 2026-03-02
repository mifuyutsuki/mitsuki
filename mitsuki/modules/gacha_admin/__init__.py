# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""
Gacha administration commands.

Commands in this module is part of the `gacha-admin` namespace, which is
scope-limited to System Guild.
"""

import interactions as ipy
from typing import Optional, Union
import os

from mitsuki.lib.errors import UnderConstruction
from mitsuki.lib.view import timeout_resetter
from mitsuki.modules.gacha_admin import commands, customids


try:
  SYSTEM_GUILD_ID = ipy.Snowflake(os.environ.get("SYSTEM_GUILD_ID"))
except Exception:
  SYSTEM_GUILD_ID = None

if SYSTEM_GUILD_ID:
  SYSTEM_GUILDS = [SYSTEM_GUILD_ID]
else:
  SYSTEM_GUILDS = [ipy.GLOBAL_SCOPE]


class GachaAdminModule(ipy.Extension):
  @ipy.slash_command(
    name="gacha-admin",
    description="Mitsuki Gacha management commands",
    contexts=[ipy.ContextType.GUILD],
    scopes=SYSTEM_GUILDS,
  )
  async def gacha_admin_cmd(self, ctx: ipy.SlashContext):
    pass


  @gacha_admin_cmd.subcommand(
    sub_cmd_name="sync",
    sub_cmd_description="Sync cached Gacha data with database",
  )
  async def gacha_admin_sync_cmd(self, ctx: ipy.SlashContext):
    await commands.GachaSync.create(ctx).run()


  @gacha_admin_cmd.subcommand(
    sub_cmd_name="upload",
    sub_cmd_description="Upload a gacha data file",
  )
  @ipy.slash_option(
    name="type",
    description="Type of file to upload",
    opt_type=ipy.OptionType.STRING,
    choices=[
      ipy.SlashCommandChoice("Roster update (yaml)", "roster_yaml"),
      ipy.SlashCommandChoice("Season data (yaml)", "season_yaml"),
    ],
    required=True,
  )
  @ipy.slash_option(
    name="file",
    description="File to upload",
    opt_type=ipy.OptionType.ATTACHMENT,
    required=True,
  )
  async def gacha_admin_upload_cmd(self, ctx: ipy.SlashContext, type: str, file: ipy.Attachment):
    match type:
      case "roster_yaml":
        await commands.RosterUpload.create(ctx).run(file)
      # case "roster_csv":
      #   raise UnderConstruction()
      case "season_yaml":
        await commands.SeasonUpload.create(ctx).run(file)
      case _:
        raise ValueError(f"Unexpected choice value for /gacha-admin upload: {type}")


  @ipy.component_callback(customids.ROSTER_UPLOAD.string_id_pattern())
  async def gacha_admin_upload_roster_btn(self, ctx: ipy.ComponentContext):
    uuid = customids.ROSTER_UPLOAD.get_id_from(ctx)
    await commands.RosterUpload.create(ctx).proceed(uuid)


  @ipy.component_callback(customids.SEASON_UPLOAD.string_id_pattern())
  async def gacha_admin_upload_season_btn(self, ctx: ipy.ComponentContext):
    uuid = customids.SEASON_UPLOAD.get_id_from(ctx)
    await commands.SeasonUpload.create(ctx).proceed(uuid)