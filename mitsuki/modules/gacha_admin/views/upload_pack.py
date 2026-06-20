# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

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
from mitsuki.core.submitter import CardPackSubmitter
from mitsuki.modules.gacha_admin import customids


@attrs.define(slots=False)
class PackUploadPromptView(View):
  submitter: CardPackSubmitter


  def get_context(self):
    return {
      "add_count": self.submitter.add_count,
      "edit_count": self.submitter.edit_count,
      # "remove_count": self.submitter.remove_count,
      "before_count": self.submitter.original_count,
      "after_count": self.submitter.after_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("## Upload Card Pack"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "Current pack count (including seasons): **${before_count}**\n"
          "After this operation, the pack count will be **${after_count}**.\n"
          "* Packs to add: **${add_count}**\n"
          "* Packs to edit: **${edit_count}**\n"
          "Proceed with this operation?"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin upload".format(self.caller.tag)
        )
      ),
      ipy.ActionRow(
        ipy.Button(
          style=ipy.ButtonStyle.GREEN,
          label="Proceed",
          emoji=get_emoji(AppEmoji.YES),
          custom_id=customids.PACK_UPLOAD.id(self.submitter.id),
        ),
      )
    ]


@attrs.define(slots=False)
class PackUploadDoneView(View):
  submitter: CardPackSubmitter


  def get_context(self):
    return {
      "add_count": self.submitter.add_count,
      "edit_count": self.submitter.edit_count,
      # "remove_count": self.submitter.remove_count,
      "before_count": self.submitter.original_count,
      "after_count": self.submitter.after_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("## Uploaded Card Pack"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "* Added packs: **${add_count}**\n"
          "* Edited packs: **${edit_count}**"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin upload".format(self.caller.tag)
        )
      )
    ]