# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy

from typing import Optional, Union
from enum import StrEnum

from mitsuki import utils, settings
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks

from .. import customids


class UserInfo(libcmd.TargetMixin, libcmd.ReaderCommand):
  class Templates(StrEnum):
    USER = "user_info_user"
    MEMBER = "user_info_member"


  @staticmethod
  def has_server_profile(target_user: Union[ipy.User, ipy.Member]):
    if isinstance(target_user, ipy.User):
      return False
    return target_user.guild_banner is not None or target_user.guild_avatar is not None


  def components(
    self,
    target_user: Union[ipy.User, ipy.Member],
    avatar_url: str,
    banner_url: Optional[str] = None,
    view_global: bool = False,
    timed_out: bool = False,
  ) -> list[ipy.Button]:
    components = []

    if not timed_out and self.has_server_profile(target_user):
      if view_global:
        components.append(ipy.Button(
          style=ipy.ButtonStyle.BLURPLE,
          label="Server profile",
          emoji=settings.emoji.gallery,
          custom_id=customids.USER_INFO_SERVER.id(target_user.id),
        ))
      else:
        components.append(ipy.Button(
          style=ipy.ButtonStyle.BLURPLE,
          label="Main profile",
          emoji=settings.emoji.gallery,
          custom_id=customids.USER_INFO_GLOBAL.id(target_user.id),
        ))

    components.append(ipy.Button(
      style=ipy.ButtonStyle.LINK,
      label="Avatar",
      url=avatar_url,
    ))
    if banner_url:
      components.append(ipy.Button(
        style=ipy.ButtonStyle.LINK,
        label="Banner",
        url=banner_url,
      ))

    return components


  async def run(self, target: Optional[Union[ipy.User, ipy.Member, ipy.Snowflake]] = None):
    await self.defer(suppress_error=True)

    if isinstance(target, ipy.Snowflake):
      if self.ctx.guild:
        target = await self.ctx.guild.fetch_member(target) or await self.bot.fetch_user(target)
      else:
        target = await self.bot.fetch_user(target)

    target = target or self.caller_user
    if isinstance(target, ipy.Member):
      await self.run_member(target, view_global=False)
    else:
      await self.run_user(target)


  async def run_user(self, target: Optional[Union[ipy.User, ipy.Member, ipy.Snowflake]] = None):
    await self.defer(suppress_error=True)

    if isinstance(target, ipy.Snowflake):
      target = await self.bot.fetch_user(target, force=True)
    else:
      target = target or self.caller_user
      target = await self.bot.fetch_user(target.id, force=True)

    self.set_target(target)

    escapes = [
      "target_globalname",
      "target_dispname",
      # "target_nickname",
      # "guild_name",
    ]

    # Obtain banner
    try:
      # This can AttributeError, but then let it set banner to None
      banner = target.banner.as_url()
    except Exception:
      banner = None
    
    avatar = target.avatar.as_url()

    data = {
      "target_globalname": target.global_name or target.username,
      "target_dispname": target.display_name,
      "target_avatar": avatar,
      "target_banner": banner,
      "created_at": target.created_at.format("f")
    }
    components = self.components(target, avatar, banner, timed_out=True)

    await self.send(
      self.Templates.USER, other_data=data, template_kwargs=dict(escape_data_values=escapes, color=None),
      components=components
    )


  async def run_member(
    self, target: Optional[Union[ipy.Member, ipy.Snowflake]] = None, view_global: bool = False
  ):
    await self.defer(suppress_error=True, edit_origin=self.has_origin)

    if isinstance(target, ipy.Snowflake):
      _target = await self.ctx.guild.fetch_member(target)
      if not _target:
        return await self.run_user(target)
      target = _target
    else:
      target = target or self.caller_user
      if isinstance(target, ipy.User):
        return await self.run_user(target)

    self.set_target(target)

    # Obtain banner (for user, requires fetching with force=True)
    try:
      # This can AttributeError, but then let it set banner to None
      if view_global or not target.guild_banner:
        _user = await self.bot.fetch_user(target.id, force=True)
        banner = _user.banner.as_url()
      else:
        banner = target.banner.as_url()
    except AttributeError:
      banner = None

    try:
      if view_global:
        avatar = target.user.avatar.as_url()
      else:
        avatar = target.guild_avatar.as_url()
    except AttributeError:
      avatar = target.avatar.as_url()

    data = {
      "target_globalname": target.global_name or target.username,
      "target_dispname": target.display_name,
      "target_avatar": avatar,
      "target_banner": banner,
      "target_nickname": target.nick or "-",
      "created_at": target.created_at.format("f"),
      "guild_name": target.guild.name,
      "guild_id": target.guild.id,
      "joined_at": target.joined_at.format("f"),
      "is_booster": "Yes" if target.premium else "No",
    }
    escapes = [
      "target_globalname",
      "target_dispname",
      "target_nickname",
      "guild_name",
    ]
    color = utils.get_member_color_value(target)
    string_templates = []

    if target.nick and not view_global:
      string_templates.append("user_info_has_nickname")
    data |= {
      "guild_name": target.guild.name,
      "guild_id": target.guild.id,
      "joined_at": target.joined_at.format("f"),
      "target_nickname": target.nick or "-",
      "is_booster": "Yes" if target.premium else "No",
    }
    components = self.components(target, avatar, banner, view_global=view_global)
    interactable = [c for c in components if c.custom_id]

    m = await self.send(
      self.Templates.MEMBER,
      other_data=data,
      template_kwargs=dict(
        escape_data_values=escapes,
        use_string_templates=string_templates,
        color=color
      ),
      components=components
    )

    if len(interactable) > 0:
      try:
        _ = await self.bot.wait_for_component(components=interactable, timeout=45)
      except TimeoutError:
        if m:
          await m.edit(components=self.components(target, avatar, banner, timed_out=True))