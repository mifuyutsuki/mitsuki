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
  BaseContext,
  Member,
  User,
  Permissions,
  is_owner,
  Client,
  Snowflake,
)
from interactions.api.events import Component

from typing import Union, List, Optional

# TODO: Move exceptions here or to own module
from mitsuki.utils import BotDenied, UserDenied


__all__ = (
  "UserDenied",
  "BotDenied",
  "assert_user_permissions",
  "assert_bot_permissions",
  "assert_bot_channel_permissions",
  "has_user_permissions",
  "has_bot_permissions",
  "has_bot_channel_permissions",
)


# class UserDenied(Exception):
#   def __init__(self, requires: str) -> None:
#     self.requires = requires


# class BotDenied(Exception):
#   def __init__(self, requires: str) -> None:
#     self.requires = requires


async def assert_user_roles(
  ctx: BaseContext,
  roles: Union[List[Snowflake], Snowflake],
  message: str
):
  if not await has_user_roles(ctx, roles):
    raise UserDenied(message)


async def has_user_roles(ctx: BaseContext, roles: Union[List[Snowflake], Snowflake]):
  if not ctx.guild or not isinstance(ctx.author, Member):
    return False
  if not isinstance(roles, list):
    roles = [roles]
  return ctx.author.has_any_role(roles)


async def assert_user_permissions(
  ctx: BaseContext,
  permissions: Union[List[Permissions] | Permissions],
  message: str
):
  if not await has_user_permissions(ctx, permissions):
    raise UserDenied(message)


async def has_user_permissions(ctx: BaseContext, permissions: Union[List[Permissions] | Permissions]):
  if not isinstance(ctx.author, Member):
    return False
  if not isinstance(permissions, list):
    permissions = [permissions]
  return ctx.author.has_permission(*permissions) or await is_owner()(ctx)


async def assert_bot_permissions(
  ctx: BaseContext,
  permissions: Union[List[Permissions] | Permissions],
  message: str
):
  if not await has_bot_permissions(ctx, permissions):
    raise BotDenied(message)


async def has_bot_permissions(ctx: BaseContext, permissions: Union[List[Permissions] | Permissions]):
  if not isinstance(ctx.author, Member):
    return False

  bot_member = await ctx.bot.fetch_member(ctx.bot.user.id, ctx.guild_id)
  if not bot_member:
    return False

  if not isinstance(permissions, list):
    permissions = [permissions]
  return bot_member.has_permission(*permissions)


async def assert_bot_channel_permissions(
  bot: Client,
  channel_id: Snowflake,
  permissions: Union[List[Permissions] | Permissions],
  message: str
):
  if not await has_bot_channel_permissions(bot, channel_id, permissions):
    raise BotDenied(message)


async def has_bot_channel_permissions(
  bot: Client,
  channel_id: Snowflake,
  permissions: Union[List[Permissions] | Permissions]
):
  channel = await bot.fetch_channel(channel_id)
  if not channel:
    return False
  if not isinstance(permissions, list):
    permissions = [permissions]

  return all(permission in channel.permissions_for(bot.user.id) for permission in permissions)


def is_caller(ctx: BaseContext, message: Optional[str] = None):
  """
  Produce a command check for whether the component is activated by the caller.

  If a non-caller user uses the component, the specified message or the default
  "This interaction is not for you" is sent to the user.

  Args:
      ctx: Command context object
      message: Wrong user message

  Returns:
      Coroutine to be passed into `bot.wait_for_component()`.
  """
  message = message or "This interaction is not for you"

  async def check(component: Component):
    c = component.ctx.author.id == ctx.author.id
    if not c:
      await component.ctx.send(message, ephemeral=True)
    return c
  return check