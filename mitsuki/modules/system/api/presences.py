# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
import attrs

from typing import Optional
from enum import StrEnum
from interactions.client.errors import HTTPException

from mitsuki import utils
from mitsuki.lib import commands as libcmd
from mitsuki.lib import errors as liberr
from mitsuki.lib import checks as checks
from mitsuki.lib.userdata import new_session


from .. import schema


@attrs.define(kw_only=True)
class Presence(libcmd.AsDict):
  id: Optional[int] = attrs.field(default=None)
  name: str         = attrs.field()


  @classmethod
  def create(cls, name: str):
    return cls(name=name)


  @classmethod
  async def fetch(cls, id: int):
    statement = sa.select(schema.Presence).where(schema.Presence.id == id)

    async with new_session.begin() as session:
      return await session.scalar(statement)


  @classmethod
  async def fetch_all(cls):
    statement = sa.select(schema.Presence).order_by(schema.Presence.name)

    async with new_session.begin() as session:
      results = (await session.scalars(statement)).all()
    return [cls(id=result.id, name=result.name) for result in results]


  @classmethod
  async def fetch_next(cls, prev: Optional["Presence"] = None):
    statement = sa.select(schema.Presence)
    if prev and prev.id:
      statement = statement.where(schema.Presence.id != prev.id)
    statement = statement.order_by(sa.func.random()).limit(1)

    async with new_session.begin() as session:
      if result := await session.scalar(statement):
        return cls(**result.asdict())

    return None


  async def add(self, session: AsyncSession):
    """Add a new presence to the rotation."""
    statement = sa.insert(schema.Presence).values(name=self.name).returning(schema.Presence.id)
    self.id = await session.scalar(statement)


  async def edit(self, session: AsyncSession, name: str):
    """Edit an existing presence in the rotation."""
    statement = sa.update(schema.Presence).where(schema.Presence.id == self.id).values(name=name)
    await session.execute(statement)


  async def delete(self, session: AsyncSession):
    """Delete a presence out of the rotation."""
    statement = sa.delete(schema.Presence).where(schema.Presence.id == self.id)
    await session.execute(statement)
    self.id = None


  @classmethod
  async def delete_id(cls, session: AsyncSession, id: int):
    statement = sa.delete(schema.Presence).where(schema.Presence.id == id).returning(schema.Presence.name)
    return cls(name=await session.scalar(statement))