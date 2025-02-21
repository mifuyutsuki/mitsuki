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


class ReorderMessage(WriterCommand):
  schedule_message: ScheduleMessage
  new_number: int

  class Templates(StrEnum):
    SELECT  = "schedule_message_reorder_select"
    SUCCESS = "schedule_message_reorder_success"


  def new_number_dict(self):
    return {
      "old_number": self.schedule_message.number,
      "old_number_s": f"{self.schedule_message.number}",
      "number": self.new_number,
      "number_s": f"{self.new_number}"
    }


  async def select(self):
    """
    Open the reorder menu for a given message. Schedule type QUEUE only.

    Inputs:
      Message ID from component Custom ID

    Buttons:
      To Front  : Move message to front of queue
      Custom... : Select a number (prompt)
      To Back   : Move message to back of queue
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    components = [
      ActionRow(
        Button(
          style=ButtonStyle.BLURPLE,
          label="To Front",
          custom_id=CustomIDs.MESSAGE_REORDER_FRONT.id(message_id),
          disabled=message.number <= schedule.posted_number + 1
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Custom...",
          custom_id=CustomIDs.MESSAGE_REORDER.prompt().id(message_id),
          disabled=schedule.backlog_number < 2
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="To Back",
          custom_id=CustomIDs.MESSAGE_REORDER_BACK.id(message_id),
          disabled=message.number == schedule.current_number
        )
      ),
      ActionRow(
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      )
    ]
    sent = await self.send(
      self.Templates.SELECT,
      other_data=schedule.asdict() | message.asdict(),
      components=components,
    )

    try:
      _ = await self.ctx.bot.wait_for_component(sent, components, timeout=30)
    except TimeoutError:
      if sent:
        await self.ctx.edit(sent, components=[
          ActionRow(
            Button(
              style=ButtonStyle.GRAY,
              label="Refresh",
              custom_id=CustomIDs.MESSAGE_REORDER.id(message_id),
            ),
            Button(
              style=ButtonStyle.GRAY,
              label="Back to Message",
              custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
            )
          )
        ])


  async def to_front(self):
    """
    Move message to front of queue.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    self.schedule_message = message
    self.new_number       = schedule.posted_number + 1
    return await self.send_commit(
      self.Templates.SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      ]
    )


  async def to_back(self):
    """
    Move message to back of queue.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    self.schedule_message = message
    self.new_number       = schedule.current_number
    return await self.send_commit(
      self.Templates.SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Message",
          custom_id=CustomIDs.MESSAGE_VIEW.id(message_id),
        )
      ]
    )


  async def prompt(self):
    """
    [Prompt] Move message to a specified valid number.
  
    Inputs:
      Message ID from component Custom ID
    """
    await assert_in_guild(self.ctx)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    return await self.ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Number",
          custom_id="number",
          placeholder=f"Number from {schedule.posted_number + 1} to {schedule.current_number}",
          required=True,
        ),
        title=f"Reorder Message",
        custom_id=CustomIDs.MESSAGE_REORDER.response().id(message_id)
      )
    )


  async def response(self, number_s: str):
    """
    [Response] Move message to a specified valid number.
  
    Inputs:
      Message ID from component Custom ID
      New number from prompt
    """
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    message_id = int(CustomID.get_id_from(self.ctx))
    message    = await check_fetch_message(message_id, guild=self.ctx.guild.id)
    schedule   = await check_fetch_schedule(self.ctx, f"{message.schedule_id}")

    # Number check
    if not number_s.isnumeric():
      raise BadInput(field="Schedule message number")
    number = int(number_s)
    if not (schedule.posted_number < number <= schedule.current_number):
      raise BadInputRange(field="Schedule message number")

    # Reorder
    self.schedule_message = message
    self.new_number       = number
    return await self.send_commit(
      self.Templates.SUCCESS,
      other_data=message.asdict() | self.new_number_dict(),
      components=[]
    )


  async def transaction(self, session: AsyncSession):
    await self.schedule_message.update_reorder(session, self.new_number, author=self.ctx.author.id)