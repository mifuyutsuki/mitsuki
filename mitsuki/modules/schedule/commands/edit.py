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

from mitsuki import bot
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


class EditMessage(WriterCommand):
  state: "EditMessage.States"
  data: "EditMessage.Data"

  schedule_message: ScheduleMessage

  @define(slots=False)
  class Data(AsDict):
    pass

  class Templates(StrEnum):
    SUCCESS    = "schedule_message_edit_success"


  async def prompt(self):
    await assert_in_guild(self.ctx)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    # Schedule existence check
    _ = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label="Message",
          custom_id="message",
          placeholder="e.g. \"Which anime school uniform is your favorite?\"",
          value=message.message,
          min_length=1,
          max_length=1800
        ),
        ShortText(
          label="Tags",
          custom_id="tags",
          placeholder="Space-separated e.g. \"anime apparel favorite\"",
          value=message.tags,
          required=False,
        ),
        title=f"Edit Message",
        custom_id=CustomIDs.MESSAGE_EDIT.response().id(message_id)
      )
    )


  async def response(self, message: str, tags: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    message_id     = int(CustomID.get_id_from(self.ctx))
    message_object = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule       = await check_fetch_schedule(self.ctx, f"{message_object.schedule_id}")

    message = message.strip()

    # Length check
    if len(message) <= 0:
      raise BadInput(field="Schedule message")
    if tags and len(tags.strip()) <= 0:
      raise BadInput(field="Schedule message tags")

    message_object.message = message
    assigned_len = len(schedule.assign(message_object))
    if assigned_len > 2000:
      raise MessageTooLong(assigned_len)

    if tags:
      message_object.set_tags(tags)
    else:
      message_object.tags = None

    self.schedule_message = message_object
    return await self.send_commit(self.Templates.SUCCESS, other_data=message_object.asdict(), components=[])


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.update_modify(session, self.ctx.author.id)