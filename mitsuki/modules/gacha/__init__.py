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
  AllowedMentions,
  AutocompleteContext,
  Extension,
  slash_command,
  slash_option,
  slash_default_member_permission,
  SlashContext,
  SlashCommandChoice,
  StringSelectMenu,
  component_callback,
  ComponentContext,
  OptionType,
  BaseUser,
  User,
  Member,
  Permissions,
  check,
  is_owner,
  auto_defer,
  listen,
  cooldown,
  Buckets,
)
from interactions.api.events import Startup
from typing import Optional

from mitsuki import init_event

from . import commands
from .gachaman import gacha


# =============================================================================


class GachaModule(Extension):
  @listen(Startup)
  async def on_startup(self):
    await init_event.wait()
    await gacha.sync_db()


  @slash_command(
    name="gacha",
    description="Roll your favorite characters and memories",
    dm_permission=False
  )
  async def gacha_cmd(self, ctx: SlashContext):
    pass

  gacha_admin_cmd = gacha_cmd.group(
    name="admin",
    description="Gacha administration commands"
  )

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="details",
    sub_cmd_description="View details on playing the gacha"
  )
  async def details_cmd(self, ctx: SlashContext):
    await commands.Details.create(ctx).run()

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="shards",
    sub_cmd_description="View your or another user's amount of Shards"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 3.0)
  @slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=OptionType.USER
  )
  async def shards_cmd(self, ctx: SlashContext, user: Optional[BaseUser] = None):
    await commands.Shards.create(ctx).run(user)

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="profile",
    sub_cmd_description="View your or another user's gacha profile"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 3.0)
  @slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=OptionType.USER
  )
  async def profile_cmd(self, ctx: SlashContext, user: Optional[BaseUser] = None):
    await commands.Profile.create(ctx).run(user)

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="daily",
    sub_cmd_description=f"Claim your gacha daily"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 3.0)
  async def daily_cmd(self, ctx: SlashContext):
    await commands.Daily.create(ctx).run()

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="roll",
    sub_cmd_description="Roll gacha once using Shards"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 3.0)
  async def roll_cmd(self, ctx: SlashContext):
    await commands.Roll.create(ctx).run()

  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View a list of your or another user's collected cards"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  @slash_option(
    name="sort",
    description="Card sorting mode, default: latest acquired",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
      SlashCommandChoice(name="Latest acquired", value="date"),
      SlashCommandChoice(name="Number acquired", value="count"),
      SlashCommandChoice(name="Rarity", value="rarity"),
      SlashCommandChoice(name="Name", value="alpha"),
      SlashCommandChoice(name="Series", value="series"),
      SlashCommandChoice(name="Card ID", value="id"),
    ]
  )
  @slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=OptionType.USER
  )
  async def cards_cmd(
    self,
    ctx: SlashContext,
    sort: Optional[str] = None,
    user: Optional[BaseUser] = None
  ):
    await commands.Cards.create(ctx).run(user, sort)

  @component_callback(commands.CustomIDs.CARDS.numeric_id_pattern())
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  async def cards_btn_cmd(self, ctx: ComponentContext):
    return await commands.Cards.create(ctx).run_from_button()


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="gallery",
    sub_cmd_description="View a gallery of your or another user's collected cards"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  @slash_option(
    name="sort",
    description="Card sorting mode, default: latest acquired",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
      SlashCommandChoice(name="Latest acquired", value="date"),
      SlashCommandChoice(name="Number acquired", value="count"),
      SlashCommandChoice(name="Rarity", value="rarity"),
      SlashCommandChoice(name="Name", value="alpha"),
      SlashCommandChoice(name="Series", value="series"),
      SlashCommandChoice(name="Card ID", value="id"),
    ]
  )
  @slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=OptionType.USER
  )
  async def gallery_cmd(
    self,
    ctx: SlashContext,
    sort: Optional[str] = None,
    user: Optional[BaseUser] = None
  ):
    await commands.Gallery.create(ctx).run(user, sort)

  @component_callback(commands.CustomIDs.GALLERY.numeric_id_pattern())
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  async def gallery_btn_cmd(self, ctx: ComponentContext):
    return await commands.Gallery.create(ctx).run_from_button()


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="view",
    sub_cmd_description="View an obtained card"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 5.0)
  @slash_option(
    name="name",
    description="Card name to search",
    required=True,
    autocomplete=True,
    opt_type=OptionType.STRING,
    min_length=3,
    max_length=128
  )
  @slash_option(
    name="user",
    description="View cards in a user's collection",
    required=False,
    opt_type=OptionType.USER
  )
  async def view_cmd(
    self,
    ctx: SlashContext,
    name: str,
    user: Optional[BaseUser] = None
  ):
    await commands.View.create(ctx).run(name, user)

  @component_callback(commands.CustomIDs.VIEW.string_id_pattern())
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  async def view_btn_cmd(self, ctx: ComponentContext):
    return await commands.View.create(ctx).run_from_button()

  @view_cmd.autocomplete("name")
  async def view_cmd_autocomplete(self, ctx: AutocompleteContext):
    await commands.View.create(ctx).autocomplete(ctx.input_text)


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="give",
    sub_cmd_description="Give Shards to another user"
  )
  @cooldown(Buckets.USER, 1, 15.0)
  @auto_defer(time_until_defer=2.0)
  @slash_option(
    name="target",
    description="User to give Shards to",
    required=True,
    opt_type=OptionType.USER
  )
  @slash_option(
    name="amount",
    description="Amount of Shards to give",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=1
  )
  async def give_cmd(
    self,
    ctx: SlashContext,
    target: BaseUser,
    amount: int
  ):
    await commands.Give.create(ctx).run(target, amount)


  # ===========================================================================
  # ===========================================================================

  @gacha_admin_cmd.subcommand(
    sub_cmd_name="give",
    sub_cmd_description="Give Shards to another user"
  )
  @slash_option(
    name="target",
    description="User to give Shards to",
    required=True,
    opt_type=OptionType.USER
  )
  @slash_option(
    name="amount",
    description="Amount of Shards to give",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=1
  )
  @auto_defer(ephemeral=True)
  async def system_give_cmd(
    self,
    ctx: SlashContext,
    target: BaseUser,
    amount: int
  ):
    await commands.GiveAdmin.create(ctx).run(target, amount)


  # ===========================================================================
  # ===========================================================================

  @gacha_admin_cmd.subcommand(
    sub_cmd_name="reload",
    sub_cmd_description="Reload gacha configuration files"
  )
  @auto_defer(ephemeral=True)
  async def system_reload_cmd(self, ctx: SlashContext):
    await commands.ReloadAdmin.create(ctx).run()


  # ===========================================================================
  # ===========================================================================

  @gacha_admin_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View the card roster"
  )
  @auto_defer(ephemeral=True)
  async def system_cards_cmd(self, ctx: SlashContext):
    await commands.ViewAdmin.create(ctx).run(sort="id")