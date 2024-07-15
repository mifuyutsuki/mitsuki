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
  Snowflake,
  Timestamp,
  Message as DiscordMessage,
  InteractionContext,
  Permissions,
)

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import func

from attrs import define, field
from datetime import datetime, timezone
from croniter import croniter
from typing import List, Union, Optional, Any, Callable, TypeVar
from string import Template
from enum import IntEnum

from . import schema

from mitsuki import bot
from mitsuki.lib.checks import has_bot_channel_permissions
from mitsuki.lib.userdata import new_session, AsDict


# =================================================================================================
# Utility functions

T = TypeVar("T")

def separated_list(type: Callable[[str], T], separator: str = ","):
  def wrapper(ls: Optional[str] = None):
    return [type(li) for li in ls.split(separator)] if ls else None
  return wrapper

def option(type: Callable[[Any], T]):
  return lambda s: type(s) if s else None

def timestamp_now():
  return datetime.now(tz=timezone.utc).timestamp()

# =================================================================================================
# Utility functions

class ScheduleTypes(IntEnum):
  QUEUE = 0
  RANDOM_QUEUE = 1
  RANDOM = 2
  ONE_MESSAGE = 3


# =================================================================================================
# Schedule

SCHEDULE_COLUMNS = schema.Schedule().columns.copy()

@define
class Schedule(AsDict):
  title: str
  guild: Snowflake = field(converter=Snowflake)
  created_by: Snowflake = field(converter=Snowflake)
  modified_by: Snowflake = field(converter=Snowflake)
  date_created: float
  date_modified: float
  id: Optional[int] = field(default=None)

  active: bool = field(default=False, converter=bool)
  discoverable: bool = field(default=False, converter=bool)
  pin: bool = field(default=False, converter=bool)
  type: int = field(default=0)
  format: str = field(default="${message}", converter=lambda s: s.strip())

  post_routine: str = field(default="0 0 * * *")
  post_channel: Optional[Snowflake] = field(default=None, converter=option(Snowflake))
  manager_roles: Optional[str] = field(default=None)

  current_number: int = field(default=0)
  current_pin: Optional[int] = field(default=None, converter=option(Snowflake))
  last_fire: Optional[float] = field(default=None)

  @post_routine.validator
  def is_valid_routine(self, attribute, value):
    if not croniter.is_valid(value):
      raise ValueError(f"Invalid routine {value}")

  @property
  def manager_role_objects(self):
    return separated_list(Snowflake, " ")(self.manager_roles)

  def cron(self, start_time: Optional[Union[datetime, float]] = None):
    return croniter(self.post_routine, start_time=start_time or datetime.now(tz=timezone.utc))

  def has_unsent(self) -> bool:
    if self.last_fire is None:
      return False
    return self.cron().next(datetime, start_time=self.last_fire) < datetime.now(tz=timezone.utc)

  def asdbdict(self):
    return {k: v for k, v in self.asdict().items() if k in SCHEDULE_COLUMNS}

  def __eq__(self, other):
    if not isinstance(other, Schedule):
      return False
    if self.id and other.id:
      return self.id == other.id and self.title == other.title
    return self.title == other.title


  @classmethod
  async def fetch(cls, title: str):
    query = select(schema.Schedule).where(schema.Schedule.title == title)
    async with new_session() as session:
      result = await session.scalar(query)
    if result is None:
      return None

    return cls(**result.asdict())


  @classmethod
  async def fetch_many(cls, active: Optional[bool] = None):
    query = select(schema.Schedule)
    if active is not None:
      query = query.where(schema.Schedule.active == active)

    async with new_session() as session:
      results = (await session.scalars(query)).all()
    return [cls(**result.asdict()) for result in results]


  @staticmethod
  async def fetch_active_crons():
    query = (
      select(schema.Schedule.title, schema.Schedule.post_routine)
      .where(schema.Schedule.active == True)
    )

    async with new_session() as session:
      results = (await session.execute(query)).all()
    return {result.title: result.post_routine for result in results}


  @staticmethod
  async def fetch_number(schedule_title: str):
    query = (
      select(func.count(schema.Message.id))
      .join(schema.Schedule, schema.Schedule.title == schema.Message.schedule)
      .where(schema.Schedule.title == schedule_title)
      .where(schema.Message.message_id != None)
    )

    async with new_session() as session:
      return await session.scalar(query) or 0


  @staticmethod
  async def fetch_type(schedule_title: str):
    query = select(schema.Schedule.type).where(schema.Schedule.title == schedule_title)
    async with new_session() as session:
      return ScheduleTypes(await session.scalar(query))


  @staticmethod
  async def fetch_last_fire(schedule_title: str):
    query = select(schema.Schedule.last_fire).where(schema.Schedule.title == schedule_title)
    async with new_session() as session:
      return await session.scalar(query)


  async def next(self):
    query = (
      select(schema.Message)
      .join(schema.Schedule, schema.Schedule.title == schema.Message.schedule)
      .where(schema.Schedule.title == self.title)
    )
    match self.type:
      case ScheduleTypes.QUEUE:
        query = query.where(schema.Message.message_id == None).order_by(schema.Message.number)
      case ScheduleTypes.RANDOM_QUEUE:
        query = query.where(schema.Message.message_id == None).order_by(func.random())
      case ScheduleTypes.RANDOM:
        query = query.order_by(func.random())
      case ScheduleTypes.ONE_MESSAGE:
        pass
      case _:
        raise ValueError(f"Unknown schedule type '{self.type}'")
    query = query.limit(1)

    async with new_session() as session:
      result = (await session.scalars(query)).first()
    if not result:
      return None
    return Message(**result.asdict(), schedule_object=self)


  def activate(self):
    self.active    = True
    self.last_fire = timestamp_now()
    return self


  def deactivate(self):
    self.active    = False
    self.last_fire = timestamp_now()
    return self


  def assign(self, message: "Message"):
    return Template(self.format).safe_substitute(message.asdbdict())


  @staticmethod
  async def exists(schedule_title: str):
    query = select(schema.Schedule.id).where(schema.Schedule.title == schedule_title)
    async with new_session() as session:
      return await session.scalar(query) is not None


  async def is_valid(self):
    if not self.type == ScheduleTypes.ONE_MESSAGE:
      if (
        "${message}" not in self.format
        or await Message.fetch_count(self.title) <= 0
      ):
        return False
    if (
      not self.post_channel
      or len(self.format.strip()) <= 0
      or not croniter.is_valid(self.post_routine)
    ):
      return False

    required_permissions = [Permissions.SEND_MESSAGES]
    if self.pin:
      required_permissions.extend([
        Permissions.MANAGE_MESSAGES,      # for pin
        Permissions.VIEW_CHANNEL,         # for fetching previous pin
        Permissions.READ_MESSAGE_HISTORY, # for fetching previous pin
      ])
    if not await has_bot_channel_permissions(bot, self.post_channel, required_permissions):
      return False

    return True


  @classmethod
  def create(
    cls,
    ctx: InteractionContext,
    title: str,
    type: Union[ScheduleTypes, int] = ScheduleTypes.QUEUE,
    pin: bool = False,
    discoverable: bool = False,
  ):
    if not ctx.guild:
      raise ValueError("Schedules can only be created in a server")

    date_created = timestamp_now()
    return cls(
      title=title,
      guild=ctx.guild.id,
      created_by=ctx.author.id,
      modified_by=ctx.author.id,
      date_created=date_created,
      date_modified=date_created,
      type=type,
      pin=pin,
      discoverable=discoverable,
    )


  def create_message(self, author: Snowflake, message: str):
    return Message.create(author, self.title, message)


  async def add_message(self, session: AsyncSession, author: Snowflake, message: str):
    return await Message.create(author, self.title, message).add(session)


  async def add(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id"]:
      values.pop(key)

    statement = insert(schema.Schedule).values(values)
    await session.execute(statement)


  async def update_modify(self, session: AsyncSession, modified_by: Snowflake):
    self.modified_by = modified_by
    self.date_modified = timestamp_now()
    await self.update(session)


  async def update(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id", "title"]:
      values.pop(key)
  
    statement = (
      update(schema.Schedule)
      .where(schema.Schedule.title == self.title)
      .values(values)
    )
    await session.execute(statement)


# =================================================================================================
# Schedule Message

MESSAGE_COLUMNS = schema.Message().columns.copy()

@define
class Message(AsDict):
  schedule: str
  created_by: Snowflake
  modified_by: Snowflake
  date_created: float
  date_modified: float

  message: str
  tags: Optional[str] = field(default=None)
  id: Optional[int] = field(default=None)

  number: Optional[int] = field(default=None)
  message_id: Optional[Snowflake] = field(default=None)
  date_posted: Optional[float] = field(default=None)

  schedule_object: Optional[Schedule] = field(default=None)

  date_created_f: str = field(init=False)
  date_modified_f: str = field(init=False)
  date_posted_f: str = field(init=False)


  def __attrs_post_init__(self):
    self.date_created_f = f"<t:{int(self.date_created)}:f>"
    self.date_modified_f = f"<t:{int(self.date_modified)}:f>"
    self.date_posted_f = f"<t:{int(self.date_posted)}:f>" if self.date_posted else "-"


  @classmethod
  async def fetch(
    cls,
    schedule_title: str,
    discoverable: Optional[bool] = None,
    backlog: Optional[bool] = None,
    sort: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
  ):
    query = (
      select(schema.Message, schema.Schedule)
      .join(schema.Schedule, schema.Schedule.title == schema.Message.schedule)
      .where(schema.Schedule.title == schedule_title)
    )

    if discoverable == True:
      query = query.where(schema.Schedule.discoverable == True)
    elif discoverable == False:
      query = query.where(schema.Schedule.discoverable == False)

    if backlog == True:
      query = query.where(schema.Message.message_id == None)
    elif backlog == False:
      query = query.where(schema.Message.message_id != None)

    sort = sort or "number"
    match sort:
      case "number":
        query = query.order_by(schema.Message.number.desc())
      case "created":
        query = query.order_by(schema.Message.date_created.desc())
      case "modified":
        query = query.order_by(schema.Message.date_modified.desc())
      case _:
        raise ValueError(f"Invalid sort option '{sort}'")

    if limit:
      query = query.limit(limit)
      if offset:
        query = query.offset(offset)

    async with new_session() as session:
      results = (await session.execute(query)).all()

    return [
      cls(**result.Message.asdict(), schedule_object=Schedule(**result.Schedule.asdict()))
      for result in results
    ]


  @staticmethod
  async def fetch_count(schedule_title: str):
    query = select(func.count(schema.Message.id)).where(schema.Message.schedule == schedule_title)
    async with new_session() as session:
      return await session.scalar(query) or 0


  @classmethod
  def create(
    cls,
    author: Snowflake,
    schedule_title: str,
    message: str,
    tags: Optional[str] = None,
  ):
    date_created = timestamp_now()
    return cls(
      schedule=schedule_title,
      created_by=author,
      modified_by=author,
      date_created=date_created,
      date_modified=date_created,
      message=message,
      tags=tags,
    )


  async def add(self, session: AsyncSession):
    statement = (
      update(schema.Schedule)
      .where(schema.Schedule.title == self.schedule)
      .values(current_number=schema.Schedule.__table__.c.current_number + 1)
      .returning(schema.Schedule.current_number, schema.Schedule.type)
    )
    number, type = (await session.execute(statement)).first().tuple()
    if type == ScheduleTypes.QUEUE:
      self.number = number

    values = self.asdbdict()
    for key in ["id"]:
      values.pop(key)

    statement = insert(schema.Message).values(values)
    await session.execute(statement)


  async def update_modify(self, session: AsyncSession, modified_by: Snowflake):
    self.modified_by = modified_by
    self.date_modified = timestamp_now()
    self.__attrs_post_init__()
    await self.update(session)


  async def update(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id", "schedule"]:
      values.pop(key)

    statement = (
      update(schema.Message)
      .where(schema.Message.id == self.id)
      .values(**values)
    )
    await session.execute(statement)


  def add_posted_message(self, message: DiscordMessage):
    self.message_id = message.id
    self.date_posted = message.timestamp.timestamp()
    return self


  def asdbdict(self):
    return {k: v for k, v in self.asdict().items() if k in MESSAGE_COLUMNS}


  def assign_to(self, format: str):
    return Template(format).safe_substitute(**self.asdict())