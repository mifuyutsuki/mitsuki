# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import User, Member, Permissions, is_owner, Embed, BrandColors
from interactions.client.errors import HTTPException
from attrs import define, field
from enum import StrEnum
from typing import Optional, Union

from mitsuki.lib.messages import load_templates, set_templates, get_templates
from mitsuki.lib.commands import AsDict, ReaderCommand
from mitsuki.lib.checks import assert_user_owner


class ReloadTemplates(ReaderCommand):
  # Messages for these do not use the template system (used by self.send())

  async def run(self):
    await assert_user_owner(self.ctx)
    await self.defer(ephemeral=True)

    # Load or fail
    try:
      new_templates = load_templates(raise_on_error=True)
    except Exception as e:
      await self.ctx.send(embed=Embed(
        title="Error",
        description=f"Unable to reload message templates.\n```\n{type(e).__name__}: {str(e)}```",
        color=BrandColors.RED,
      ))
      return
  
    old_templates = get_templates()

    # Compare 1: Templates
    tmps_del_count = 0
    tmps_mod_count = 0

    for k, v in old_templates._templates.items():
      # In old, but not in new (deleted)
      if k not in new_templates._templates:
        tmps_del_count += 1
      # Old and new are different (modified)
      elif v != new_templates._templates[k]:
        tmps_mod_count += 1

    # Additions = New - (Old - Del)
    tmps_add_count = max(0, len(new_templates._templates) - len(old_templates._templates) + tmps_del_count)

    # Compare 2: Strings
    strs_del_count = 0
    strs_mod_count = 0

    for k, v in old_templates._strings.items():
      if k not in new_templates._strings:
        strs_del_count += 1
      elif v != new_templates._strings[k]:
        strs_mod_count += 1

    strs_add_count = max(0, len(new_templates._strings) - len(old_templates._strings) + strs_del_count)

    # Compare 3: Colors
    cols_del_count = 0
    cols_mod_count = 0

    for k, v in old_templates.colors.items():
      if k not in new_templates.colors:
        cols_del_count += 1
      elif v != new_templates.colors[k]:
        cols_mod_count += 1

    cols_add_count = max(0, len(new_templates.colors) - len(old_templates.colors) + cols_del_count)

    # Complete
    set_templates(new_templates)

    await self.ctx.send(embed=Embed(
      title="Reload Success",
      description=(
        f"`{len(new_templates._templates)}` templates: "
        f"`{tmps_add_count}` added, `{tmps_del_count}` removed, `{tmps_mod_count}` modified\n"
        f"`{len(new_templates._strings)}` strings: "
        f"`{strs_add_count}` added, `{strs_del_count}` removed, `{strs_mod_count}` modified\n"
        f"`{len(new_templates.colors)}` colors: "
        f"`{cols_add_count}` added, `{cols_del_count}` removed, `{cols_mod_count}` modified\n"
      ),
      color=BrandColors.BLURPLE
    ))
