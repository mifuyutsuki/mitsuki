# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

__all__ = (
  "MitsukiException",
  "ProviderError",
  "MitsukiSoftException",
  "UserDenied",
  "BotDenied",
  "InteractionDenied",
  "ScopeDenied",
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


# TODO: Scope errors
class ScopeDenied(MitsukiSoftException):
  """Scope-restricted command was run outside of its scope."""

  TEMPLATE: str = "error_denied_scope"

  def __init__(self, scope: str) -> None:
    self.scope = scope