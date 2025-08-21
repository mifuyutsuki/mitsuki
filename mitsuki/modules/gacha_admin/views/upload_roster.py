# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

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
import attrs

from typing import Optional

from mitsuki.utils import escape_text
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import (
  View,
)
from mitsuki.core.submitter import CardSubmitter
from mitsuki.modules.gacha_admin import customids


@attrs.define(slots=False)
class RosterUploadPromptView(View):
  submitter: CardSubmitter


  def get_context(self):
    return {
      "add_count": self.submitter.add_count,
      "edit_count": self.submitter.edit_count,
      "delist_count": self.submitter.delist_count,
      "before_count": self.submitter.original_count,
      "after_count": self.submitter.after_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent([
        ipy.TextDisplayComponent("## Upload Gacha Roster"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "Current roster size: **${before_count}**\n"
          "After this operation, the roster size will be **${after_count}**.\n"
          "* Cards to add: **${add_count}**\n"
          "* Cards to edit: **${edit_count}**\n"
          "* Cards to delist: **${delete_count}**\n"
          "Proceed with this operation?"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin upload".format(self.caller.tag)
        )
      ]),
      ipy.Button(
        style=ipy.ButtonStyle.GREEN,
        label="Proceed",
        emoji=get_emoji(AppEmoji.YES),
        custom_id=customids.ROSTER_UPLOAD.id(self.submitter.id),
      )
    ]


@attrs.define(slots=False)
class RosterUploadDoneView(View):
  submitter: CardSubmitter


  def get_context(self):
    return {
      "add_count": self.submitter.add_count,
      "edit_count": self.submitter.edit_count,
      "delist_count": self.submitter.delist_count,
      "before_count": self.submitter.original_count,
      "after_count": self.submitter.after_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent([
        ipy.TextDisplayComponent("## Uploaded Gacha Roster"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "* Added cards: **${add_count}**\n"
          "* Edited cards: **${edit_count}**\n"
          "* Delisted cards: **${delete_count}**\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin upload".format(self.caller.tag)
        )
      ])
    ]