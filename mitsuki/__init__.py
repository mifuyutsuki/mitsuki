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
import traceback

from interactions import (
  Status,
  Activity,
  ActivityType,
  Client,
  Intents,
  listen,
  InteractionContext,
)
from interactions.api.events import (
  Startup,
  Ready,
  CommandError,
  CommandCompletion,
  ComponentCompletion
)
from interactions.client.const import CLIENT_FEATURE_FLAGS
from interactions.client.errors import CommandCheckFailure
from interactions.client.mixins.send import SendMixin
from os import environ
from datetime import datetime, timezone
import asyncio

from mitsuki import settings
from mitsuki.messages import load_message
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
    asyncio.run(initialize())


  @listen(Startup)
  async def on_startup(self):
    pass


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
      message = load_message("error_command_perms", user=event.ctx.author)
    else:
      traceback.print_exception(event.error)
      logger.exception(event.error)
      message = load_message("error", data={"error_repr": repr(event.error)}, user=event.ctx.author)
    
    if isinstance(event.ctx, SendMixin):
      await event.ctx.send(**message.to_dict())
  

  @listen(CommandCompletion)
  async def on_command_completion(self, event: CommandCompletion):
    if isinstance(event.ctx, InteractionContext):
      command_name = event.ctx.invoke_target
      logger.info(f"Command emitted: {command_name}")
      # if len(event.ctx.args) > 0:
      #   args = [str(v) for v in event.ctx.args]
      #   logger.info(f"args: {args}")
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


bot = Bot()


def run():
  global bot

  dev_mode = environ.get("ENABLE_DEV_MODE") == "1"
  curr_time = datetime.now(tz=timezone.utc).isoformat(sep=" ")

  print(f"Mitsuki v{__version__}")
  print(f"Copyright (c) 2024 Mifuyu (mifuyutsuki)")
  print(f"Current time in UTC: {curr_time}")
  print("")
  
  if dev_mode:
    bot.load_extension("interactions.ext.jurigged")
    print("Running in dev mode. Jurigged is active")
    
    if not settings.dev.scope:
      logger.warning(
        "Settings property dev.dev_scope is not set. Running commands globally"
      )
    
    bot.debug_scope = settings.dev.scope
    token = environ.get("DEV_BOT_TOKEN")
  else:
    token = environ.get("BOT_TOKEN")
  
  if not token:
    raise SystemExit("Token not set. Please add your bot token to .env")
  
  bot.load_extension("mitsuki.core")
  bot.load_extension("mitsuki.info")
  bot.load_extension("mitsuki.gacha")

  # fixes image loading issues?
  CLIENT_FEATURE_FLAGS["FOLLOWUP_INTERACTIONS_FOR_IMAGES"] = True

  bot.start(token)