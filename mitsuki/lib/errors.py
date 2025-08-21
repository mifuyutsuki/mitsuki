# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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
  "RequestException",
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
  """Base class for Mitsuki exceptions."""

  ephemeral: bool = False
  """Whether the error message should be posted ephemerally."""
  title: str = "Error"
  """Title of error to show in the error message."""
  desc: str = "An unexpected error occured, please contact application owner."
  """Description of error to show in the error message."""
  fields: dict[str, str] = {}
  """Embed fields to show in the error message."""
  show_traceback: bool = True
  """Whether to show the error traceback. Defaults to False on derived instances."""

  def __init__(self, *args):
    super().__init__(*args)
    self.fields = {}

  def __init_subclass__(cls, *args, **kwargs):
    cls.show_traceback = False


class ProviderError(MitsukiException):
  """Could not connect to upstream provider, please try again later."""

  desc = "Could not connect to upstream provider, please try again later."


class RequestException(MitsukiException):
  """
  Base class for Mitsuki bot exceptions caused by user requests.

  Exception messages under this class are not logged to Sentry and are ephemeral by default.
  """

  ephemeral = True


class UnderConstruction(RequestException):
  """Command is under construction and is currently unavailable."""

  title = "Under Construction"
  desc = "This command is under construction and is currently unavailable."


class UserDenied(RequestException):
  """User lacks permissions to do an action, such as running an admin command."""

  title = "Permission Error"
  desc = "You don't have permissions to run this command."

  def __init__(self, requires: Optional[str] = None) -> None:
    if requires:
      self.fields = {"Required Permissions": requires}


class BotDenied(RequestException):
  """Bot lacks permissions to do an action, such as changing bot's own nickname."""

  title = "Permission Error"
  desc = "The bot lacks permissions to run this command."

  def __init__(self, requires: Optional[str] = None) -> None:
    if requires:
      self.fields = {"Required Permissions": requires}


class InteractionDenied(RequestException):
  """User interacted with a component not meant for the user."""

  title = "Permission Error"
  desc = "This interaction is not for you."


class ScopeDenied(RequestException):
  """Command was run outside of its scope."""

  title = "Command Unavailable"
  desc = "This command is not available in this channel."

  def __init__(self, scope: Optional[str] = None) -> None:
    if scope:
      self.fields = {"Command Scope": scope}


class OutOfGuild(RequestException):
  """Guild-only command was run outside of a guild."""

  title = "Command Unavailable"
  desc = "This command is not available outside of a server."


class ObjectNotFound(RequestException):
  """Could not find object (e.g. Schedule), which may already have been deleted."""

  def __init__(self, obj_name: str):
    self.desc = "Could not find {} with the specified ID or key.".format(obj_name)


class BadInput(RequestException):
  """Not a valid input for a field."""

  def __init__(self, field: str):
    self.desc = "Not a valid input for '{}'.".format(field)


class BadInputRange(RequestException):
  """Not a valid input range for a numeric field."""

  def __init__(self, field: str):
    self.desc = "Not a valid input range for '{}'.".format(field)


class BadLength(RequestException):
  """Input is too long."""

  def __init__(self, field: str, length: Optional[int] = None, max_length: Optional[int] = None):
    if length is not None and max_length is not None:
      self.desc = "Not a valid input length for '{}' ({} > {}).".format(field, length, max_length)
    else:
      self.desc = "Not a valid input length for '{}'.".format(field)