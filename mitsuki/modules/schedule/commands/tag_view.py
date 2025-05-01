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
  TagNotFound,
  TagInvalidName,
)
from ..utils import (
  check_fetch_schedule,
  check_fetch_message,
  fetch_schedule,
  has_schedule_permissions,
)
from ..customids import CustomIDs

from .view import ViewSchedule
from .messages import ManageMessages


class ViewTag(SelectionMixin, ReaderCommand):
  enable_manager: bool = False


  class Templates(StrEnum):
    VIEW       = "schedule_tag_view"
    VIEW_EMPTY = "schedule_tag_view_empty"


  async def view_from_select(self):
    return await self.view(int(self.ctx.values[0]))


  async def view_from_button(self):
    return await self.view(int(CustomID.get_id_from(self.ctx)))


  async def view(self, tag_id: int):
    await assert_in_guild(self.ctx)

    # This fetch implies the schedule exists due to inner join, otherwise throwing Tag Not Found
    tag = await ScheduleTag.fetch(tag_id, guild=self.ctx.guild.id, public=not self.is_ephemeral)
    if not tag:
      raise TagNotFound()

    schedule = await fetch_schedule(self.ctx, tag.schedule_title)
    self.enable_manager = self.is_ephemeral and await has_schedule_permissions(self.ctx, schedule)

    if not self.ctx.deferred:
      if self.has_origin:
        await self.defer(edit_origin=self.is_ephemeral)
      else:
        await self.defer()

    messages = await ScheduleMessage.search(
      tags=tag.name, guild=self.ctx.guild.id, schedule=tag.schedule_id, public=not self.enable_manager
    )

    string_templates = []
    buttons = []

    if self.enable_manager:
      string_templates.append("schedule_tag_view_info_s")
      buttons.extend([
        Button(
          style=ButtonStyle.RED,
          label="Delete",
          emoji=settings.emoji.delete,
          custom_id=CustomIDs.TAG_DELETE.confirm().id(tag_id),
        ),
        Button(
          style=ButtonStyle.BLURPLE,
          label="Edit...",
          emoji=settings.emoji.edit,
          custom_id=CustomIDs.TAG_EDIT.prompt().id(tag_id),
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Refresh",
          emoji=settings.emoji.refresh,
          custom_id=CustomIDs.TAG_VIEW.id(tag_id),
        ),
        Button(
          style=ButtonStyle.GRAY,
          label="Back to Tags",
          emoji=settings.emoji.back,
          custom_id=CustomIDs.TAG_MANAGE.id(tag.schedule_id)
        ),
      ])

    if len(messages) <= 0:
      await self.send(
        self.Templates.VIEW_EMPTY,
        other_data=tag.asdict(),
        template_kwargs=dict(use_string_templates=string_templates),
        components=buttons,
      )
      return

    self.field_data = messages
    self.selection_values = [
      StringSelectOption(
        label=f"{truncate(tag.schedule_title, length=90)} #{message.number_s} ",
        value=str(message.id),
        description=message.partial_message
      )
      for message in messages
      if message.id
    ]
    self.selection_placeholder = "Message to view..."
    await self.send_selection(
      self.Templates.VIEW,
      other_data=tag.asdict() | {"total_messages": len(messages)},
      extra_components=buttons,
      template_kwargs=dict(use_string_templates=string_templates),
      timeout=0 if self.is_ephemeral else 45,
    )


  async def selection_callback(self, ctx: ComponentContext):
    if self.enable_manager:
      return await ManageMessages.create(ctx).view(ctx.values[0])
    return await ViewSchedule.create(ctx).view(ctx.values[0])