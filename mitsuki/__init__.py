# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from dotenv import load_dotenv
load_dotenv()

import interactions as ipy
import os

APP_PATH = __file__

try:
  SYSTEM_GUILD_ID = ipy.Snowflake(os.environ.get("SYSTEM_GUILD_ID"))
except Exception:
  SYSTEM_GUILD_ID = None

try:
  EXCLUSIVE_GUILD_ID = ipy.Snowflake(os.environ.get("EXCLUSIVE_GUILD_ID"))
except Exception:
  EXCLUSIVE_GUILD_ID = None


EXCLUSIVE_GUILDS = []

if SYSTEM_GUILD_ID:
  EXCLUSIVE_GUILDS.append(SYSTEM_GUILD_ID)

if EXCLUSIVE_GUILD_ID:
  if EXCLUSIVE_GUILD_ID != SYSTEM_GUILD_ID:
    EXCLUSIVE_GUILDS.append(EXCLUSIVE_GUILD_ID)

if len(EXCLUSIVE_GUILDS) == 0:
  EXCLUSIVE_GUILDS = [ipy.GLOBAL_SCOPE]

import asyncio
init_event = asyncio.Event()

from os import environ
from datetime import datetime, timezone

from mitsuki.logger import logger
from mitsuki.version import __version__
from mitsuki.lib.userdata import db_init

from mitsuki import settings
from mitsuki.core.settings import Setting

__all__ = (
  "__version__",
  "run",
  "logger",
  "init_event",
  "APP_PATH",
  "SYSTEM_GUILD_ID",
  "SYSTEM_GUILDS",
  "EXCLUSIVE_GUILD_ID",
  "EXCLUSIVE_GUILDS",
)


def run(prod: bool = False):
  from mitsuki.client import MitsukiClient

  bot = MitsukiClient()
  db_init()

  curr_time = datetime.now(tz=timezone.utc).isoformat(sep=" ")
  print("Mitsuki v{}".format(__version__))
  print("Copyright (c) 2024-2025 Mifuyu (mifuyutsuki)")
  print("Current time in UTC: {}".format(curr_time))
  print("Running mode: {}".format("Production" if prod else "Development"))
  print("")

  sentry_dsn = environ.get("SENTRY_DSN")
  sentry_env = environ.get("SENTRY_ENV", "dev")
  token      = environ.get("BOT_TOKEN")

  if not token:
    raise SystemExit("Cannot run Mitsuki without a bot token. Set environment variable BOT_TOKEN to run")

  if prod:
    if sentry_dsn:
      try:
        import sentry_sdk
        bot.load_extension("interactions.ext.sentry", token=sentry_dsn, enable_tracing=True, environment=sentry_env)
      except ImportError:
        logger.warning("Install sentry_sdk to enable Sentry error tracking (pip install sentry_sdk)")
      except Exception as e:
        logger.exception(e)
        logger.warning("Failed to load Sentry integration")
      else:
        print("Sentry logging is active")
    else:
      logger.warning("Set environment variable SENTRY_DSN in .env to enable Sentry error tracking")

  if not prod:
    try:
      import jurigged
      bot.load_extension("interactions.ext.jurigged")
    except ImportError:
      logger.warning("Install jurigged to enable hot code reloading (pip install -U -r requirements-dev.txt)")
    except Exception as e:
      logger.exception(e)
      logger.warning("Failed to load jurigged for hot code reloading")
    else:
      print("Hot code reloading (jurigged) is active")

  bot.load_extension("mitsuki.modules.about")
  bot.load_extension("mitsuki.modules.server")
  bot.load_extension("mitsuki.modules.user")
  bot.load_extension("mitsuki.modules.schedule")

  if SYSTEM_GUILD_ID:
    bot.load_extension("mitsuki.modules.system")
    bot.load_extension("mitsuki.modules.gacha_admin")
    logger.info("System Guild: {}".format(SYSTEM_GUILD_ID))
  else:
    logger.warning("System Guild (SYSTEM_GUILD_ID) is not set, which is required for system and admin commands")

  if EXCLUSIVE_GUILD_ID:
    bot.load_extension("mitsuki.modules.gacha")
    logger.info("Exclusive Guild: {}".format(EXCLUSIVE_GUILD_ID))
  else:
    logger.warning("Exclusive Guild (EXCLUSIVE_GUILD_ID) is not set, which is required for Exclusive comands")

  # fixes image loading issues?
  # CLIENT_FEATURE_FLAGS["FOLLOWUP_INTERACTIONS_FOR_IMAGES"] = True

  bot.start(token)