# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional, Union, List, Dict, Any
from interactions import (
  Snowflake,
  InteractionContext,
  Permissions,
)

from mitsuki.lib.checks import (
  has_user_permissions,
  has_user_roles,
  has_bot_channel_permissions,
)
from mitsuki.lib.errors import (
  UserDenied,
)

from .errors import ScheduleNotFound, MessageNotFound
from .userdata import Schedule, Message as ScheduleMessage


async def fetch_schedule(ctx: InteractionContext, schedule_key: str) -> Optional[Schedule]:
  """Fetch a Schedule by key."""

  # ID search (numeric key, or starts with @)
  schedule = None
  if schedule_key.isnumeric():
    id = int(schedule_key)
    schedule = await Schedule.fetch_by_id(id, guild=ctx.guild.id)
  elif schedule_key.startswith("@") and schedule_key[1:].isnumeric():
    id = int(schedule_key[1:])
    schedule = await Schedule.fetch_by_id(id, guild=ctx.guild.id)

  # If ID search fails, fallback here
  if not schedule:
    schedule = await Schedule.fetch(ctx.guild.id, schedule_key)

  return schedule


async def check_fetch_schedule(ctx: InteractionContext, schedule_key: str, hide: bool = False) -> Schedule:
  """
  Fetch a Schedule by key, and raise an error on failure.
  
  Raises if the calling user has no permissions, or schedule is not found.
  """

  # Search
  schedule = await fetch_schedule(ctx, schedule_key)

  # Deny if no role and no admin, unless hide is set, in which case throw Not Found
  if not await has_schedule_permissions(ctx, schedule):
    if not hide:
      raise UserDenied(requires="Server admin or Schedule manager role(s)")
    raise ScheduleNotFound(schedule_key=schedule_key)

  # Throw error on no Schedule
  if not schedule:
    raise ScheduleNotFound(schedule_key=schedule_key)

  # Schedule found
  return schedule


async def check_fetch_message(message_id: int, guild: Optional[Snowflake] = None) -> ScheduleMessage:
  """
  Fetch a Schedule Message by id, and raise an error on failure.

  Raises if the message is not found.
  """

  message = await ScheduleMessage.fetch(message_id, guild=guild)
  if not message:
    raise MessageNotFound()
  return message


async def has_schedule_permissions(ctx: InteractionContext, schedule: Optional[Schedule] = None) -> bool:
  """
  Check if the calling user (`ctx.author`) has schedule manager permissions.

  A user has schedule permissions if they are a server admin, or have a manager role for a given schedule.

  If `schedule` is not provided, only checks for admin.
  """

  has_role  = False
  has_admin = await has_user_permissions(ctx, Permissions.ADMINISTRATOR)

  # Role check
  if schedule and schedule.manager_role_objects:
    has_role = await has_user_roles(ctx, schedule.manager_role_objects)

  return has_role or has_admin