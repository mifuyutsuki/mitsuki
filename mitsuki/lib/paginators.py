# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions.ext.paginators import Paginator as _Paginator
from attrs import define, field


@define(eq=False, order=False, hash=False, kw_only=False)
class Paginator(_Paginator):
  first_button_emoji = field(repr=False, default="⏪")
  back_button_emoji = field(repr=False, default="◀")
  next_button_emoji = field(repr=False, default="▶")
  last_button_emoji = field(repr=False, default="⏩")
  callback_button_emoji = field(repr=False, default="#️⃣")
  hide_buttons_on_stop = field(repr=False, default=True)