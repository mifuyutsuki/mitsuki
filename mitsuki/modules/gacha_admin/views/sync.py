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
from mitsuki.core.submitter import CardSubmitter
from mitsuki.modules.gacha_admin import customids


@attrs.define(slots=False)
class GachaSyncView(View):
  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("## Data Synchronized"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent("Synchronized cached Mitsuki Gacha data with the database.\n"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin sync".format(self.caller.tag)
        )
      )
    ]