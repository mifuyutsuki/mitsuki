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

from mitsuki import init_event
from . import commands, customids, presencer

import os
import logging

logger = logging.getLogger(__name__)


try:
  SYSTEM_GUILD_ID = ipy.Snowflake(os.environ.get("SYSTEM_GUILD_ID"))
except Exception:
  SYSTEM_GUILD_ID = None

if SYSTEM_GUILD_ID:
  SYSTEM_GUILDS = [SYSTEM_GUILD_ID]
else:
  SYSTEM_GUILDS = [ipy.GLOBAL_SCOPE]


class SystemModule(ipy.Extension):
  @ipy.listen(ipy.events.Ready)
  async def on_ready(self, event: ipy.events.Ready):
    await init_event.wait()

    presencer.set_presencer(self.bot)
    await presencer.presencer().init()


  # TODO: Make this module DM only (ContextType.BOT_DM)
  system_cmd = ipy.SlashCommand(
    name="system",
    description="System commands (requires bot owner)",
    scopes=SYSTEM_GUILDS,
    contexts=[ipy.ContextType.GUILD],
  )

  # ===============================================================================================
  # Manage Presences
  # ===============================================================================================

  @system_cmd.subcommand(
    sub_cmd_name="presences",
    sub_cmd_description="Manage bot presences",
  )
  async def system_presences_cmd(self, ctx: ipy.SlashContext):
    await commands.SystemPresences.create(ctx).run()

  @ipy.component_callback(customids.SYSTEM_PRESENCES)
  async def system_presences_btn(self, ctx: ipy.ComponentContext):
    await commands.SystemPresences.create(ctx).run()

  # ===============================================================================================

  @ipy.component_callback(customids.SYSTEM_PRESENCES_ADD.prompt())
  async def system_presences_add_prompt(self, ctx: ipy.ComponentContext):
    await commands.SystemPresencesAdd.create(ctx).prompt()

  @ipy.modal_callback(customids.SYSTEM_PRESENCES_ADD.response())
  async def system_presences_add_response(self, ctx: ipy.ModalContext, name: str):
    await commands.SystemPresencesAdd.create(ctx).response(name)

  # ===============================================================================================

  # @ipy.component_callback(customids.SYSTEM_PRESENCES_EDIT.numeric_id_pattern())
  # async def system_presences_edit_btn(self, ctx: ipy.ComponentContext):
  #   pass

  # @ipy.component_callback(customids.SYSTEM_PRESENCES_EDIT.select())
  # async def system_presences_edit_select(self, ctx: ipy.ComponentContext):
  #   pass

  # @ipy.component_callback(customids.SYSTEM_PRESENCES_EDIT.prompt().numeric_id_pattern())
  # async def system_presences_edit_prompt(self, ctx: ipy.ComponentContext):
  #   pass

  # @ipy.modal_callback(customids.SYSTEM_PRESENCES_EDIT.response().numeric_id_pattern())
  # async def system_presences_edit_response(self, ctx: ipy.ModalContext):
  #   pass

  # ===============================================================================================

  # @ipy.component_callback(customids.SYSTEM_PRESENCES_DELETE.confirm().numeric_id_pattern())
  # async def system_presences_delete_confirm(self, ctx: ipy.ComponentContext):
  #   await commands.SystemPresencesDelete.create(ctx).confirm(customids.CustomID.get_int_from(ctx))

  @ipy.component_callback(customids.SYSTEM_PRESENCES_DELETE.numeric_id_pattern())
  async def system_presences_delete(self, ctx: ipy.ComponentContext):
    await commands.SystemPresencesDelete.create(ctx).delete(customids.CustomID.get_int_from(ctx))

  # ===============================================================================================
  # Manage Templates
  # ===============================================================================================

  system_templates_cmd = system_cmd.group(
    name="templates",
    description="Manage bot templates"
  )

  @system_templates_cmd.subcommand(
    sub_cmd_name="reload",
    sub_cmd_description="Reload bot templates"
  )
  async def system_templates_cmd(self, ctx: ipy.SlashContext):
    await commands.ReloadTemplates.create(ctx).run()


def setup(bot: ipy.Client):
  if not SYSTEM_GUILD_ID:
    logger.warning("System guild is not specified, which is needed to restrict scope of system commands")
  SystemModule(bot)