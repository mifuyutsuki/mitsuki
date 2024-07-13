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
)

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import func

from attrs import define, field
from attrs import asdict as _asdict
from datetime import datetime, timezone
from croniter import croniter
from typing import List, Tuple, Optional, Any, Callable, TypeVar, Self
from string import Template

from . import schema

from mitsuki import bot
from mitsuki.lib.userdata import new_session, AsDict


T = TypeVar("T")

def separated_list(type: Callable[[str], T], separator: str = ","):
  def wrapper(ls: Optional[str] = None):
    return [type(li) for li in ls.split(separator)] if ls else None
  return wrapper

def option(type: Callable[[Any], T]):
  return lambda s: type(s) if s else None


SCHEDULE_COLUMNS = schema.Schedule().columns.copy()

@define
class Schedule(AsDict):
  title: str
  guild: Snowflake = field(converter=Snowflake)
  creator: Snowflake = field(converter=Snowflake)
  date_created: float
  date_modified: float

  id: Optional[int] = field(default=None)
  post_cron: str = field(default="0 0 * * *")
  replacement: bool = field(default=False, converter=bool)
  cycle: bool = field(default=False, converter=bool)
  active: bool = field(default=False, converter=bool)
  pin: bool = field(default=False, converter=bool)
  randomize: bool = field(default=False, converter=bool)
  number_current: int = field(default=0)
  # number_offset: int = field(default=0)
  format: str = field(default="${message}", converter=lambda s: s.strip())

  channel: Optional[Snowflake] = field(default=None, converter=option(Snowflake))
  manager_roles: Optional[str] = field(default=None)

  def get_cron(self, start_time: Optional[datetime] = None):
    return croniter(self.post_cron, start_time=start_time or datetime.now(tz=timezone.utc))


  @classmethod
  async def fetch(cls, title: str):
    query = select(schema.Schedule).where(schema.Schedule.title == title)
    async with new_session() as session:
      sched = await session.scalar(query)
    if sched is None:
      return None

    return cls(**sched.asdict())


  @classmethod
  async def fetch_all(cls, active: Optional[bool] = None):
    query = select(schema.Schedule)
    if active is not None:
      query = query.where(schema.Schedule.active == active)

    async with new_session() as session:
      scheds = (await session.scalars(query)).all()
    return [cls(**sched.asdict()) for sched in scheds]


  @staticmethod
  async def fetch_active_crons():
    query = (
      select(schema.Schedule.title, schema.Schedule.post_cron)
      .where(schema.Schedule.active == True)
    )

    async with new_session() as session:
      results = (await session.execute(query)).all()
    return {result.title: result.post_cron for result in results}


  @staticmethod
  async def fetch_number(schedule_title: str):
    query = (
      select(func.count(schema.Message.id))
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule)
      .where(schema.Schedule.title == schedule_title)
      .where(schema.Message.message_id != None)
    )

    async with new_session() as session:
      result = await session.scalar(query)
    return result or 0


  async def fetch_manager_roles(self):
    if not self.manager_roles:
      return []
    return separated_list(Snowflake, " ")


  @classmethod
  def create(
    cls,
    ctx: InteractionContext,
    title: str,
    replacement: bool = False,
    cycle: bool = False,
    pin: bool = False,
    randomize: bool = False,
    start_at_number: Optional[int] = None,
  ):
    if not ctx.guild:
      raise ValueError("Schedules can only be created in a server")

    date_created = datetime.now(tz=timezone.utc).timestamp()
    return cls(
      title=title,
      guild=ctx.guild.id,
      creator=ctx.author.id,
      date_created=date_created,
      date_modified=date_created,
      replacement=replacement,
      cycle=cycle,
      pin=pin,
      randomize=randomize,
      number_current=start_at_number or 0,
    )


  async def add(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id"]:
      values.pop(key)

    statement = insert(schema.Schedule).values(values)
    await session.execute(statement)


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


  def asdbdict(self):
    return {k: v for k, v in self.asdict().items() if k in SCHEDULE_COLUMNS}


MESSAGE_COLUMNS = schema.Message().columns.copy()

@define
class Message(AsDict):
  schedule_object: Schedule

  schedule: int
  creator: Snowflake
  date_created: float
  date_modified: float

  number: int
  message: str
  order: float

  id: Optional[int] = field(default=None)
  tags: Optional[str] = field(default=None)
  number_posted: Optional[int] = field(default=None)
  message_id: Optional[Snowflake] = field(default=None)
  date_posted: Optional[float] = field(default=None)

  date_created_f: str = field(init=False)
  date_modified_f: str = field(init=False)
  date_posted_f: str = field(init=False)

  def __attrs_post_init__(self):
    self.date_created_f = f"<t:{int(self.date_created)}:f>"
    self.date_modified_f = f"<t:{int(self.date_modified)}:f>"
    self.date_posted_f = f"<t:{int(self.date_posted)}:f>" if self.date_posted else "-"


  @classmethod
  async def fetch_from_schedule(
    cls,
    schedule_title: str,
    include_backlog: bool = False,
    sort: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
  ):
    query = (
      select(schema.Message, schema.Schedule)
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule)
      .where(schema.Schedule.title == schedule_title)
    )

    if not include_backlog:
      query = query.where(schema.Message.message_id != None)

    sort = sort or "number"
    match sort:
      case "number":
        query = query.order_by(schema.Message.number.desc())
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


  @classmethod
  async def fetch_next_backlog(cls, schedule_title: str) -> Optional["Message"]:
    query = (
      select(schema.Message, schema.Schedule)
      .join(schema.Schedule, schema.Schedule.id == schema.Message.schedule)
      .where(schema.Schedule.title == schedule_title)
      .where(schema.Message.message_id == None)
      .order_by(schema.Message.number)
      .limit(1)
    )
    async with new_session() as session:
      result = (await session.execute(query)).first()

    if result is None:
      return None
    return cls(**result.Message.asdict(), schedule_object=Schedule(**result.Schedule.asdict()))


  @classmethod
  def create(cls, ctx: InteractionContext, schedule: Schedule, message: str):
    date_created = datetime.now(tz=timezone.utc).timestamp()
    return cls(
      schedule_object=schedule,
      schedule=schedule.id,
      creator=ctx.author.id,
      date_created=date_created,
      date_modified=date_created,
      number=schedule.number_current + 1,
      order=schedule.number_current + 1.0,
      message=message,
    )


  async def add(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id"]:
      values.pop(key)

    statement = insert(schema.Message).values(values)
    await session.execute(statement)

    statement = (
      update(schema.Schedule)
      .where(schema.Schedule.id == self.schedule_object.id)
      .values(number_current=schema.Schedule.__table__.c.number_current + 1)
    )
    await session.execute(statement)


  async def update(self, session: AsyncSession):
    values = self.asdbdict()
    for key in ["id", "title"]:
      values.pop(key)

    statement = (
      update(schema.Message)
      .where(schema.Message.id == self.id)
      .values(**values)
    )
    await session.execute(statement)


  def asdbdict(self):
    return {k: v for k, v in self.asdict().items() if k in MESSAGE_COLUMNS}


  def add_posted_message(self, message: DiscordMessage):
    self.message_id = message.id
    self.date_posted = message.timestamp.timestamp()
    return self


  def assign_to(self, schedule: Schedule):
    return Template(schedule.format).safe_substitute(**self.asdict())