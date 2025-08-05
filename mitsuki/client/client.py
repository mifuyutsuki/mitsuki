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
import logging
import sys
import os

from mitsuki.logger import log_format
from mitsuki.client.handler import ClientHandlerMixin


class MitsukiClient(ClientHandlerMixin, ipy.Client):
  """Mitsuki Client application."""

  intents = ipy.Intents.DEFAULT
  send_command_tracebacks = False
  del_unused_app_cmd = True

  def __init__(self):
    super().__init__(
      status=ipy.Status.DND,
      activity=ipy.Activity(
        name = "Starting up...",
        type = ipy.ActivityType.PLAYING
      )
    )

    ipy_log_handler = logging.StreamHandler(stream=sys.stderr)
    ipy_log_handler.setFormatter(log_format)
    ipy_logger = logging.getLogger("interactions")
    ipy_logger.addHandler(ipy_log_handler)
    self.logger = ipy_logger

    if os.environ.get("DEBUG") == "1":
      self.logger.setLevel(logging.DEBUG)
    else:
      self.logger.setLevel(logging.INFO)