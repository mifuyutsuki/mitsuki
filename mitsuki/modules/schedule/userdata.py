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

from sqlalchemy import select, insert, update, delete
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
  guild: Snowflake = field(converter=Snowflake)
  title: str
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
  posted_number: int = field(default=0)
  last_fire: Optional[float] = field(default=None)

  backlog_number: int = field(init=False)
  post_channel_mention: str = field(init=False)
  created_by_mention: str = field(init=False)
  modified_by_mention: str = field(init=False)
  date_created_f: str = field(init=False)
  date_modified_f: str = field(init=False)
  manager_role_mentions: str = field(init=False)

  def __attrs_post_init__(self):
    self.backlog_number       = self.current_number - self.posted_number
    self.post_channel_mention = f"<#{self.post_channel}>" if self.post_channel else "-"
    self.created_by_mention   = f"<@{self.created_by}>"
    self.modified_by_mention  = f"<@{self.modified_by}>"
    self.date_created_f       = f"<t:{int(self.date_created)}:f>"
    self.date_modified_f      = f"<t:{int(self.date_modified)}:f>"
    if manager_roles := self.manager_role_objects:
      self.manager_role_mentions = " ".join([f"<@&{manager_role}>" for manager_role in manager_roles])
    else:
      self.manager_role_mentions = "-"


  @post_routine.validator
  def is_valid_routine(self, attribute, value):
    if not croniter.is_valid(value):
      raise ValueError(f"Invalid routine {value}")

  @property
  def manager_role_objects(self) -> Optional[List[Snowflake]]:
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
      return self.id == other.id and self.guild == other.guild and self.title == other.title
    return self.guild == other.guild and self.title == other.title


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
      guild=ctx.guild.id,
      title=title,
      created_by=ctx.author.id,
      modified_by=ctx.author.id,
      date_created=date_created,
      date_modified=date_created,
      type=type,
      pin=pin,
      discoverable=discoverable,
    )


  @classmethod
  async def fetch(cls, guild: Snowflake, title: str):
    query = (
      select(schema.Schedule)
      .where(schema.Schedule.guild == guild)
      .where(schema.Schedule.title == title)
    )
    async with new_session() as session:
      result = await session.scalar(query)
    if result is None:
      return None

    return cls(**result.asdict())


  @classmethod
  async def fetch_by_id(cls, id: int, guild: Optional[Snowflake] = None):
    query = (
      select(schema.Schedule)
      .where(schema.Schedule.id == id)
    )
    if guild:
      query = query.where(schema.Schedule.guild == guild)

    async with new_session() as session:
      result = await session.scalar(query)
    if result is None:
      return None
    return cls(**result.asdict())


  @classmethod
  async def fetch_many(
    cls,
    guild: Optional[Snowflake] = None,
    active: Optional[bool] = None,
    sort: Optional[str] = None
  ):
    query = select(schema.Schedule)
    if guild:
      query = query.where(schema.Schedule.guild == guild)
    if active is not None:
      query = query.where(schema.Schedule.active == active)

    sort = sort or "name"
    match sort.lower():
      case "name":
        query = query.order_by(schema.Schedule.title)
      case "id":
        query = query.order_by(schema.Schedule.id)
      case "created":
        query = query.order_by(schema.Schedule.date_created.desc())
      case "modified":
        query = query.order_by(schema.Schedule.date_modified.desc())
      case _:
        raise ValueError(f"Unknown sort option '{sort}'")

    async with new_session() as session:
      results = (await session.scalars(query)).all()
    return [cls(**result.asdict()) for result in results]


  @staticmethod
  async def fetch_number(guild: Snowflake, title: str, backlog: Optional[bool] = None):
    return await Message.fetch_count(guild, title, backlog=backlog)


  @staticmethod
  async def fetch_type(guild: Snowflake, title: str):
    query = (
      select(schema.Schedule.type)
      .where(schema.Schedule.guild == guild)
      .where(schema.Schedule.title == title)
    )
    async with new_session() as session:
      return ScheduleTypes(await session.scalar(query))


  @staticmethod
  async def fetch_last_fire(guild: Snowflake, title: str):
    query = (
      select(schema.Schedule.last_fire)
      .where(schema.Schedule.guild == guild)
      .where(schema.Schedule.title == title)
    )
    async with new_session() as session:
      return await session.scalar(query)


  async def next(self):
    query = (
      select(schema.Message)
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule_id)
      .where(schema.Schedule.guild == self.guild)
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
    return Message(
      **result.asdict(),
      schedule_guild=self.guild,
      schedule_title=self.title,
      schedule_channel=self.post_channel,
      schedule_type=self.type,
    )


  def activate(self):
    self.active    = True
    self.last_fire = timestamp_now()
    return self


  def deactivate(self):
    self.active    = False
    self.last_fire = timestamp_now()
    return self


  def assign(self, message: "Message"):
    user_message = Template(self.format).safe_substitute(
      {
        "message": message.message,
        "number": message.number_s,
      }
    )
    if message.number:
      mitsuki_message = f"-# Scheduled message '{self.title}' #{message.number}"
    else:
      mitsuki_message = f"-# Scheduled message '{self.title}'"
    if message.tags:
      mitsuki_message += f" - Tags: {message.tags.replace(" ", ", ")}"
    return user_message + "\n-# — — — — — — — — — —\n" + mitsuki_message


  @staticmethod
  async def exists(guild: Snowflake, title: str):
    query = (
      select(schema.Schedule.id)
      .where(schema.Schedule.guild == guild)
      .where(schema.Schedule.title == title)
    )
    async with new_session() as session:
      return await session.scalar(query) is not None


  async def is_valid(self):
    if not self.type == ScheduleTypes.ONE_MESSAGE:
      if (
        "${message}" not in self.format
        or await Message.fetch_count(self.guild, self.title) <= 0
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


  def create_message(self, author: Snowflake, message: str):
    return Message.create(author, self, message)


  async def add_message(self, session: AsyncSession, author: Snowflake, message: Union["Message", str]):
    if isinstance(message, str):
      message = Message.create(author, self, message)
    return await message.add(session)


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
    self.__attrs_post_init__()


# =================================================================================================
# Schedule Message

MESSAGE_COLUMNS = schema.Message().columns.copy()

@define
class Message(AsDict):
  schedule_id: int
  created_by: Snowflake = field(converter=Snowflake)
  modified_by: Snowflake = field(converter=Snowflake)
  date_created: float
  date_modified: float

  message: str = field(converter=lambda s: s.strip())
  tags: Optional[str] = field(default=None)
  post_time: Optional[float] = field(default=None)
  id: Optional[int] = field(default=None)

  number: Optional[int] = field(default=None)
  message_id: Optional[Snowflake] = field(default=None, converter=option(Snowflake))
  date_posted: Optional[float] = field(default=None)

  schedule_guild: Optional[Snowflake] = field(default=None)
  schedule_title: Optional[str] = field(default=None)
  schedule_channel: Optional[Snowflake] = field(default=None)
  schedule_type: Optional[int] = field(default=None)

  number_s: str = field(init=False)
  partial_message: str = field(init=False)
  long_partial_message: str = field(init=False)
  posted_mark: str = field(init=False)
  message_link: str = field(init=False)
  schedule_channel_mention: str = field(init=False)
  created_by_mention: str = field(init=False)
  modified_by_mention: str = field(init=False)
  post_time_f: str = field(init=False)
  date_created_f: str = field(init=False)
  date_modified_f: str = field(init=False)
  date_posted_f: str = field(init=False)


  def __attrs_post_init__(self):
    if self.schedule_guild and self.schedule_channel and self.message_id:
      self.message_link = (
        f"https://discord.com/channels/{self.schedule_guild}/{self.schedule_channel}/{self.message_id}"
      )
    else:
      self.message_link = "-"

    self.number_s = str(self.number) if self.number else "???"
    self.partial_message = self.message if len(self.message) < 100 else self.message[:97].strip() + "..."
    self.long_partial_message = self.message if len(self.message) < 1024 else self.message[:1022].strip() + "..."
    self.posted_mark = "✅" if self.message_link != "-" else "🕗"

    self.schedule_channel_mention = f"<>" if self.schedule_channel else "-"
    self.created_by_mention = f"<@{self.created_by}>"
    self.modified_by_mention = f"<@{self.modified_by}>"
    self.post_time_f = f"<t:{int(self.post_time)}:f>" if self.post_time else "-"
    self.date_created_f = f"<t:{int(self.date_created)}:f>"
    self.date_modified_f = f"<t:{int(self.date_modified)}:f>"
    self.date_posted_f = f"<t:{int(self.date_posted)}:f>" if self.date_posted else "-"


  @classmethod
  async def fetch(
    cls,
    message_id: int,
    guild: Optional[Snowflake] = None,
  ):
    query = (
      select(
        schema.Message,
        schema.Schedule.guild,
        schema.Schedule.title,
        schema.Schedule.post_channel,
        schema.Schedule.type,
      )
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule_id)
      .where(schema.Message.id == message_id)
    )
    if guild:
      query = query.where(schema.Schedule.guild == guild)

    async with new_session() as session:
      result = (await session.execute(query)).first()

    if not result:
      return None
    return cls(
      **result.Message.asdict(),
      schedule_guild=result.guild,
      schedule_title=result.title,
      schedule_channel=result.post_channel,
      schedule_type=result.type,
    )


  @classmethod
  async def fetch_by_schedule(
    cls,
    guild: Snowflake,
    schedule_title: str,
    discoverable: Optional[bool] = None,
    backlog: Optional[bool] = None,
    sort: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
  ):
    query = (
      select(
        schema.Message,
        schema.Schedule.guild,
        schema.Schedule.title,
        schema.Schedule.post_channel,
        schema.Schedule.type,
      )
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule_id)
      .where(schema.Schedule.guild == guild)
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
        raise ValueError(f"Unknown sort option '{sort}'")

    if limit:
      query = query.limit(limit)
      if offset:
        query = query.offset(offset)

    async with new_session() as session:
      results = (await session.execute(query)).all()

    return [
      cls(
        **result.Message.asdict(),
        schedule_guild=result.guild,
        schedule_title=result.title,
        schedule_channel=result.post_channel,
        schedule_type=result.type,
      )
      for result in results
    ]


  @staticmethod
  async def fetch_count(guild: Snowflake, schedule_title: str, backlog: Optional[bool] = None):
    query = (
      select(func.count(schema.Message.id))
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule_id)
      .where(schema.Schedule.guild == guild)
      .where(schema.Schedule.title == schedule_title)
    )
    if backlog == True:
      query = query.where(schema.Message.message_id == None)
    elif backlog == False:
      query = query.where(schema.Message.message_id != None)

    async with new_session() as session:
      return await session.scalar(query) or 0


  @classmethod
  def create(
    cls,
    author: Snowflake,
    schedule: Schedule,
    message: str,
    tags: Optional[str] = None,
    post_time: Optional[float] = None,
  ):
    date_created = timestamp_now()
    if schedule.type == ScheduleTypes.QUEUE:
      number = schedule.current_number + 1
    else:
      number = None

    return cls(
      schedule_id=schedule.id,
      created_by=author,
      modified_by=author,
      date_created=date_created,
      date_modified=date_created,
      message=message,
      tags=tags,
      post_time=post_time,
      number=number,
      schedule_guild=schedule.guild,
      schedule_title=schedule.title,
      schedule_channel=schedule.post_channel,
      schedule_type=schedule.type,
    )


  async def add(self, session: AsyncSession):
    statement = (
      update(schema.Schedule)
      .where(schema.Schedule.id == self.schedule_id)
      .values(current_number=schema.Schedule.__table__.c.current_number + 1)
    )
    await session.execute(statement)

    values = self.asdbdict()
    for key in ["id"]:
      values.pop(key)

    statement = insert(schema.Message).values(values)
    await session.execute(statement)


  async def update_renumber(self, session: AsyncSession, new_number: int):
    # Numbers are queue type only
    if not self.schedule_type == ScheduleTypes.QUEUE or not self.number:
      return

    # Renumber messages at and above this message's new number
    await session.execute(
      update(schema.Message)
      .where(schema.Message.schedule_id == self.schedule_id)
      .where(schema.Message.number >= new_number)
      .values(number=schema.Message.__table__.c.number + 1)
    )

    # Set this message to the new number
    await session.execute(
      update(schema.Message)
      .where(schema.Message.id == self.id)
      .values(number=new_number)
    )

    # Update object attribute
    self.number = new_number


  async def delete(self, session: AsyncSession):
    await session.execute(
      delete(schema.Message)
      .where(schema.Message.id == self.id)
    )


  async def update_modify(self, session: AsyncSession, modified_by: Snowflake):
    self.modified_by = modified_by
    self.date_modified = timestamp_now()
    self.__attrs_post_init__()
    await self.update(session)


  async def update(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id", "schedule_id"]:
      values.pop(key)

    await session.execute(
      update(schema.Message)
      .where(schema.Message.id == self.id)
      .values(**values)
    )


  def add_posted_message(self, message: DiscordMessage):
    self.message_id = message.id
    self.date_posted = message.timestamp.timestamp()
    return self


  def asdbdict(self):
    return {k: v for k, v in self.asdict().items() if k in MESSAGE_COLUMNS}


  def asfmtdict(self):
    return {k: str(v) if v is not None else "-" for k, v in self.asdict().items()}


  def assign_to(self, format: str):
    return Template(format).safe_substitute(**self.asfmtdict())