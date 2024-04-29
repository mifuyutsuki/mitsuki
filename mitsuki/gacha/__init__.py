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
from interactions.client.errors import HTTPException
from mitsuki.paginators import Paginator
from rapidfuzz import fuzz, process
from typing import Optional

from mitsuki import bot, init_event
from mitsuki import settings
from mitsuki.messages import (
  load_message,
  load_multipage,
  load_multifield,
)
from mitsuki.core import system_command
from mitsuki.utils import is_caller, process_text, suppressed_defer
from mitsuki.userdata import new_session, initialize
from mitsuki.gacha import userdata, commands
from mitsuki.gacha.gachaman import gacha
from mitsuki.gacha.schema import SourceCard


# =============================================================================


system_gacha_command = system_command(
  group_name="gacha",
  group_description="Manage gacha system"
)


def currency_data():
  return {
    "currency": gacha.currency,
    "currency_icon": gacha.currency_icon,
    "currency_name": gacha.currency_name,
  }


def bot_data():
  return {
    "bot_user": bot.user.mention,
    "bot_username": bot.user.display_name,
    "bot_usericon": bot.user.avatar_url
  }


def card_data(card: SourceCard):
  stars       = gacha.stars[card.rarity]
  color       = gacha.colors[card.rarity]
  dupe_shards = gacha.dupe_shards[card.rarity]

  return {
    "id"          : card.id,
    "type"        : card.type,
    "series"      : card.series,
    "name"        : card.name,
    "image"       : card.image,
    "stars"       : stars,
    "color"       : color,
    "dupe_shards" : dupe_shards,
    "card_id"     : card.id      # Alias used by /admin gacha cards
  }


# =============================================================================


class MitsukiGacha(Extension):
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
    sub_cmd_description="View your or another user's collected cards"
  )
  @auto_defer(time_until_defer=2.0)
  @cooldown(Buckets.USER, 1, 15.0)
  @slash_option(
    name="mode",
    description="Card viewing mode, default: list",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
      SlashCommandChoice(name="list", value="list"),
      SlashCommandChoice(name="deck", value="deck"),
    # SlashCommandChoice(name="compact", value="compact")
    ]
  )
  @slash_option(
    name="sort",
    description="Card sorting mode, default: rarity (list mode), acquired (deck mode)",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
      SlashCommandChoice(name="Rarity", value="rarity"),
      SlashCommandChoice(name="Name", value="alpha"),
      SlashCommandChoice(name="First acquired", value="date"),
      SlashCommandChoice(name="Series", value="series"),
      SlashCommandChoice(name="Number acquired", value="count"),
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
    mode: Optional[str] = "list",
    sort: Optional[str] = None,
    user: Optional[BaseUser] = None
  ):
    if mode == "deck":
      await commands.Gallery.create(ctx).run(user, sort)
    else:
      await commands.Cards.create(ctx).run(user, sort)


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
    # autocomplete=True,
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


  # @view_cmd.autocomplete("name")
  # async def view_cmd_autocomplete(self, ctx: AutocompleteContext):
  #   search_key     = ctx.input_text
  #   if len(search_key) < 3:
  #     return await ctx.send([])
    
  #   search_results = await userdata.card_search(
  #     search_key,
  #     search_by="name",
  #     sort="match",
  #     limit=6,
  #     cutoff=55.0,
  #     strong_cutoff=None,
  #     ratio=fuzz.token_ratio,
  #     processor=process_text
  #   )
    
  #   await ctx.send([
  #     {"name": f"{card.name} • {card.type} • {card.series}", "value": card.name}
  #     for card in search_results
  #   ])


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="give",
    sub_cmd_description="Give Shards to another user"
  )
  @cooldown(Buckets.USER, 1, 15.0)
  @auto_defer(time_until_defer=2.0)
  @slash_option(
    name="target_user",
    description="User to give Shards to",
    required=True,
    opt_type=OptionType.USER
  )
  @slash_option(
    name="shards",
    description="Amount of Shards to give",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=1
  )
  async def give_cmd(
    self,
    ctx: SlashContext,
    target_user: BaseUser,
    shards: int
  ):
    user       = ctx.author
    own_shards = await userdata.shards(user.id)

    # NOTE: don't defer, otherwise the cmd fails to ping the target user
    
    # ---------------------------------------------------------------
    # Check invalids
    
    if user.id == target_user.id:
      message = load_message("gacha_give_self", user=ctx.author)
      await ctx.send(**message.to_dict())
      return
    
    if target_user.bot:
      message = load_message("gacha_give_bot", user=ctx.author)
      await ctx.send(**message.to_dict())
      return
    
    if isinstance(target_user, User):
      message = load_message("gacha_give_nonmember", user=ctx.author)
      await ctx.send(**message.to_dict())
      return
    
    # ---------------------------------------------------------------
    # Insufficient funds?
    
    if own_shards < shards:
      message = load_message(
        "gacha_insufficient_funds",
        data={
          "cost": shards,
          "shards": own_shards,
          **currency_data()
        },
        user=user,
        target_user=target_user
      )
      await ctx.send(**message.to_dict())
      return
    
    # ---------------------------------------------------------------
    # Generate message & give funds

    sender_message = load_message(
      "gacha_give",
      data={
        "shards": shards,
        **currency_data()
      },
      user=user,
      target_user=target_user
    )

    receiver_message = load_message(
      "gacha_give_notification",
      data={
        "shards": shards,
        **currency_data(),
        **bot_data()
      },
      user=user,
      target_user=target_user,
      escape_data_values=["username", "target_username"]
    )

    async with new_session() as session:
      try:
        await userdata.shards_exchange(session, user.id, target_user.id, shards)

        await ctx.send(**sender_message.to_dict())
        await ctx.channel.send(**receiver_message.to_dict(), allowed_mentions=AllowedMentions.all())
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()

  
  # ===========================================================================
  # ===========================================================================

  @system_gacha_command.subcommand(
    sub_cmd_name="give",
    sub_cmd_description="Give Shards to another user"
  )
  @slash_option(
    name="target_user",
    description="User to give Shards to",
    required=True,
    opt_type=OptionType.USER
  )
  @slash_option(
    name="shards",
    description="Amount of Shards to give",
    required=True,
    opt_type=OptionType.INTEGER,
    min_value=1
  )
  @slash_default_member_permission(Permissions.ADMINISTRATOR)
  @check(is_owner())
  @auto_defer(ephemeral=True)
  async def system_give_cmd(
    self,
    ctx: SlashContext,
    target_user: BaseUser,
    shards: int
  ):
    shards_before = await userdata.shards(target_user.id)
    shards_after  = shards_before + shards

    message = load_message(
      "gacha_give",
      data={
        "shards": shards,
        "shards_before": shards_before,
        "shards_after": shards_after,
        **currency_data()
      },
      user=ctx.author,
      target_user=target_user
    )

    async with new_session() as session:
      try:
        await userdata.shards_give(session, target_user.id, shards)

        await ctx.send(**message.to_dict(), ephemeral=True)
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()
  
  
  # ===========================================================================
  # ===========================================================================

  @system_gacha_command.subcommand(
    sub_cmd_name="reload",
    sub_cmd_description="Reload gacha configuration files"
  )
  @slash_default_member_permission(Permissions.ADMINISTRATOR)
  @check(is_owner())
  @auto_defer(ephemeral=True)
  async def system_reload_cmd(self, ctx: SlashContext):
    gacha.reload()
    await gacha.sync_db()

    message = load_message(
      "gacha_reload",
      data={
        "cards": len(gacha.cards)
      },
      user=ctx.author
    )

    await ctx.send(**message.to_dict(), ephemeral=True)


  # ===========================================================================
  # ===========================================================================
    
  @system_gacha_command.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View the card roster"
  )
  @slash_default_member_permission(Permissions.ADMINISTRATOR)
  @check(is_owner())
  @auto_defer(ephemeral=True)
  async def system_cards_cmd(self, ctx: SlashContext):
    roster_cards = await userdata.card_list_all()

    cards = []
    for roster_card in roster_cards:
      cards.append(roster_card.asdict())
    
    message = load_multifield(
      "gacha_cards_admin",
      cards,
      base_data={
        "total_cards": len(cards)
      },
      user=ctx.author,
      escape_data_values=["name", "type", "series"]
    )
    paginator = Paginator.create_from_embeds(bot, *message.embeds)
    paginator.show_select_menu = True
    await paginator.send(ctx, content=message.content, ephemeral=True)
