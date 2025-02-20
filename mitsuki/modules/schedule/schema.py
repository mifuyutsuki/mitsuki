# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import BigInteger
from rapidfuzz import fuzz
from typing import Optional, List, Callable

from mitsuki.lib.userdata import Base


# =================================================================================================
# Database tables

class Schedule(Base):
  __tablename__ = "schedules"
  __table_args__ = (
    UniqueConstraint("title", "guild"),
  )

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  guild: Mapped[int] = mapped_column(BigInteger)
  title: Mapped[str] = mapped_column()
  created_by: Mapped[int] = mapped_column(BigInteger)
  modified_by: Mapped[int] = mapped_column(BigInteger)
  date_created: Mapped[float]
  date_modified: Mapped[float]

  active: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  discoverable: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  pin: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  type: Mapped[int]
  format: Mapped[str] = mapped_column(server_default="${message}")

  post_routine: Mapped[str] = mapped_column(server_default="0 0 * * *") # daily
  post_channel: Mapped[Optional[int]] = mapped_column(BigInteger)
  manager_roles: Mapped[Optional[str]]

  current_number: Mapped[int] = mapped_column(server_default=text("0"))
  current_pin: Mapped[Optional[int]] = mapped_column(BigInteger)
  posted_number: Mapped[int] = mapped_column(server_default=text("0"))
  last_fire: Mapped[Optional[float]]


class Message(Base):
  __tablename__ = "schedule_messages"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  schedule_id: Mapped[int]
  created_by: Mapped[int] = mapped_column(BigInteger)
  modified_by: Mapped[int] = mapped_column(BigInteger)
  date_created: Mapped[float]
  date_modified: Mapped[float]

  message: Mapped[str]
  tags: Mapped[Optional[str]]
  post_time: Mapped[Optional[float]]

  number: Mapped[Optional[int]]
  message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
  date_posted: Mapped[Optional[float]]