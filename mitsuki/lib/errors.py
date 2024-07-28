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
  "UserDenied",
  "BotDenied",
  "ScopeDenied",
)


class UserDenied(Exception):
  def __init__(self, requires: str) -> None:
    self.requires = requires


class BotDenied(Exception):
  def __init__(self, requires: str) -> None:
    self.requires = requires


# TODO: Scope errors
class ScopeDenied(Exception):
  def __init__(self, scope: str) -> None:
    self.scope = scope