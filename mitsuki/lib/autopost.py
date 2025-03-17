# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import (
  TYPE_ALL_CHANNEL,
)
from typing import Dict, List, Optional, Union

from mitsuki import logger
from asyncio import Lock, sleep

_autosend_lock = Lock()

AUTOSEND_DELAY_SECONDS = 0.1


async def autosend(channel: TYPE_ALL_CHANNEL, content: str, sleep_seconds: Optional[float] = None, **kwargs):
  sleep_seconds = sleep_seconds or AUTOSEND_DELAY_SECONDS

  async with _autosend_lock:
    m = await channel.send(content, **kwargs)
    if sleep_seconds:
      await sleep(sleep_seconds)

  return m