# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import logging
import sys
import os

__all__ = (
  "log_format",
  "logger",
)

log_format = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s | %(message)s")

_mitsuki_log_handler = logging.StreamHandler(sys.stderr)
_mitsuki_log_handler.setFormatter(log_format)
_mitsuki_logger = logging.getLogger("mitsuki")
_mitsuki_logger.addHandler(_mitsuki_log_handler)

if os.environ.get("DEBUG") == "1":
  _mitsuki_logger.setLevel(logging.DEBUG)
else:
  _mitsuki_logger.setLevel(logging.INFO)

logger = _mitsuki_logger