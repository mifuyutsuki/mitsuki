# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from dotenv import load_dotenv
load_dotenv(override=True)

import logging
logging.basicConfig(
  format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
  level=logging.INFO
)

from interactions import (
  Status,
  Activity,
  ActivityType,
  Client,
  Intents,
  listen,
  BaseContext,
  InteractionContext,
  ComponentContext
)
from interactions.api.events import (
  Startup,
  Ready,
  CommandError,
  CommandCompletion,
  ComponentCompletion
)
from interactions.client.errors import CommandCheckFailure
from os import environ

from mitsuki.messages import load as load_messages
from mitsuki.messages import message
from mitsuki.userdata import initialize
from mitsuki.version import __version__

__all__ = (
  "bot",
  "run",
)

logger = logging.getLogger(__name__)


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


  @listen(Startup)
  async def on_startup(self):
    await initialize()


  @listen(Ready)
  async def on_ready(self):
    await self.change_presence(
      status=Status.ONLINE,
      activity=Activity(
        name=f"Magical Mitsuki",
        type=ActivityType.PLAYING
      )
    )
    logger.info(f"Ready: {self.user.tag} ({self.user.id})")
    

  @listen(CommandError, disable_default_listeners=True)
  async def on_command_error(self, event: CommandError):
    if isinstance(event.error, CommandCheckFailure):
      embed = message("error_command_perms", user=event.ctx.user)
      await event.ctx.send(embed=embed)
      return
    
    logger.exception(event.error)

    data  = dict(error_repr=repr(event.error))
    embed = message("error", format=data, user=event.ctx.user)
    await event.ctx.send(embed=embed)
  

  @listen(CommandCompletion)
  async def on_command_completion(self, event: CommandCompletion):
    if isinstance(event.ctx, InteractionContext):
      command_name = event.ctx.invoke_target
      logger.info(f"Command emitted: {command_name}")
      if len(event.ctx.args) > 0:
        args = [str(v) for v in event.ctx.args]
        logger.info(f"args: {args}")
      if len(event.ctx.kwargs) > 0:
        kwargs = {k: str(v) for k, v in event.ctx.kwargs.items()}
        logger.info(f"kwargs: {kwargs}")
  

  @listen(ComponentCompletion)
  async def on_component_completion(self, event: ComponentCompletion):
    command_name = event.ctx.invoke_target
    try:
      component_name = event.ctx.custom_id.split("|")[1]
    except Exception:
      component_name = event.ctx.custom_id
    
    logger.info(f"Component emitted: {command_name}: {component_name}")
    if len(event.ctx.values) > 0:
      values = [str(v) for v in event.ctx.args]
      logger.info(f"values: {values}")


print(f"Mitsuki {__version__}")
print(f"Copyright (c) 2024 Mifuyu (mifuyutsuki)")
print(f"---------------------------------------")

load_messages(environ.get("MESSAGES_YAML"))
bot = Bot()
bot.load_extension("mitsuki.core")
bot.load_extension("mitsuki.gacha")


def run():
  global bot
  bot.start(environ.get("BOT_TOKEN"))