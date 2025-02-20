# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import (
  BaseContext,
  InteractionContext,
  Member,
)
from interactions.api.events import Component

from rapidfuzz.utils import default_process
from rapidfuzz import fuzz

import unicodedata
import regex as re

__all__ = (
  "ratio",
  "substring_ratio",
  "escape_text",
  "process_text",
  "remove_accents",
  "truncate",
  "is_caller",
  "get_member_color",
  "get_member_color_value",
)


_escape_text_re = re.compile(r"[*_`.+(){}!#|:@<>~\-\[\]\\\/]")
_remove_accents_re = re.compile(r"\p{Mn}")


def ratio(s1: str, s2: str, processor=None):
  return (
    (0.55 * fuzz.token_ratio(s1, s2, processor=processor))
    + (0.35 * fuzz.ratio(s1, s2, processor=processor))
    + (0.10 * fuzz.partial_ratio(s1, s2, processor=processor))
  )


def substring_ratio(s1: str, s2: str, processor=None):
  _s1 = processor(s1)
  _s2 = processor(s2)
  return 1.0 if (_s1 in _s2 or _s2 in _s1) else 0.0


def escape_text(text: str):
  """
  Escape Discord markdown special characters in a text.

  For example, `*murasaki_park*` is converted into `\\*murasaki\\_park\\*`.

  Args:
      text: String to be escaped

  Returns:
      Discord markdown-escaped string
  """
  global _escape_text_re
  return _escape_text_re.sub(r"\\\g<0>", text)


def process_text(text: str):
  return default_process(remove_accents(text))


def remove_accents(text: str):
  global _remove_accents_re
  return _remove_accents_re.sub('', unicodedata.normalize('NFKD', text))


def truncate(text: str, length: int = 100):
  return text if len(text) < length else text[:length - 3].strip() + "..."


def is_caller(ctx: BaseContext):
  """
  Produce a command check for whether the component is activated by the caller.

  If a non-caller user uses the component, the message "This interaction is not
  for you" is sent to the user.

  Args:
      ctx: Command context object

  Returns:
      Coroutine to be passed into `bot.wait_for_component()`.
  """

  async def check(component: Component):
    c = component.ctx.author.id == ctx.author.id
    if not c:
      await component.ctx.send(
        "This interaction is not for you", 
        ephemeral=True
      )
    return c
  return check


def get_member_color(member: Member):
  """
  Obtain the member color, based on their top colored role.

  Args:
      member: Guild (server) member object

  Returns:
      Color object
  """
  if not hasattr(member, "roles"):
    # Not a guild member object
    return None

  pos, color = 0, None
  for role in member.roles:
    if role.color.value != 0 and role.position > pos:
      pos, color = role.position, role.color
  return color


def get_member_color_value(member: Member):
  """
  Obtain as an int value the member color, based on their top colored role.

  Args:
      member: Guild (server) member object

  Returns:
      Color object
  """

  if color := get_member_color(member):
    return color.value
  return None