# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import re
from attrs import define, field
from typing import Optional, Union, List, Dict, Any, NamedTuple
from enum import Enum, StrEnum
from contextlib import suppress
from interactions import (
  ComponentContext,
  Snowflake,
  BaseUser,
  Member,
  InteractionContext,
  Message,
  Timestamp,
  ActionRow,
  Button,
  ButtonStyle,
  StringSelectMenu,
  StringSelectOption,
  ChannelSelectMenu,
  ChannelType,
  TYPE_ALL_CHANNEL,
  RoleSelectMenu,
  Role,
  Permissions,
  Modal,
  ShortText,
  ParagraphText,
  spread_to_rows,
)
from interactions.client.errors import Forbidden, NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from mitsuki import settings
from mitsuki.utils import escape_text, is_caller, get_member_color_value
from mitsuki.lib.commands import (
  CustomID,
  AsDict,
  ReaderCommand,
  WriterCommand,
  TargetMixin,
  MultifieldMixin,
  AutocompleteMixin,
  SelectionMixin,
)
from mitsuki.lib.checks import (
  assert_in_guild,
  assert_bot_permissions,
  assert_user_permissions,
  assert_user_roles,
  has_user_permissions,
  has_user_roles,
  has_bot_channel_permissions,
)
from mitsuki.lib.errors import (
  MitsukiSoftException,
  UserDenied,
  BadInput,
  BadInputRange,
  BadLength,
)
from mitsuki.lib.userdata import new_session

from ..userdata import (
  Schedule,
  Message as ScheduleMessage,
  ScheduleTypes
)
from ..daemon import daemon
from ..errors import (
  ScheduleException,
  ScheduleNotFound,
  MessageNotFound,
  MessageTooLong,
)
from ..utils import (
  check_fetch_schedule,
  check_fetch_message,
  has_schedule_permissions,
)
from ..customids import CustomIDs


class AddMessage(WriterCommand):
  schedule: Schedule
  schedule_message: ScheduleMessage

  class Templates(StrEnum):
    SUCCESS     = "schedule_message_add_success"


  async def prompt_from_button(self):
    return await self.prompt(CustomID.get_id_from(self.ctx))


  async def prompt(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
  
    schedule_title = schedule.title if len(schedule.title) <= 32 else schedule.title[:30].strip() + "..."
    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label=f"Message in \"{schedule_title}\"",
          custom_id="message",
          placeholder="e.g. \"Which anime school uniform is your favorite?\"",
          min_length=1,
          max_length=1800
        ),
        ShortText(
          label=f"Tags (Optional)",
          custom_id="tags",
          placeholder="Space-separated e.g. \"anime apparel favorite\"",
          required=False,
        ),
        title=f"Add Message",
        custom_id=CustomIDs.MESSAGE_ADD.response().id(schedule.id)
      )
    )


  async def response_from_prompt(self, message: str, tags: Optional[str] = None):
    return await self.response(CustomID.get_id_from(self.ctx), message, tags)


  async def response(self, schedule_key: str, message: str, tags: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)

    message = message.strip()

    # Length check
    if len(message) <= 0:
      raise BadInput(field="Schedule message")

    # Create message
    self.schedule_message = schedule.create_message(self.caller_id, message)
    assigned_len = len(schedule.assign(self.schedule_message))
    if assigned_len > 2000:
      raise MessageTooLong(assigned_len)
    if tags:
      self.schedule_message.set_tags(tags)

    m = await self.send_commit(self.Templates.SUCCESS, other_data=self.schedule_message.asdict(), components=[])

    # Delayed action to fetch message id
    if m and self.schedule_message.id:
      await self.ctx.edit(m, components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Go to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(self.schedule_message.id)
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Reorder...",
          emoji=settings.emoji.configure,
          custom_id=CustomIDs.MESSAGE_REORDER.id(self.schedule_message.id),
          disabled=schedule.backlog_number <= 0
        ),
      ])


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.add(session)