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
  Status,
  Activity,
  ActivityType,
  Client,
  Intents,
  listen
)
from interactions.api.events import CommandError
from interactions.client.errors import CommandCheckFailure
from os import environ
import traceback

from mitsuki.messages import load as load_messages
from mitsuki.messages import message
from mitsuki.userdata import initialize

from dotenv import load_dotenv
load_dotenv(override=True)

__all__ = (
  "bot",
  "run",
)


class Bot(Client):
  def __init__(self):
    super().__init__(
      status=Status.DND,
      activity=Activity(
        name = "Starting up...",
        type = ActivityType.PLAYING
      )
    )

    self.intents  = Intents.DEFAULT


  @listen()
  async def on_startup(self):
    print("Bot is starting up")
    initialize()
  

  @listen(CommandError, disable_default_listeners=True)
  async def on_command_error(self, event: CommandError):
    if isinstance(event.error, CommandCheckFailure):
      embed = message("error_command_perms", user=event.ctx.user)
      await event.ctx.send(embed=embed)
      return
    
    traceback.print_exception(event.error)

    data  = dict(error_repr=repr(event.error))
    embed = message("error", format=data, user=event.ctx.user)
    await event.ctx.send(embed=embed)


  @listen()
  async def on_ready(self):
    await self.change_presence(
      status=Status.ONLINE,
      activity=Activity(
        name="Mitsuki Tsukuyomi",
        type=ActivityType.PLAYING
      )
    )

    print("Bot is ready")
    print(f"User: {self.user.tag} ({self.user.id})")


load_messages(environ.get("MESSAGES_YAML"))
bot = Bot()
bot.load_extension("mitsuki.core")
bot.load_extension("mitsuki.gacha")


def run():
  global bot
  bot.start(environ.get("BOT_TOKEN"))