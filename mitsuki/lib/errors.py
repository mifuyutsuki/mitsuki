# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from typing import Optional


__all__ = (
  "MitsukiException",
  "ProviderError",
  "MitsukiSoftException",
  "UserDenied",
  "BotDenied",
  "InteractionDenied",
  "ScopeDenied",
  "OutOfGuild",
  "BadInput",
  "BadInputRange",
  "BadLength",
)


class MitsukiException(Exception):
  """Base class for Mitsuki bot exceptions."""

  TEMPLATE: str = "error"
  data: dict[str, str] = {}


class ProviderError(MitsukiException):
  """Could not connect to upstream provider, please try again later."""

  TEMPLATE: str = "error_provider"


class MitsukiSoftException(MitsukiException):
  """
  Base class for Mitsuki bot exceptions which do not need error logging, such as permission errors.

  Exception messages under this class are ephemeral by default.
  """

  EPHEMERAL: bool = True


class UserDenied(MitsukiSoftException):
  """User lacks permissions to do an action, such as running an admin command."""

  TEMPLATE: str = "error_denied_user"

  def __init__(self, requires: str) -> None:
    self.requires = requires
    self.data = {
      "requires": requires,
    }


class BotDenied(MitsukiSoftException):
  """Bot lacks permissions to do an action, such as changing bot's own nickname."""

  TEMPLATE: str = "error_denied_bot"

  def __init__(self, requires: str) -> None:
    self.requires = requires
    self.data = {
      "requires": requires,
    }


class InteractionDenied(MitsukiSoftException):
  """User selected a component not meant for the user."""

  TEMPLATE: str = "error_denied_interaction"


class ScopeDenied(MitsukiSoftException):
  """Scope-restricted command was run outside of its scope."""

  TEMPLATE: str = "error_denied_scope"

  def __init__(self, scope: str) -> None:
    self.data = {"scope": scope}


class OutOfGuild(MitsukiSoftException):
  """Guild-only command was run outside of a guild."""

  TEMPLATE: str = "error_out_of_guild"


class BadInput(MitsukiSoftException):
  """Not a valid input for a field."""

  TEMPLATE: str = "error_bad_input"

  def __init__(self, field: str):
    self.data = {"field": field}


class BadInputRange(MitsukiSoftException):
  """Not a valid input range for a numeric field."""

  TEMPLATE: str = "error_bad_input_range"

  def __init__(self, field: str):
    self.data = {"field": field}


class BadLength(MitsukiSoftException):
  """Input is too long."""

  TEMPLATE: str = "error_bad_length_unspecified"

  def __init__(self, field: str, length: Optional[int] = None, max_length: Optional[int] = None):
    if length is not None and max_length is not None:
      self.TEMPLATE = "error_bad_length"
    else:
      self.TEMPLATE = "error_bad_length_unspecified"

    self.data = {
      "field": field,
      "length": length or "-",
      "max_length": max_length or "-",
    }