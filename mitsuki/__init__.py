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

APP_PATH = __file__

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
)


def run():
  from mitsuki.client import MitsukiClient

  bot = MitsukiClient()
  db_init()

  curr_time = datetime.now(tz=timezone.utc).isoformat(sep=" ")
  print(f"Mitsuki v{__version__}")
  print(f"Copyright (c) 2024-2025 Mifuyu (mifuyutsuki)")
  print(f"Current time in UTC: {curr_time}")
  print("")

  sentry_dsn = environ.get("SENTRY_DSN")
  sentry_env = environ.get("SENTRY_ENV") or "dev"

  if environ.get("ENABLE_DEV_MODE") == "1":
    # Activate Jurigged integration with dev-mode (run.py dev)
    print("Running in dev mode")
    try:
      bot.load_extension("interactions.ext.jurigged")
    except ImportError:
      logger.warning(
        "Install jurigged to enable hot code reloading (pip install -U -r requirements-dev.txt)"
      )
    except Exception as e:
      logger.exception(e)
      logger.warning("Could not enable hot code reloading (jurigged)")
    else:
      print("Hot code reloading (jurigged) is active")

    # TODO: System commands
    if not settings.dev.scope:
      logger.warning("Settings property dev.dev_scope is not set. Running commands globally")

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

  bot.load_extension("mitsuki.modules.about")
  bot.load_extension("mitsuki.modules.system")
  bot.load_extension("mitsuki.modules.server")
  bot.load_extension("mitsuki.modules.user")
  bot.load_extension("mitsuki.modules.gacha")
  bot.load_extension("mitsuki.modules.schedule")

  # fixes image loading issues?
  # CLIENT_FEATURE_FLAGS["FOLLOWUP_INTERACTIONS_FOR_IMAGES"] = True

  bot.start(token)