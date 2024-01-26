# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy
from interactions import Client, Intents, listen

from .common import *


class Bot(Client):
  def __init__(self):
    super().__init__(
      status=ipy.Status.DND,
      activity=ipy.Activity(
        name = "Starting up...",
        type = ipy.ActivityType.PLAYING
      )
    )

    self.intents  = Intents.DEFAULT
    
  @listen()
  async def on_startup(self):
    print("Bot is starting up")

  @listen()
  async def on_ready(self):
    await self.change_presence(
      status=ipy.Status.ONLINE,
      activity=ipy.Activity(
        name="Mitsuki Tsukuyomi",
        type=ipy.ActivityType.PLAYING
      )
    )

    print("Bot is ready")
    print(f"User: {self.user.tag} ({self.user.id})")


bot = Bot()
bot.load_extension("mitsuki.core")
bot.load_extension("mitsuki.gacha")