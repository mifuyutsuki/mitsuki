# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from mitsuki.lib.errors import RequestException
from mitsuki.utils import escape_text

from typing import Optional


class GachaException(RequestException):
  pass


class UnregisteredGachaUser(GachaException):
  """
  User is not registered yet and is trying to perform a gacha action other than a daily.

  Note that some commands may choose not to return this error, and opt to show "0 Shards" or similar instead.
  """

  desc = "You have not started Mitsuki Gacha yet. To start, use command `/gacha daily` for the first time."


class InsufficientShards(GachaException):
  """User has not enough Shards."""

  title = "Not Enough Currency"
  ephemeral = False

  def __init__(self, item_name: str, item_emoji_s: str, cost: int, has_amount: int):
    self.desc = "Needs {} **{}** {} to perform the action. (has {} **{}**)".format(
      item_emoji_s, cost, item_name, item_emoji_s, has_amount
    )