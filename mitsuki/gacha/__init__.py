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
from interactions import slash_option, OptionType, BaseUser
from interactions import slash_default_member_permission, Permissions
from interactions import check, is_owner
from interactions.ext.paginators import Paginator
from sqlalchemy.orm import Session
from typing import Optional

from . import userdata
from .gachaman import gacha
from .. import bot
from ..messages import message, message_with_fields, username_from_user
from ..common import userdata_engine


# =================================================================


class MitsukiGacha(Extension):
  @slash_command(
    name="gacha",
    description="Roll your favorite characters and memories"
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
    target_user = user if user else ctx.user
    shards_get  = userdata.get_shards(target_user)
    shards      = shards_get if shards_get else 0

    currency_icon = gacha.settings.currency_icon

    data = dict(
      currency_icon=currency_icon,
      target_user=target_user.mention,
      shards=shards
    )

    embed = message("gacha_shards", format=data, user=ctx.user)
    await ctx.send(embed=embed)


  @gacha_cmd.subcommand(
    sub_cmd_name="daily",
    sub_cmd_description=f"Claim your gacha daily"
  )
  async def daily_cmd(self, ctx: SlashContext):
    daily_tz     = gacha.settings.daily_tz
    daily_tz_str = f"-{daily_tz}" if daily_tz < 0 else f"+{daily_tz}"

    is_daily_available = userdata.is_daily_available(ctx.user, daily_tz)
    if not is_daily_available:
      data  = dict(
        daily_tz=daily_tz_str
      )
      embed = message("gacha_daily_already_claimed", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return
    
    currency_icon = gacha.settings.currency_icon
    shards        = gacha.settings.daily_shards
    data = dict(
      daily_tz=daily_tz_str,
      shards=shards,
      currency_icon=currency_icon
    )
    embed = message("gacha_daily", format=data, user=ctx.user)

    with Session(userdata_engine) as session:
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
    user     = ctx.user
    cost     = gacha.settings.cost

    currency      = gacha.settings.currency
    currency_icon = gacha.settings.currency_icon
    
    # ---------------------------------------------------------------
    # Check if enough shards - return if insufficient

    shards = userdata.get_shards(user)
    if shards < cost:
      data = dict(
        cost=cost,
        shards=shards,
        currency=currency,
        currency_icon=currency_icon
      )
      embed = message("gacha_insufficient_funds", format=data, user=user)
      await ctx.send(embed=embed)
      return
  
    # ---------------------------------------------------------------
    # Roll

    min_rarity  = userdata.check_user_pity(gacha.settings.pity, user)
    rolled      = gacha.roll(min_rarity=min_rarity)
    is_new_card = not userdata.user_has_card(user, rolled)

    dupe_shards = 0
    if not is_new_card:
      dupe_shards = gacha.settings.dupe_shards[rolled.rarity]

    # ---------------------------------------------------------------
    # Generate embed

    color = gacha.settings.colors.get(rolled.rarity)
    stars = gacha.settings.stars.get(rolled.rarity)

    data = dict(
      type=rolled.type,
      series=rolled.series,
      name=rolled.name,
      stars=stars,
      currency=currency,
      image=rolled.image,
      dupe_shards=dupe_shards
    )

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

    with Session(userdata_engine) as session:
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
    target_user       = user if user else ctx.user
    target_user_cards = userdata.list_cards(target_user)
    target_username   = username_from_user(target_user)
    target_usericon   = target_user.avatar_url

    if len(target_user_cards) <= 0:
      data = dict(
        target_username=target_username,
        target_usericon=target_usericon
      )
      embed = message("gacha_cards_no_cards", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return

    cards = []
    cards_data = gacha.roster.from_ids(target_user_cards.keys())
    for card_data in cards_data:
      stars = gacha.settings.stars.get(card_data.rarity)
      card = dict(
        name=card_data.name,
        type=card_data.type,
        series=card_data.series,
        stars=stars,
        amount=target_user_cards[card_data.id].count,
        first_acquired=int(target_user_cards[card_data.id].first_acquired)
      )
      cards.append(card)
    
    data = dict(
      target_username=target_username,
      target_usericon=target_usericon,
      target_user=target_user.mention,
      total_cards=len(target_user_cards)
    )

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
    currency      = gacha.settings.currency
    currency_icon = gacha.settings.currency_icon
    own_shards    = userdata.get_shards(user)
    own_shards    = own_shards if own_shards else 0

    if user.id == target_user.id:
      embed = message("gacha_give_self", user=user)
      await ctx.send(embed=embed)
      return

    if own_shards < shards:
      data = dict(
        cost=shards,
        shards=own_shards,
        currency=currency,
        currency_icon=currency_icon
      )
      embed = message("gacha_insufficient_funds", format=data, user=user)
      await ctx.send(embed=embed)
      return

    data = dict(
      currency=currency,
      currency_icon=currency_icon,
      target_user=target_user.mention,
      shards=shards
    )
    embed = message("gacha_give", format=data, user=user)

    with Session(userdata_engine) as session:
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
    description="Bot owner only: administrative functions",
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
    currency      = gacha.settings.currency
    currency_icon = gacha.settings.currency_icon

    data = dict(
      currency=currency,
      currency_icon=currency_icon,
      target_user=target_user.mention,
      shards=shards
    )
    embed = message("gacha_give", format=data, user=ctx.user)

    with Session(userdata_engine) as session:
      userdata.modify_shards(session, target_user, shards)

      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()
  