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
from mitsuki.utils import escape_text, is_caller, get_member_color_value, truncate
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


class ViewSchedule(SelectionMixin, ReaderCommand):
  class Templates(StrEnum):
    SEARCH_RESULTS = "schedule_view_search_results"
    NO_RESULTS = "schedule_view_no_results"

    VIEW = "schedule_view"


  async def search(self, search_key: str):
    await assert_in_guild(self.ctx)

    if search_key.startswith("@") and search_key[1:].isnumeric:
      if by_id := await ScheduleMessage.fetch(int(search_key[1:]), guild=self.ctx.guild.id, public=True):
        return await self.view(by_id)

    await self.defer(suppress_error=True)

    results = await ScheduleMessage.search(search_key, guild=self.ctx.guild.id, public=True)
    if len(results) <= 0:
      await self.send(self.Templates.NO_RESULTS, other_data={"search_key": truncate(search_key, length=50)})
      return

    self.field_data = results
    self.selection_values = [
      StringSelectOption(
        label=f"{truncate(result.schedule_title, length=90)} #{result.number_s}",
        value=str(result.id),
        description=result.partial_message,
      )
      for result in results
    ]
    self.selection_placeholder = "Select a message to view"
    return await self.send_selection(
      self.Templates.SEARCH_RESULTS,
      other_data={"search_key": truncate(search_key, length=50), "total_results": len(results)},
      timeout=45,
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await self.create(ctx).view(ctx.values[0])


  async def view(self, message: Union[ScheduleMessage, int, str]):
    await assert_in_guild(self.ctx)

    await self.defer(edit_origin=self.has_origin and not self.ctx.deferred)

    if isinstance(message, str):
      if not message.isnumeric():
        raise BadInput(field="Message ID")
      message_get = await ScheduleMessage.fetch(int(message), guild=self.ctx.guild.id, public=True)
    elif isinstance(message, int):
      message_get = await ScheduleMessage.fetch(message, guild=self.ctx.guild.id, public=True)
    else:
      message_get = message

    if not message_get:
      raise MessageNotFound()

    await self.send(
      self.Templates.VIEW,
      other_data=message_get.asdict(),
      components=[
        Button(
          style=ButtonStyle.LINK,
          label="Message",
          url=message_get.message_link
        )
      ]
    )