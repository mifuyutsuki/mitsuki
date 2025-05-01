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


class DeleteTag(WriterCommand):
  schedule_tag: ScheduleTag

  class Templates(StrEnum):
    CONFIRM = "schedule_tag_delete_confirm"
    SUCCESS = "schedule_tag_delete_success"


  async def confirm_from_button(self):
    await self.confirm(int(CustomID.get_id_from(self.ctx)))


  async def confirm(self, tag_id: int):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    tag = await ScheduleTag.fetch(tag_id, guild=self.ctx.guild.id, public=True)
    if not tag:
      raise TagNotFound()

    return await self.send(
      self.Templates.CONFIRM,
      other_data=tag.asdict(),
      components=[
        Button(
          style=ButtonStyle.RED,
          label="Delete",
          emoji=settings.emoji.delete,
          custom_id=CustomIDs.TAG_DELETE.id(tag_id)
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Cancel",
          emoji=settings.emoji.back,
          custom_id=CustomIDs.TAG_VIEW.id(tag_id)
        )
      ]
    )


  async def run_from_button(self):
    await self.run(int(CustomID.get_id_from(self.ctx)))


  async def run(self, tag_id: int):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer(ephemeral=True)

    tag = await ScheduleTag.fetch(tag_id, guild=self.ctx.guild.id, public=True)
    if not tag:
      raise TagNotFound()

    self.schedule_tag = tag
    await self.send_commit(
      self.Templates.SUCCESS,
      other_data=tag.asdict(),
      components=[
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Tags",
          emoji=settings.emoji.back,
          custom_id=CustomIDs.TAG_MANAGE.id(tag.schedule_id)
        )
      ]
    )


  async def transaction(self, session: AsyncSession):
    await self.schedule_tag.delete(session)