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

from .tag_view import ViewTag


class ManageTag(SelectionMixin, AutocompleteMixin, ReaderCommand):
  class Templates(StrEnum):
    LIST       = "schedule_tag_list"
    LIST_EMPTY = "schedule_tag_list_empty"


  async def autocomplete(self, input_text: str):
    options = [
      self.option(
        schedule.title,
        schedule.title
      )
      for schedule in await Schedule.fetch_many(self.ctx.guild.id, discoverable=True, sort="id")
      if len(input_text) == 0 or input_text.lower().strip() in schedule.title.lower()
    ]

    return await self.send_autocomplete(options)


  async def manage_from_button(self):
    return await self.manage(CustomID.get_id_from(self.ctx))


  async def manage(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    if self.has_origin:
      await self.defer(edit_origin=True, ephemeral=True)
    else:
      await self.defer(ephemeral=True)

    schedule = await check_fetch_schedule(self.ctx, schedule_key)
    tags = await ScheduleTag.fetch_all(schedule, public=False)

    buttons = [
      Button(
        style=ButtonStyle.GREEN,
        label="Add...",
        emoji=settings.emoji.new,
        custom_id=CustomIDs.TAG_ADD.prompt().id(schedule.id),
      ),
      Button(
        style=ButtonStyle.GRAY,
        label="Refresh",
        emoji=settings.emoji.refresh,
        custom_id=CustomIDs.TAG_MANAGE.id(schedule.id),
      ),
      Button(
        style=ButtonStyle.GRAY,
        label="Back to Schedule",
        emoji=settings.emoji.back,
        custom_id=CustomIDs.SCHEDULE_MANAGE_VIEW.id(schedule.id)
      ),
    ]

    if len(tags) == 0:
      await self.send(
        self.Templates.LIST_EMPTY,
        other_data=schedule.asdict() | {"schedule_title": schedule.title, "total_tags": len(tags)},
        components=buttons
      )
      return

    self.selection_values = [
      StringSelectOption(
        label=tag.name,
        value=tag.id,
        description=tag.partial_description,
      )
      for tag in tags if tag.id
    ]
    self.selection_placeholder = "Select a tag to view..."
    self.selection_per_page = 10
    self.field_data = tags

    await self.send_selection_multiline(
      self.Templates.LIST,
      other_data=schedule.asdict() | {"schedule_title": schedule.title, "total_tags": len(tags)},
      extra_components=buttons,
    )


  async def list_from_button(self):
    return await self.list(CustomID.get_id_from(self.ctx))


  async def list(self, schedule_key: str):
    await assert_in_guild(self.ctx)

    ephemeral = self.ctx.ephemeral
    if self.has_origin:
      await self.defer(edit_origin=True)
    else:
      await self.defer()

    schedule = await fetch_schedule(self.ctx, schedule_key)
    if not schedule or not schedule.discoverable:
      raise ScheduleNotFound()

    tags = await ScheduleTag.fetch_all(schedule, public=True)

    if len(tags) == 0:
      await self.send(
        self.Templates.LIST_EMPTY,
        other_data=schedule.asdict() | {"schedule_title": schedule.title, "total_tags": len(tags)},
        components=[]
      )
      return

    self.selection_values = [
      StringSelectOption(
        label=tag.name,
        value=tag.id,
        description=tag.partial_description,
      )
      for tag in tags if tag.id
    ]
    self.selection_placeholder = "Select a tag to view..."
    self.selection_per_page = 10
    self.field_data = tags

    await self.send_selection_multiline(
      self.Templates.LIST,
      other_data=schedule.asdict() | {"schedule_title": schedule.title, "total_tags": len(tags)},
      timeout=0 if ephemeral else 45,
      extra_components=[],
    )


  async def selection_callback(self, ctx: ComponentContext):
    return await ViewTag.create(ctx).view_from_select()