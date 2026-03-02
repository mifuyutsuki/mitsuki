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

from mitsuki.utils import escape_text, user_mention, get_member_color_value
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import StaticView
from ..userdata import Schedule, Message


@attrs.define(slots=False)
class SchedulePostView(StaticView):
  schedule: Schedule
  post: Message


  def get_context(self):
    tags = self.post.tags.split() if self.post.tags else ["-"]
    tags = ["`{}`".format(tag) for tag in tags]
    return {
      "schedule": self.schedule.title,
      "message": self.post.message,
      "number": self.post.number_s,
      "tags": " ".join(tags),
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent(self.schedule.format),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# Tags: ${tags}\n"
          "-# Scheduled message '${schedule}' #${number}\n"
        )
      )
    ]