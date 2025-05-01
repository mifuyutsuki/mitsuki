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
  ScheduleTag,
  ScheduleTypes,
)
from ..daemon import daemon
from ..errors import (
  ScheduleException,
  ScheduleNotFound,
  MessageNotFound,
  MessageTooLong,
  TagInvalidName,
  TagAlreadyExists,
  TagNotFound,
)
from ..utils import (
  check_fetch_schedule,
  check_fetch_message,
  has_schedule_permissions,
)
from ..customids import CustomIDs


class EditTag(WriterCommand):
  schedule_tag: ScheduleTag


  class Templates(StrEnum):
    SUCCESS = "schedule_tag_edit_success"


  async def prompt_from_button(self):
    return await self.prompt(int(CustomID.get_id_from(self.ctx)))


  async def prompt(self, tag_id: int):
    await assert_in_guild(self.ctx)

    tag = await ScheduleTag.fetch(tag_id, guild=self.ctx.guild.id, public=True)
    if not tag:
      raise TagNotFound()

    tag_name = truncate(tag.name, length=32)
    await self.ctx.send_modal(
      modal=Modal(
        ParagraphText(
          label=f"Description (Optional)",
          custom_id="description",
          placeholder="No description set",
          value=tag.description,
          min_length=0,
          max_length=100,
          required=False,
        ),
        title=f"Edit Tag: {tag_name}",
        custom_id=CustomIDs.TAG_EDIT.response().id(tag.id)
      )
    )


  async def response_from_prompt(self, description: Optional[str] = None):
    return await self.response(int(CustomID.get_id_from(self.ctx)), description)


  async def response(self, tag_id: int, description: Optional[str] = None):
    await assert_in_guild(self.ctx)
    await self.defer(ephemeral=True)

    tag = await ScheduleTag.fetch(tag_id, guild=self.ctx.guild.id, public=True)
    if not tag:
      raise TagNotFound()

    self.schedule_tag = tag
    self.schedule_tag.set_description(description.strip() if description else None)

    await self.send_commit(self.Templates.SUCCESS, other_data=tag.asdict(), components=[])


  async def transaction(self, session: AsyncSession):
    await self.schedule_tag.update_modify(session, self.ctx.author.id)