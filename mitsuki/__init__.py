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
  level=logging.WARNING
)

from interactions import (
  Status,
  Activity,
  ActivityType,
  Client,
  Intents,
  InteractionContext,
  IntervalTrigger,
  listen,
  Task,
)
from interactions.api.events import (
  Startup,
  Ready,
  CommandError,
  CommandCompletion,
  ComponentCompletion,
)
from interactions.client.errors import (
  CommandCheckFailure,
  CommandOnCooldown,
  MaxConcurrencyReached,
)
from interactions.client.const import CLIENT_FEATURE_FLAGS
from interactions.client.mixins.send import SendMixin
from os import environ
from os.path import dirname, abspath
from datetime import datetime, timezone
from typing import List
from random import Random

import traceback
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

init_event = asyncio.Event()


class Bot(Client):
  status_index: int 
  arona: Random
  
  def __init__(self):
    super().__init__(
      status=Status.DND,
      activity=Activity(
        name = "Starting up...",
        type = ActivityType.PLAYING
      )
    )
    self.intents = Intents.DEFAULT
    self.send_command_tracebacks = False

    self.status_index = 0
    self.arona = Random()


  @listen(Startup)
  async def on_startup(self):
    await initialize()
    self.cycle_status.start()

    init_event.set()


  @listen(Ready)
  async def on_ready(self):
    await self.next_status()
    print(f"Ready: {self.user.tag} ({self.user.id})")
  

  @Task.create(IntervalTrigger(seconds=max(60, settings.mitsuki.status_cycle)))
  async def cycle_status(self):
    await self.next_status()
  
  
  async def next_status(self):
    if len(settings.mitsuki.status) == 0:
      await self.change_presence(
        status=Status.ONLINE,
        activity=None
      )
      return
    
    await self.change_presence(
      status=Status.ONLINE,
      activity=Activity(
        name=settings.mitsuki.status[self.status_index],
        type=ActivityType.PLAYING
      )
    )
    
    if settings.mitsuki.status_randomize:
      new_index = self.arona.randrange(len(settings.mitsuki.status))
      new_index = new_index + 1 if self.status_index == new_index else new_index
    else:
      new_index += 1
    
    if new_index >= len(settings.mitsuki.status):
      new_index = 0
    self.status_index = new_index


  @listen(CommandError, disable_default_listeners=True)
  async def on_command_error(self, event: CommandError):
    if isinstance(event.error, CommandOnCooldown):
      cooldown_seconds = int(event.error.cooldown.get_cooldown_time())
      message = load_message(
        "error_cooldown",
        data={"cooldown_seconds": cooldown_seconds},
        user=event.ctx.author
      )
      ephemeral = True
    elif isinstance(event.error, MaxConcurrencyReached):
      message = load_message(
        "error_concurrency",
        user=event.ctx.author
      )
      ephemeral = True
    elif isinstance(event.error, CommandCheckFailure):
      message = load_message(
        "error_command_perms",
        user=event.ctx.author
      )
      ephemeral = True
    else:
      # traceback.print_exception(event.error)

      # Look for the Mitsuki source
      tb = event.error.__traceback__
      use_tb = tb
      mitsuki_tb = None
      while tb is not None:
        if dirname(abspath(__file__)) in tb.tb_frame.f_code.co_filename:
          mitsuki_tb = tb
        use_tb = mitsuki_tb or tb
        tb = tb.tb_next
      
      if mitsuki_tb:
        e_path = (
          use_tb.tb_frame.f_code.co_filename
          .replace(dirname(abspath(__file__)), "mitsuki")
          .replace("\\", ".")
          .replace("/", ".")
          .rsplit(".", maxsplit=1)[0]
          .replace(".__init__", "")
        ) if mitsuki_tb else ""
        e_coname = use_tb.tb_frame.f_code.co_name
        e_lineno = use_tb.tb_lineno
        error_repr = (
          f"{e_path}:{e_coname}:{e_lineno}: "
          f"{type(event.error).__name__}: "
          f"{str(event.error)}"
        )
      else:
        error_repr = (
          f"{type(event.error).__name__}: "
          f"{str(event.error)}"
        ) if use_tb else repr(event.error)

      logger.exception(error_repr)
      
      message = load_message(
        "error",
        data={"error_repr": error_repr},
        user=event.ctx.author
      )
      ephemeral = False
    
    if isinstance(event.ctx, SendMixin):
      await event.ctx.send(**message.to_dict(), ephemeral=ephemeral)
  

  # @listen(CommandCompletion)
  # async def on_command_completion(self, event: CommandCompletion):
  #   if isinstance(event.ctx, InteractionContext):
  #     command_name = event.ctx.invoke_target
  #     logger.info(f"Command emitted: {command_name}")
  #     # if len(event.ctx.args) > 0:
  #     #   args = [str(v) for v in event.ctx.args]
  #     #   logger.info(f"args: {args}")
  #     if len(event.ctx.kwargs) > 0:
  #       kwargs = {k: str(v) for k, v in event.ctx.kwargs.items()}
  #       logger.info(f"kwargs: {kwargs}")
  

  # @listen(ComponentCompletion)
  # async def on_component_completion(self, event: ComponentCompletion):
  #   command_name = event.ctx.invoke_target
  #   try:
  #     component_name = event.ctx.custom_id.split("|")[1]
  #   except Exception:
  #     component_name = event.ctx.custom_id
    
  #   logger.info(f"Component emitted: {command_name}: {component_name}")
  #   if len(event.ctx.values) > 0:
  #     values = [str(v) for v in event.ctx.args]
  #     logger.info(f"values: {values}")


bot = Bot()


def run():
  global bot

  curr_time = datetime.now(tz=timezone.utc).isoformat(sep=" ")

  print(f"Mitsuki v{__version__}")
  print(f"Copyright (c) 2024 Mifuyu (mifuyutsuki)")
  print(f"Current time in UTC: {curr_time}")
  print("")
  
  dev_mode = environ.get("ENABLE_DEV_MODE") == "1"
  sentry_dsn = environ.get("SENTRY_DSN")
  sentry_env = environ.get("SENTRY_ENV") or "dev"

  if dev_mode:
    # Activate Jurigged integration with dev-mode (run.py dev)
    bot.load_extension("interactions.ext.jurigged")
    print("Running in dev mode. Jurigged is active")
    
    if not settings.dev.scope:
      logger.warning(
        "Settings property dev.dev_scope is not set. Running commands globally"
      )
    
    bot.debug_scope = settings.dev.scope
    token = environ.get("DEV_BOT_TOKEN")
  else:
    # Activate Sentry integration with no dev-mode (run.py)
    if sentry_dsn:
      bot.load_extension("interactions.ext.sentry", token=sentry_dsn, enable_tracing=True, environment=sentry_env)
      print("Sentry logging is active")
    else:
      logger.warning("Env variable SENTRY_DSN is not set. Sentry logging is off")
      
    token = environ.get("BOT_TOKEN")
  
  if not token:
    raise SystemExit("Token not set. Please add your bot token to .env")
  
  bot.load_extension("mitsuki.core")
  bot.load_extension("mitsuki.info")
  bot.load_extension("mitsuki.gacha")

  # fixes image loading issues?
  # CLIENT_FEATURE_FLAGS["FOLLOWUP_INTERACTIONS_FOR_IMAGES"] = True

  bot.start(token)