# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from mitsuki.lib.errors import MitsukiSoftException
from mitsuki.utils import escape_text

from typing import Optional


__all__ = (
  "ScheduleException",
  "ScheduleNotFound",
  "MessageTooLong",
  "MessageNotFound",
)


class ScheduleException(MitsukiSoftException):
  """Base class for Schedule exceptions."""


class ScheduleNotFound(ScheduleException):
  TEMPLATE: str = "schedule_error_schedule_not_found"

  def __init__(self, schedule_key: Optional[str] = None):
    schedule_key = schedule_key or "-"
    self.data = {"schedule_title": escape_text(schedule_key)}

    super().__init__(f"Unable to find schedule with key '{schedule_key}'")


class ScheduleAlreadyExists(ScheduleException):
  TEMPLATE: str = "schedule_error_schedule_already_exists"

  def __init__(self, title: str):
    self.data = {"title": title}

    super().__init__(f"Schedule '{title}' already exists in given server")


class MessageTooLong(ScheduleException):
  TEMPLATE: str = "schedule_error_message_too_long"

  def __init__(self, length: int):
    self.data = {"length": length}

    super().__init__(f"Schedule message has too many characters ({length})")


class MessageNotFound(ScheduleException):
  TEMPLATE: str = "schedule_error_message_not_found"

  def __init__(self):
    super().__init__(f"Unable to find schedule message")


class TagNotFound(ScheduleException):
  TEMPLATE: str = "schedule_error_tag_not_found"

  def __init__(self):
    super().__init__(f"Unable to find schedule tag")


class TagAlreadyExists(ScheduleException):
  TEMPLATE: str = "schedule_error_tag_already_exists"

  def __init__(self, name: str):
    self.data = {"name": name}

    super().__init__(f"Tag '{name}' already exists in given schedule")


class TagInvalidName(ScheduleException):
  TEMPLATE: str = "schedule_error_tag_invalid_name"

  def __init__(self):
    super().__init__(f"Tag contains invalid characters, such as spaces")