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
  StringSelectMenu,
  OptionType,
  BaseUser,
  Permissions,
  check,
  is_owner,
  auto_defer,
)
from interactions.client.errors import HTTPException
from interactions.api.events import Component
from mitsuki.paginators import Paginator
from sqlalchemy.orm import Session
from rapidfuzz import fuzz, utils, process
from typing import Optional

from mitsuki import bot
from mitsuki.messages import message, message_with_fields, username_from_user
from mitsuki.userdata import engine
from mitsuki.gacha import userdata
from mitsuki.gacha.gachaman import gacha, Card


# =================================================================


def _data(
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  card: Optional[Card] = None,
  **kwargs
):
  # Preset data
  data = {
    "currency": gacha.settings.currency,
    "currency_icon": gacha.settings.currency_icon,
    "currency_name": gacha.settings.currency_name,
  }

  if user:
    data.update({
      "user"     : user.mention,
      "username" : username_from_user(user),
      "usericon" : user.avatar_url
    })
  
  if target_user:
    data.update({
      "target_user"     : target_user.mention,
      "target_username" : username_from_user(target_user),
      "target_usericon" : target_user.avatar_url
    })
  
  if card:
    stars       = gacha.settings.stars.get(card.rarity)
    dupe_shards = gacha.settings.dupe_shards.get(card.rarity)
    data.update({
      "id"          : card.id,
      "type"        : card.type,
      "series"      : card.series,
      "name"        : card.name,
      "image"       : card.image,
      "stars"       : stars,
      "dupe_shards" : dupe_shards,
      "card_id"     : card.id      # Alias used by /admin gacha cards
    })

  data.update(**kwargs)

  return data


# =================================================================


class MitsukiGacha(Extension):
  @slash_command(
    name="gacha",
    description="Roll your favorite characters and memories",
    dm_permission=False
  )
  async def gacha_cmd(self, ctx: SlashContext):
    pass


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
    shards      = userdata.get_shards(target_user)

    data = _data(target_user=target_user, shards=shards)

    embed = message("gacha_shards", format=data, user=ctx.user)
    await ctx.send(embed=embed)


  @gacha_cmd.subcommand(
    sub_cmd_name="daily",
    sub_cmd_description=f"Claim your gacha daily"
  )
  async def daily_cmd(self, ctx: SlashContext):
    shards       = gacha.settings.daily_shards
    daily_tz     = gacha.settings.daily_tz
    daily_tz_str = f"-{daily_tz}" if daily_tz < 0 else f"+{daily_tz}"

    data = _data(shards=shards, daily_tz=daily_tz_str)

    is_daily_available = userdata.is_daily_available(ctx.user, daily_tz)
    if not is_daily_available:
      embed = message("gacha_daily_already_claimed", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return
    
    embed = message("gacha_daily", format=data, user=ctx.user)

    with Session(engine) as session:
      userdata.modify_shards(session, ctx.user, shards, daily=True)

      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise 
      else:
        session.commit()


  @gacha_cmd.subcommand(
    sub_cmd_name="roll",
    sub_cmd_description="Roll gacha once using Shards"
  )
  async def roll_cmd(self, ctx: SlashContext):
    user   = ctx.user
    shards = userdata.get_shards(user)
    cost   = gacha.settings.cost

    # ---------------------------------------------------------------
    # Check if enough shards - return if insufficient
    
    if shards < cost:
      data  = _data(shards=shards, cost=cost)
      embed = message("gacha_insufficient_funds", format=data, user=user)
      await ctx.send(embed=embed)
      return
  
    # ---------------------------------------------------------------
    # Roll

    # TODO: pass pity data to gachaman.roll

    min_rarity  = userdata.check_user_pity(gacha.settings.pity, user)
    rolled      = gacha.roll(min_rarity=min_rarity)
    is_new_card = not userdata.user_has_card(user, rolled)
    dupe_shards = 0 if is_new_card else gacha.settings.dupe_shards[rolled.rarity]

    # ---------------------------------------------------------------
    # Generate embed

    color = gacha.settings.colors.get(rolled.rarity)
    data  = _data(card=rolled)

    if is_new_card:
      embed = message(
        "gacha_get_new_card",
        format=data, user=user, color=color
      )
    else:
      embed = message(
        "gacha_get_dupe_card",
        format=data, user=user, color=color
      )

    # ---------------------------------------------------------------
    # Update userdata
      
    pity_settings = gacha.settings.pity

    with Session(engine) as session:
      userdata.modify_shards(session, user, dupe_shards - cost)
      userdata.give_card(session, user, rolled)
      userdata.update_user_pity(session, pity_settings, user, rolled.rarity)
      
      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()


  @gacha_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View your or another user's collected cards"
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
    user: Optional[BaseUser] = None
  ):
    target_user       = user or ctx.user
    target_user_cards = userdata.list_cards(target_user)

    data = _data(target_user=target_user)

    if len(target_user_cards) <= 0:
      embed = message("gacha_cards_no_cards", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return

    cards = []
    cards_data = gacha.roster.from_ids(target_user_cards.keys())
    for card_data in cards_data:
      card = _data(
        card=card_data,
        amount=target_user_cards[card_data.id].count,
        first_acquired=int(target_user_cards[card_data.id].first_acquired)
      )
      cards.append(card)
    
    data.update(total_cards=len(cards_data))

    embeds = message_with_fields(
      "gacha_cards",
      cards,
      base_format=data,
      user=ctx.user
    )
    paginator = Paginator.create_from_embeds(bot, *embeds, timeout=45)
    paginator.show_select_menu = True
    await paginator.send(ctx)

  
  @gacha_cmd.subcommand(
    sub_cmd_name="view",
    sub_cmd_description="View a card from your or another user's collection"
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
    description="User's collection to view (default: self)",
    required=False,
    opt_type=OptionType.USER
  )
  async def view_cmd(
    self,
    ctx: SlashContext,
    name: str,
    user: Optional[BaseUser] = None
  ):    
    target_user       = user if user else ctx.user
    target_user_cards = userdata.list_cards(target_user)

    data = _data(target_user=target_user, total_cards=len(target_user_cards))

    if len(target_user_cards) <= 0:
      embed = message("gacha_view_no_cards", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return

    cards_data = gacha.roster.from_ids(target_user_cards.keys())

    card_ids    = []
    card_names  = []
    for card_data in cards_data:
      card_ids.append(card_data.id)
      card_names.append(card_data.name)
    
    search_key = name
    search_results = process.extract(
      search_key,
      card_names,
      scorer=fuzz.WRatio,
      limit=6,
      processor=utils.default_process,
      score_cutoff=50.0
    )

    data.update(search_key=search_key)

    if len(search_results) <= 0:
      embed = message("gacha_view_no_results", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return

    cards = []
    card_select = []
    card_select_ids = []
    strong_match_ids = []

    for _, score, idx in search_results:
      card_select_ids.append(card_ids[idx])

      # Strong match handling
      if score >= 90.0:
        strong_match_ids.append(card_ids[idx])
      
      # Dupe name handling
      repeat_no = 2
      card_select_name = card_names[idx]
      while card_select_name in card_select:
        card_select_name = f"{card_names[idx]} ({repeat_no})"
        repeat_no += 1
      card_select.append(card_select_name)
    
    cards_data = gacha.roster.from_ids(card_select_ids)
    for card_data in cards_data:
      card = _data(
        card=card_data,
        amount=target_user_cards[card_data.id].count,
        first_acquired=int(target_user_cards[card_data.id].first_acquired)
      )
      cards.append(card)

    if len(strong_match_ids) == 1:
      # Unambiguous strong match
      selected_card = gacha.roster.from_id(strong_match_ids[0])
      send = ctx.send
    else:
      # Ambiguous and/or weak match(es)
      select_menu = StringSelectMenu(
        *card_select,
        placeholder="Card to view from search results",
        custom_id="gacha_view_select",
        min_values=1,
        max_values=1
      )
      embed = message_with_fields(
        "gacha_view_search_results",
        cards,
        base_format=data,
        user=ctx.user
      )[0]
      select_msg = await ctx.send(embed=embed, components=select_menu)

      async def check(component: Component):
        is_caller = component.ctx.author.id == ctx.author.id
        if not is_caller:
          await component.ctx.send(
            "This interaction is not for you", 
            ephemeral=True
          )
        return is_caller
      
      try:
        used_component = await bot.wait_for_component(
          components=select_menu,
          check=check,
          timeout=45
        )
      except TimeoutError:
        select_menu.disabled = True
        try:
          await select_msg.edit(embed=embed, components=select_menu)
        except HTTPException:
          # Case: message does not exist
          pass
        return
      
      selected_name = used_component.ctx.values[0]
      selected_idx  = card_select.index(selected_name)
      selected_card = cards_data[selected_idx]
      send = used_component.ctx.edit_origin

    color = gacha.settings.colors.get(selected_card.rarity)
    data = _data(
      target_user=target_user,
      card=selected_card,
      amount=target_user_cards[card_data.id].count,
      first_acquired=int(target_user_cards[card_data.id].first_acquired),
    )

    embed = message("gacha_view_card", format=data, user=ctx.user, color=color)
    await send(embed=embed, components=[])


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
    user          = ctx.user
    own_shards    = userdata.get_shards(user)

    if user.id == target_user.id:
      embed = message("gacha_give_self", user=user)
      await ctx.send(embed=embed)
      return
    
    data = _data(target_user=target_user, cost=shards, shards=own_shards)

    if own_shards < shards:
      embed = message("gacha_insufficient_funds", format=data, user=user)
      await ctx.send(embed=embed)
      return

    embed = message("gacha_give", format=data, user=user)

    with Session(engine) as session:
      userdata.modify_shards(session, user, -shards)
      userdata.modify_shards(session, target_user, +shards)

      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()

  
  @slash_command(
    name="admin",
    description="Bot owner only: administrative functions"
  )
  async def admin_cmd(self, ctx: SlashContext):
    pass


  @admin_cmd.subcommand(
    group_name="gacha",
    group_description="Roll your favorite characters and memories",
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
  async def admin_give_cmd(
    self,
    ctx: SlashContext,
    target_user: BaseUser,
    shards: int
  ):
    data = _data(
      target_user=target_user,
      shards=shards
    )
    embed = message("gacha_give", format=data, user=ctx.user)

    with Session(engine) as session:
      userdata.modify_shards(session, target_user, shards)

      try:
        await ctx.send(embed=embed, ephemeral=True)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()
  

  @admin_cmd.subcommand(
    group_name="gacha",
    group_description="Roll your favorite characters and memories",
    sub_cmd_name="reload",
    sub_cmd_description="Reload gacha configuration files"
  )
  @slash_default_member_permission(Permissions.ADMINISTRATOR)
  @check(is_owner())
  @auto_defer(ephemeral=True)
  async def admin_reload_cmd(self, ctx: SlashContext):
    gacha.reload()

    data  = _data(cards=len(gacha.roster.cards))
    embed = message("gacha_reload", format=data, user=ctx.user)

    await ctx.send(embed=embed, ephemeral=True)


  @admin_cmd.subcommand(
    group_name="gacha",
    group_description="Roll your favorite characters and memories",
    sub_cmd_name="cards",
    sub_cmd_description="View the card roster"
  )
  @slash_default_member_permission(Permissions.ADMINISTRATOR)
  @check(is_owner())
  @auto_defer(ephemeral=True)
  async def admin_cards_cmd(self, ctx: SlashContext):
    cards_data = gacha.roster.cards.values()
    cards_data = sorted(cards_data, key=lambda card: card.name)
    cards_data = sorted(cards_data, key=lambda card: card.rarity, reverse=True)

    cards = []
    for card_data in cards_data:
      cards.append(_data(card=card_data))
    
    data   = _data(total_cards=len(cards))
    embeds = message_with_fields(
      "gacha_cards_admin",
      cards,
      base_format=data,
      user=ctx.user
    )
    paginator = Paginator.create_from_embeds(bot, *embeds)
    paginator.show_select_menu = True
    await paginator.send(ctx, ephemeral=True)