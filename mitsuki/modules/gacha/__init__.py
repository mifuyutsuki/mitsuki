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
from interactions.api.events import Startup
from typing import Optional
import os

from mitsuki import init_event, EXCLUSIVE_GUILDS
from mitsuki.lib.errors import UnderConstruction
from mitsuki.lib.commands import CustomID

from mitsuki.modules.gacha import customids, commands


# =============================================================================


class GachaModule(ipy.Extension):
  @ipy.slash_command(
    name="gacha",
    description="Roll your favorite characters and memories",
    contexts=[ipy.ContextType.GUILD],
    scopes=EXCLUSIVE_GUILDS,
  )
  async def gacha_cmd(self, ctx: ipy.SlashContext):
    pass

  # gacha_admin_cmd = gacha_cmd.group(
  #   name="admin",
  #   description="Gacha administration commands"
  # )


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="info",
    sub_cmd_description="View information on playing the gacha"
  )
  async def info_cmd(self, ctx: ipy.SlashContext):
    raise UnderConstruction()


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="shards",
    sub_cmd_description="View your or another user's amount of Shards"
  )
  @ipy.cooldown(ipy.Buckets.USER, 1, 3.0)
  @ipy.slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def shards_cmd(self, ctx: ipy.SlashContext, user: Optional[ipy.BaseUser] = None):
    await commands.GachaShards.create(ctx).run(user)


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="profile",
    sub_cmd_description="View your or another user's gacha profile"
  )
  @ipy.cooldown(ipy.Buckets.USER, 1, 3.0)
  @ipy.slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def profile_cmd(self, ctx: ipy.SlashContext, user: Optional[ipy.BaseUser] = None):
    await commands.GachaProfile.create(ctx).run(user)


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="daily",
    sub_cmd_description=f"Claim your gacha daily"
  )
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 3.0)
  async def daily_cmd(self, ctx: ipy.SlashContext):
    await commands.GachaDaily.create(ctx).run()


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="roll",
    sub_cmd_description="Roll gacha once using Shards"
  )
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 3.0)
  async def roll_cmd(self, ctx: ipy.SlashContext):
    # await commands.Roll.create(ctx).run2()
    raise UnderConstruction()


  @ipy.component_callback(customids.ROLL.string_id_pattern())
  async def roll_btn(self, ctx: ipy.ComponentContext):
    # await commands.Roll.create(ctx).run2(int(CustomID.get_id_from(ctx)))
    raise UnderConstruction()


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View a list of your or another user's collected cards"
  )
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  @ipy.slash_option(
    name="sort",
    description="Card sorting mode, default: latest acquired",
    required=False,
    opt_type=ipy.OptionType.STRING,
    choices=[
      ipy.SlashCommandChoice(name="Latest acquired", value="date"),
      ipy.SlashCommandChoice(name="Number acquired", value="count"),
      ipy.SlashCommandChoice(name="Rarity", value="rarity"),
      ipy.SlashCommandChoice(name="Name", value="alpha"),
      ipy.SlashCommandChoice(name="Series", value="series"),
      ipy.SlashCommandChoice(name="Card ID", value="id"),
    ]
  )
  @ipy.slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def cards_cmd(
    self,
    ctx: ipy.SlashContext,
    sort: Optional[str] = None,
    user: Optional[ipy.BaseUser] = None
  ):
    # await commands.Cards.create(ctx).run(user, sort)
    raise UnderConstruction()


  @ipy.component_callback(customids.CARDS.numeric_id_pattern())
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  async def cards_btn_cmd(self, ctx: ipy.ComponentContext):
    # return await commands.Cards.create(ctx).run_from_button()
    raise UnderConstruction()


  # ===========================================================================
  # ===========================================================================


  @gacha_cmd.subcommand(
    sub_cmd_name="gallery",
    sub_cmd_description="View a gallery of your or another user's collected cards"
  )
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  @ipy.slash_option(
    name="sort",
    description="Card sorting mode, default: latest acquired",
    required=False,
    opt_type=ipy.OptionType.STRING,
    choices=[
      ipy.SlashCommandChoice(name="Latest acquired", value="date"),
      ipy.SlashCommandChoice(name="Number acquired", value="count"),
      ipy.SlashCommandChoice(name="Rarity", value="rarity"),
      ipy.SlashCommandChoice(name="Name", value="alpha"),
      ipy.SlashCommandChoice(name="Series", value="series"),
      ipy.SlashCommandChoice(name="Card ID", value="id"),
    ]
  )
  @ipy.slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=ipy.OptionType.USER
  )
  async def gallery_cmd(
    self,
    ctx: ipy.SlashContext,
    sort: Optional[str] = None,
    user: Optional[ipy.BaseUser] = None
  ):
    # await commands.Gallery.create(ctx).run(user, sort)
    raise UnderConstruction()


  @ipy.component_callback(customids.GALLERY.numeric_id_pattern())
  @ipy.auto_defer(time_until_defer=2.0)
  @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  async def gallery_btn_cmd(self, ctx: ipy.ComponentContext):
    # return await commands.Gallery.create(ctx).run_from_button()
    raise UnderConstruction()


  # ===========================================================================
  # ===========================================================================


  # @gacha_cmd.subcommand(
  #   sub_cmd_name="view",
  #   sub_cmd_description="View an obtained card"
  # )
  # @ipy.auto_defer(time_until_defer=2.0)
  # @ipy.cooldown(ipy.Buckets.USER, 1, 5.0)
  # @ipy.slash_option(
  #   name="name",
  #   description="Card name to search",
  #   required=True,
  #   autocomplete=True,
  #   opt_type=ipy.OptionType.STRING,
  #   min_length=3,
  #   max_length=100
  # )
  # async def view_cmd(self, ctx: ipy.SlashContext, name: str):
  #   await commands.View.create(ctx).run(name)


  # @ipy.component_callback(customids.VIEW.string_id_pattern())
  # @ipy.auto_defer(time_until_defer=2.0)
  # @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  # async def view_btn_cmd(self, ctx: ipy.ComponentContext):
  #   return await commands.View.create(ctx).view_from_button()


  # @view_cmd.autocomplete("name")
  # async def view_cmd_autocomplete(self, ctx: ipy.AutocompleteContext):
  #   await commands.View.create(ctx).autocomplete(ctx.input_text)


  # ===========================================================================
  # ===========================================================================

  # @gacha_cmd.subcommand(
  #   sub_cmd_name="give",
  #   sub_cmd_description="Give Shards to another user"
  # )
  # @ipy.cooldown(ipy.Buckets.USER, 1, 15.0)
  # @ipy.auto_defer(time_until_defer=2.0)
  # @ipy.slash_option(
  #   name="target",
  #   description="User to give Shards to",
  #   required=True,
  #   opt_type=ipy.OptionType.USER
  # )
  # @ipy.slash_option(
  #   name="amount",
  #   description="Amount of Shards to give",
  #   required=True,
  #   opt_type=ipy.OptionType.INTEGER,
  #   min_value=1
  # )
  # async def give_cmd(
  #   self,
  #   ctx: ipy.SlashContext,
  #   target: ipy.BaseUser,
  #   amount: int
  # ):
  #   await commands.Give.create(ctx).run(target, amount)


  # ===========================================================================
  # ===========================================================================

  # @gacha_admin_cmd.subcommand(
  #   sub_cmd_name="give",
  #   sub_cmd_description="Give Shards to another user"
  # )
  # @ipy.slash_option(
  #   name="target",
  #   description="User to give Shards to",
  #   required=True,
  #   opt_type=ipy.OptionType.USER
  # )
  # @ipy.slash_option(
  #   name="amount",
  #   description="Amount of Shards to give",
  #   required=True,
  #   opt_type=ipy.OptionType.INTEGER,
  #   min_value=1
  # )
  # @ipy.auto_defer(ephemeral=True)
  # async def system_give_cmd(
  #   self,
  #   ctx: ipy.SlashContext,
  #   target: ipy.BaseUser,
  #   amount: int
  # ):
  #   await commands.GiveAdmin.create(ctx).run(target, amount)


  # ===========================================================================
  # ===========================================================================

  # @gacha_admin_cmd.subcommand(
  #   sub_cmd_name="reload",
  #   sub_cmd_description="Reload gacha configuration files"
  # )
  # @ipy.auto_defer(ephemeral=True)
  # async def system_reload_cmd(self, ctx: ipy.SlashContext):
  #   await commands.ReloadAdmin.create(ctx).run()


  # ===========================================================================
  # ===========================================================================

  # @gacha_admin_cmd.subcommand(
  #   sub_cmd_name="cards",
  #   sub_cmd_description="View the card roster"
  # )
  # @ipy.auto_defer(ephemeral=True)
  # async def system_cards_cmd(self, ctx: ipy.SlashContext):
  #   await commands.ViewAdmin.create(ctx).run(sort="id")