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

from ..customids import CustomIDs


class UserInfo(libcmd.TargetMixin, libcmd.ReaderCommand):
  data: "UserInfo.Data"

  class Templates(StrEnum):
    USER = "info_user_user"
    MEMBER = "info_user_member"


  async def run(self, target: Optional[Union[ipy.User, ipy.Member]] = None):
    await self.defer(suppress_error=True)

    target = target or self.caller_user
    self.set_target(target)

    escapes = [
      "target_globalname",
      "target_dispname",
      "target_nickname",
      "guild_name",
    ]

    # Obtain banner
    try:
      # This can AttributeError, but then let it set banner to None
      banner = target.banner.as_url()
    except Exception:
      banner = None

    data = {
      "target_globalname": target.global_name or target.username,
      "target_dispname": target.display_name,
      "target_userbanner": banner,
      "created_at": target.created_at.format("f")
    }
    string_templates = []

    if not isinstance(target, ipy.Member):
      await self.send(
        self.Templates.USER,
        other_data=data,
        template_kwargs=dict(escape_data_values=escapes, color=None)
      )
    else:
      if target.nick:
        string_templates.append("info_user_has_nickname")
      data |= {
        "guild_name": target.guild.name,
        "guild_id": target.guild.id,
        "joined_at": target.joined_at.format("f"),
        "target_nickname": target.nick or "-",
        "is_booster": "Yes" if target.premium else "No",
      }

      await self.send(
        self.Templates.MEMBER,
        other_data=data,
        template_kwargs=dict(
          escape_data_values=escapes,
          use_string_templates=string_templates,
          color=utils.get_member_color_value(target)
        ),
      )