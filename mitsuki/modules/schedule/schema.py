# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from sqlalchemy import ForeignKey, Row, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import BigInteger
from rapidfuzz import fuzz
from typing import Optional, List, Callable
from attrs import define, field
from attrs import asdict as _asdict

from mitsuki.lib.userdata import Base, AsDict


# =================================================================================================
# Database tables

class Schedule(Base):
  __tablename__ = "schedules"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  title: Mapped[str] = mapped_column(unique=True)
  guild: Mapped[int] = mapped_column(BigInteger)
  creator: Mapped[int] = mapped_column(BigInteger)
  date_created: Mapped[float]
  date_modified: Mapped[float]
  active: Mapped[bool] = mapped_column(server_default=text("FALSE"))

  post_cron: Mapped[str] = mapped_column(server_default="0 0 * * *") # daily
  replacement: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  cycle: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  pin: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  randomize: Mapped[bool] = mapped_column(server_default=text("FALSE"))
  number_current: Mapped[int] = mapped_column(server_default=text("0"))
  # number_offset: Mapped[int] = mapped_column(server_default=text("0"))
  format: Mapped[str] = mapped_column(server_default="${message}")

  channel: Mapped[Optional[int]] = mapped_column(BigInteger)
  manager_roles: Mapped[Optional[str]]


class Message(Base):
  __tablename__ = "schedule_messages"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  schedule: Mapped[int]
  creator: Mapped[int] = mapped_column(BigInteger)
  date_created: Mapped[float]
  date_modified: Mapped[float]

  number: Mapped[int]
  message: Mapped[str]
  order: Mapped[float]

  tags: Mapped[Optional[str]]
  number_posted: Mapped[Optional[int]]
  message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
  date_posted: Mapped[Optional[float]]