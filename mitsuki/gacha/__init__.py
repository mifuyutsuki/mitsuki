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
from sqlalchemy.orm import Session
from typing import Optional

from . import userdata, gachaman
from ..messages import generate as message
from ..messages import username_from_user
from ..common import userdata_engine


# =================================================================


class MitsukiGacha(Extension):
  def __init__(self, bot):
    self.gachaman = gachaman.Gacha()
    self.settings = self.gachaman.settings
    self.roll     = self.gachaman.roll


  @slash_command(
    name="gacha",
    description="Roll your favorite characters and memories."
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
    shards_get  = userdata.get_shards(target_user.id)
    shards      = shards_get if shards_get else 0

    currency_icon = self.settings.currency_icon

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
    # Under construction.
    
    embed = message("under_construction", user=ctx.user)
    await ctx.send(embed=embed)


  @gacha_cmd.subcommand(
    sub_cmd_name="roll",
    sub_cmd_description="Roll gacha once using Shards"
  )
  async def roll_cmd(self, ctx: SlashContext):
    user     = ctx.user
    user_id  = ctx.user.id
    cost     = self.settings.cost

    currency      = self.settings.currency
    currency_icon = self.settings.currency_icon
    
    # ---------------------------------------------------------------
    # Check if enough shards - return if insufficient

    shards = userdata.get_shards(user_id)
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

    min_rarity  = userdata.check_user_pity(self.settings.pity, user_id)
    rolled      = self.roll(min_rarity=min_rarity)
    is_new_card = not userdata.user_has_card(user_id, rolled.id)

    dupe_shards = 0
    if not is_new_card:
      dupe_shards = self.settings.dupe_shards[rolled.rarity]

    # ---------------------------------------------------------------
    # Generate embed

    color = self.settings.colors.get(rolled.rarity)
    stars = self.settings.stars.get(rolled.rarity)

    data = dict(
      type=rolled.type,
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

    with Session(userdata_engine) as session:
      userdata.modify_shards(session, user_id, dupe_shards - cost)
      userdata.give_card(session, user_id, rolled.id)
      userdata.update_user_pity(
        session, self.settings.pity, user_id, rolled.rarity
      )
      
      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()


  @gacha_cmd.subcommand(
    sub_cmd_name="cards",
    sub_cmd_description="View your collected cards"
  )
  async def cards_cmd(self, ctx: SlashContext):
    # Under construction.

    embed = message("under_construction", user=ctx.user)
    await ctx.send(embed=embed)
  

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
    currency      = self.settings.currency
    currency_icon = self.settings.currency_icon
    own_shards    = userdata.get_shards(ctx.user.id)
    own_shards    = own_shards if own_shards else 0

    if user.id == target_user.id:
      embed = message("gacha_give_self", user=ctx.user)
      await ctx.send(embed=embed)
      return

    if own_shards < shards:
      data = dict(
        cost=shards,
        shards=own_shards,
        currency=currency,
        currency_icon=currency_icon
      )
      embed = message("gacha_insufficient_funds", format=data, user=ctx.user)
      await ctx.send(embed=embed)
      return

    data = dict(
      currency=currency,
      currency_icon=currency_icon,
      target_user=target_user.mention,
      shards=shards
    )
    embed = message("gacha_give", format=data, user=ctx.user)

    with Session(userdata_engine) as session:
      userdata.modify_shards(session, user.id, -shards)
      userdata.modify_shards(session, target_user.id, +shards)

      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()

  

  @gacha_cmd.subcommand(
    group_name="admin",
    group_description="Bot owner only: Admin functions for gacha module",
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
    currency      = self.settings.currency
    currency_icon = self.settings.currency_icon

    data = dict(
      currency=currency,
      currency_icon=currency_icon,
      target_user=target_user.mention,
      shards=shards
    )
    embed = message("gacha_give", format=data, user=ctx.user)

    with Session(userdata_engine) as session:
      userdata.modify_shards(session, target_user.id, shards)

      try:
        await ctx.send(embed=embed)
      except Exception:
        session.rollback()
        raise
      else:
        session.commit()
  