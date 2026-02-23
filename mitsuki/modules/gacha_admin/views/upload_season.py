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
from mitsuki.core.submitter import GachaSeasonSubmitter
from mitsuki.modules.gacha_admin import customids


@attrs.define(slots=False)
class SeasonUploadPromptView(View):
  submitter: GachaSeasonSubmitter


  def get_context(self):
    return {
      "season_id": self.submitter.season.id,
      "season_name": self.submitter.season.name,
      "season_description": self.submitter.season.description,
      "season_image": self.submitter.season.image,
      "season_starts_f": ipy.Timestamp.fromtimestamp(self.submitter.season.start_time).format("f"),
      "season_ends_f": ipy.Timestamp.fromtimestamp(self.submitter.season.end_time).format("f"),
      "action": "Updating existing" if self.submitter.existing_season else "Creating new",
      "before_count": self.submitter.original_card_count,
      "after_count": self.submitter.new_card_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("## Upload Season Data"),
        ipy.SeparatorComponent(divider=True),
        ipy.MediaGalleryComponent([
          ipy.MediaGalleryItem(
            ipy.UnfurledMediaItem("${season_image}")
          )
        ]),
        ipy.TextDisplayComponent(
          "__${action}__ season: **${season_name}**\n"
          "After this operation, the season will have the following information:\n"
          "* Cards in season before: **${before_count}**\n"
          "* Cards in season after: **${after_count}**\n"
          "* Season starts: ${season_starts_f}\n"
          "* Season ends: ${season_ends_f}\n"
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
          custom_id=customids.SEASON_UPLOAD.id(self.submitter.id),
        ),
      )
    ]


@attrs.define(slots=False)
class SeasonUploadDoneView(View):
  submitter: GachaSeasonSubmitter


  def get_context(self):
    return {
      "season_id": self.submitter.season.id,
      "season_name": self.submitter.season.name,
      "season_description": self.submitter.season.description,
      "season_image": self.submitter.season.image,
      "season_starts_f": ipy.Timestamp.fromtimestamp(self.submitter.season.start_time).format("f"),
      "season_ends_f": ipy.Timestamp.fromtimestamp(self.submitter.season.end_time).format("f"),
      "action": "Creating new" if self.submitter.existing_season else "Updating existing",
      "before_count": self.submitter.original_card_count,
      "after_count": self.submitter.new_card_count,
    }


  def components(self):
    return [
      ipy.ContainerComponent(
        ipy.TextDisplayComponent("## Uploaded Gacha Season"),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "Mitsuki Gacha data is being synchronized.\n"
          "* Cards in season: **${after_count}**\n"
          "* Season starts: ${season_starts_f}\n"
          "* Season ends: ${season_ends_f}\n"
        ),
        ipy.SeparatorComponent(divider=True),
        ipy.TextDisplayComponent(
          "-# {} [Admin]: /gacha-admin upload".format(self.caller.tag)
        )
      )
    ]