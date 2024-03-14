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
  slash_default_member_permission,
  SlashContext,
  SlashCommandChoice,
  StringSelectMenu,
  OptionType,
  BaseUser,
  Permissions,
  check,
  is_owner,
  auto_defer,
  listen,
)
from interactions.api.events import Startup
from interactions.client.errors import HTTPException
from mitsuki.paginators import Paginator
from rapidfuzz import fuzz, utils, process
from typing import Optional

from mitsuki import bot
from mitsuki import settings
from mitsuki.messages import (
  load_message,
  load_multipage,
  load_multifield,
)
from mitsuki.core import system_command
from mitsuki.utils import is_caller
from mitsuki.userdata import new_session, initialize
from mitsuki.gacha import userdata
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
    try:
      await gacha.sync_db()
    except Exception:
      # uninitialized DB?
      await initialize()
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
  @slash_option(
    name="user",
    description="User to view",
    required=False,
    opt_type=OptionType.USER
  )
  async def shards_cmd(self, ctx: SlashContext, user: Optional[BaseUser] = None):
    target_user = user or ctx.user
    shards      = await userdata.shards(target_user.id)

    message = load_message(
      "gacha_shards",
      data={
        "shards": shards,
        **currency_data()
      },
      user=ctx.author,
      target_user=target_user
    )
    await ctx.send(**message.to_dict())


  # ===========================================================================
  # ===========================================================================
    
  @gacha_cmd.subcommand(
    sub_cmd_name="daily",
    sub_cmd_description=f"Claim your gacha daily"
  )
  async def daily_cmd(self, ctx: SlashContext):
    shards = gacha.daily_shards

    # TODO: use global settings for daily reset
    daily_reset_time = settings.mitsuki.daily_reset
    
    # Timestamp for next daily
    daily_timestamp = userdata.daily_next(reset_time=daily_reset_time)
    daily_timestamp_r = f"<t:{int(daily_timestamp)}:R>"
    daily_timestamp_f = f"<t:{int(daily_timestamp)}:f>"

    # TODO: extra daily shards for server boosters

    # ---------------------------------------------------------------
    # Check if daily is already claimed

    if not await userdata.daily_check(ctx.user.id, daily_reset_time):
      message = load_message(
        "gacha_daily_already_claimed",
        data={
          "shards": shards,
          "timestamp_r": daily_timestamp_r,
          "timestamp_f": daily_timestamp_f,
          **currency_data()
        },
        user=ctx.author
      )
      await ctx.send(**message.to_dict())
      return
    
    # Claim daily
    message = load_message(
      "gacha_daily",
      data={
        "shards": shards,
        "timestamp_r": daily_timestamp_r,
        "timestamp_f": daily_timestamp_f,
        **currency_data()
      },
      user=ctx.author
    )

    async with new_session() as session:
      await userdata.daily_give(session, ctx.user.id, shards)
      try:
        await ctx.send(**message.to_dict())
      except Exception:
        await session.rollback()
        raise 
      else:
        await session.commit()


  # ===========================================================================
  # ===========================================================================
        
  @gacha_cmd.subcommand(
    sub_cmd_name="roll",
    sub_cmd_description="Roll gacha once using Shards"
  )
  async def roll_cmd(self, ctx: SlashContext):
    await ctx.defer()
    user   = ctx.user
    shards = await userdata.shards(user.id)
    cost   = gacha.cost

    # ---------------------------------------------------------------
    # Insufficient funds?
    
    if shards < cost:
      message = load_message(
        "gacha_insufficient_funds",
        data={
          "shards": shards,
          "cost": cost,
          **currency_data()
        },
        user=user)
      await ctx.send(**message.to_dict())
      return
  
    # ---------------------------------------------------------------
    # Roll

    # TODO: pass pity data to gachaman.roll

    min_rarity  = await userdata.pity_check(user.id, gacha.pity)
    rolled      = gacha.roll(min_rarity=min_rarity)
    is_new_card = not await userdata.card_has(user.id, rolled.id)
    dupe_shards = 0 if is_new_card else gacha.dupe_shards[rolled.rarity]

    # ---------------------------------------------------------------
    # Generate embed

    if is_new_card:
      message = load_message(
        "gacha_get_new_card",
        data={
          **card_data(rolled),
          **currency_data()
        },
        user=ctx.author
      )
    else:
      message = load_message(
        "gacha_get_dupe_card",
        data={
          **card_data(rolled),
          **currency_data()
        },
        user=ctx.author
      )

    # ---------------------------------------------------------------
    # Update userdata
    
    async with new_session() as session:
      await userdata.shards_update(session, user.id, dupe_shards - cost)
      await userdata.card_give(session, user.id, rolled.id)
      await userdata.pity_update(session, user.id, rolled.rarity, gacha.pity)
      
      try:
        await ctx.send(**message.to_dict())
      except Exception:
        await session.rollback()
        raise
      else:
        await session.commit()


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View your or another user's collected cards"
  )
  @slash_option(
    name="mode",
    description="Card viewing mode (default: list)",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
      SlashCommandChoice(name="list", value="list"),
      SlashCommandChoice(name="deck", value="deck"),
    # SlashCommandChoice(name="compact", value="compact")
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
    user: Optional[BaseUser] = None
  ):
    await ctx.defer()
    target_user       = user or ctx.user
    target_user_cards = await userdata.card_list(target_user.id)

    # ---------------------------------------------------------------
    # User has no cards?
    
    total_cards = len(target_user_cards)
    if total_cards <= 0:
      message = load_message("gacha_cards_no_cards", user=ctx.author, target_user=target_user)
      await ctx.send(**message.to_dict())
      return

    # ---------------------------------------------------------------
    # List cards

    cards = []
    for card in target_user_cards:
      cards.append(card.asdict())

    # ---------------------------------------------------------------
    # Generate message

    if mode == "list":
      message = load_multifield(
        "gacha_cards",
        cards,
        base_data={"total_cards": total_cards},
        user=ctx.author,
        target_user=target_user
      )
    elif mode == "deck":
      message = load_multipage(
        "gacha_cards_deck",
        cards,
        base_data={"total_cards": total_cards},
        user=ctx.author,
        target_user=target_user
      )
    else:
      raise ValueError(f"Unsupported viewing mode '{mode}'")
    
    paginator = Paginator.create_from_embeds(bot, *message.embeds, timeout=45)
    paginator.show_select_menu = True
    await paginator.send(ctx, content=message.content)

  
  # ===========================================================================
  # ===========================================================================
    
  @gacha_cmd.subcommand(
    sub_cmd_name="view",
    sub_cmd_description="View an obtained card"
  )
  @slash_option(
    name="name",
    description="Card name to search",
    required=True,
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
    await ctx.defer()
    target_user  = user
    if target_user:
      search_cards = await userdata.card_list(target_user.id)
    else:
      search_cards = await userdata.card_list_all_obtained()
    
    # ---------------------------------------------------------------
    # User has no cards?
    
    total_cards = len(search_cards)
    if total_cards <= 0:
      if target_user:
        message = load_message("gacha_view_no_cards", user=ctx.author, target_user=target_user)
      else:
        message = load_message("gacha_view_no_acquired", user=ctx.author)
      await ctx.send(**message.to_dict())
      return
    
    # ---------------------------------------------------------------
    # Search cards
    # TODO: Search from all users instead of on a specific user

    search_key = name
    
    search_card_refs  = {}
    search_card_ids   = []
    search_card_names = []
    for search_card in search_cards:
      search_card_refs[search_card.card] = search_card
      search_card_ids.append(search_card.card)
      search_card_names.append(search_card.name)
    
    search_results = process.extract(
      search_key,
      search_card_names,
      scorer=fuzz.WRatio,
      limit=6,
      processor=utils.default_process,
      score_cutoff=50.0
    )

    # ---------------------------------------------------------------
    # No search results?

    if len(search_results) <= 0:
      message = load_message(
        "gacha_view_no_results",
        data={
          "search_key": search_key,
          "total_cards": total_cards,
        },
        user=ctx.author,
        target_user=target_user
      )
      await ctx.send(**message.to_dict())
      return

    # ---------------------------------------------------------------
    # Parse search results

    cards = []
    results_card_selects = []
    results_card_ids     = []
    strong_match_ids     = []

    for _, score, idx in search_results:
      results_card_ids.append(search_card_ids[idx])

      # Strong match handling
      if score >= 90.0:
        strong_match_ids.append(search_card_ids[idx])
      
      # Dupe name handling
      repeat_no = 2
      results_card_select = search_card_names[idx]
      while results_card_select in results_card_selects:
        results_card_select = f"{search_card_names[idx]} ({repeat_no})"
        repeat_no += 1

      results_card_selects.append(results_card_select)
    
    results_cards = [search_card_refs[results_card_id] for results_card_id in results_card_ids]
    for results_card in results_cards:
      cards.append(results_card.asdict())

    # ---------------------------------------------------------------
    # Select or prompt select a card
    
    if len(strong_match_ids) == 1:
      # Unambiguous strong match
      selected_card = search_card_refs[strong_match_ids[0]]
      send = ctx.send
    else:
      # Ambiguous and/or weak match(es)
      select_menu = StringSelectMenu(
        *results_card_selects,
        placeholder="Card to view from search results",
        min_values=1,
        max_values=1
      )
      message = load_multifield(
        "gacha_view_search_results"
        if target_user else
        "gacha_view_search_results_2",
        cards,
        base_data={
          "search_key": search_key,
          "total_cards": total_cards,
        },
        user=ctx.author,
        target_user=target_user
      )
      embed = message.embeds[0]
      select_msg = await ctx.send(
        content=message.content,
        embed=embed,
        components=select_menu
      )

      # -------------------------------------------------------------
      # Wait for response
      
      try:
        used_component = await bot.wait_for_component(
          components=select_menu,
          check=is_caller(ctx),
          timeout=45
        )
      except TimeoutError:
        select_menu.disabled = True
        try:
          await select_msg.edit(
            content=message.content,
            embed=embed,
            components=select_menu
          )
        except HTTPException:
          # Case: message does not exist
          pass
        return
      
      selected_value    = used_component.ctx.values[0]
      selected_card_idx = results_card_selects.index(selected_value)
      selected_card     = results_cards[selected_card_idx]
      send = used_component.ctx.edit_origin

    # ---------------------------------------------------------------
    # Show card
    
    if target_user:
      message = load_message(
        "gacha_view_card",
        data=selected_card.asdict(),
        user=ctx.author,
        target_user=target_user
      )
    else:
      selected_card_user = await userdata.card_get_user(ctx.author.id, selected_card.card)
      if selected_card_user:
        message = load_message(
          "gacha_view_card_2_acquired",
          data=selected_card_user.asdict(),
          user=ctx.author,
          target_user=target_user
        )
      else:
        message = load_message(
          "gacha_view_card_2_unacquired",
          data=selected_card.asdict(),
          user=ctx.author,
          target_user=target_user
        )

    await send(**message.to_dict(), components=[])


  # ===========================================================================
  # ===========================================================================

  @gacha_cmd.subcommand(
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
  async def give_cmd(
    self,
    ctx: SlashContext,
    target_user: BaseUser,
    shards: int
  ):
    user       = ctx.author
    own_shards = await userdata.shards(user.id)

    # ---------------------------------------------------------------
    # Self-give?

    if user.id == target_user.id:
      message = load_message("gacha_give_self", user=user)
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

    message = load_message(
      "gacha_give",
      data={
        "shards": shards,
        **currency_data()
      },
      user=user,
      target_user=target_user
    )

    async with new_session() as session:
      await userdata.shards_exchange(session, user.id, target_user.id, shards)
      try:
        await ctx.send(**message.to_dict())
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
      await userdata.shards_give(session, target_user.id, shards)

      try:
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
      user=ctx.author
    )
    paginator = Paginator.create_from_embeds(bot, *message.embeds)
    paginator.show_select_menu = True
    await paginator.send(ctx, content=message.content, ephemeral=True)