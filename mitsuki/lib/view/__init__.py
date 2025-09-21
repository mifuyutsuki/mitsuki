# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

"""
Mitsuki interactions view framework.

Extends the creation of interaction responses with advanced features, such as
context loading, pagination, and timeouts.
"""

from .utils import (
  PlaceholderComponent,
)
from .core import (
  View,
  Timeout,
  add_timeout,
  reset_timeout,
  force_timeout,
  clear_timeout,
  timeout_resetter,
  timeout_clearer,
)
from .paginators import (
  SectionPaginatorMixin,
  SectionPaginatorContentPlaceholder,
  PaginatorNavPlaceholder,
  DividerStyle,
)

__all__ = (
  "PlaceholderComponent",
  "View",
  "Timeout",
  "add_timeout",
  "reset_timeout",
  "force_timeout",
  "clear_timeout",
  "timeout_resetter",
  "timeout_clearer",
  "SectionPaginatorMixin",
  "SectionPaginatorContentPlaceholder",
  "PaginatorNavPlaceholder",
  "DividerStyle",
)