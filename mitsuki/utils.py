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
)
from interactions.client.errors import (
  AlreadyDeferred,
  HTTPException,
)
from interactions.api.events import Component

from rapidfuzz.utils import default_process

import unicodedata
import regex as re
import contextlib

__all__ = (
  "UserDenied",
  "BotDenied",
  "escape_text",
  "process_text",
  "remove_accents",
  "is_caller",
  "suppressed_defer",
)


class UserDenied(Exception):
  def __init__(self, requires: str) -> None:
    self.requires = requires


class BotDenied(Exception):
  def __init__(self, requires: str) -> None:
    self.requires = requires


_escape_text_re = re.compile(r"[*_`.+(){}!#|:@<>~\-\[\]\\\/]")
_remove_accents_re = re.compile(r"\p{Mn}")


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
    if not is_caller:
      await component.ctx.send(
        "This interaction is not for you", 
        ephemeral=True
      )
    return c
  return check


async def suppressed_defer(ctx: InteractionContext, ephemeral: bool = False):
  """
  Defer a command without emitting an error.

  Warning: This function is now a built feature in interactions.py as
  defer(suppress_error=True) and is deprecated.

  Args:
      ctx: Interaction context object
  """

  with contextlib.suppress(AlreadyDeferred, HTTPException):
    await ctx.defer(ephemeral=ephemeral)
