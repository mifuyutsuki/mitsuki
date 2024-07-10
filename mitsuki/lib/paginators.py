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
from interactions import (
  ButtonStyle,
  ComponentContext,
  Modal,
  ShortText,
)
from attrs import define, field


@define(eq=False, order=False, hash=False, kw_only=False)
class Paginator(_Paginator):
  first_button_emoji = field(repr=False, default="⏪")
  back_button_emoji = field(repr=False, default="◀")
  next_button_emoji = field(repr=False, default="▶")
  last_button_emoji = field(repr=False, default="⏩")
  callback_button_emoji = field(repr=False, default="#️⃣")
  hide_buttons_on_stop = field(repr=False, default=True)
  default_button_color = field(repr=False, default=ButtonStyle.GRAY)
  wrong_user_message = field(repr=False, default="This interaction is not for you")

  def __attrs_post_init__(self):
    super().__attrs_post_init__()
    if len(self.pages) > 1:
      self.callback = self.callback_cmd
      self.show_callback_button = True

  async def callback_cmd(self, ctx: ComponentContext):
    m = await ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Page number",
          custom_id="page_no",
          placeholder=f"Number from 1 to {len(self.pages)}",
        ),
        title="Go to Page"
      )
    )
    try:
      modal_ctx = await ctx.bot.wait_for_modal(m)
    except TimeoutError:
      return

    # Reset the timeout timer
    self._timeout_task.ping.set()

    page_no_s = modal_ctx.responses["page_no"]
    if not page_no_s.isnumeric():
      # Response is not a number
      await modal_ctx.send(f"Not a valid page number", ephemeral=True)
      return
    page_no = int(page_no_s)
    if not (0 < page_no <= len(self.pages)):
      # Out of range
      await modal_ctx.send(f"Page number out of range", ephemeral=True)
      return
    if page_no - 1 == self.page_index:
      # Same page
      await modal_ctx.edit(ctx.message)
    else:
      self.page_index = page_no - 1
      await modal_ctx.defer(edit_origin=True)
      await modal_ctx.edit(ctx.message, **self.to_dict())