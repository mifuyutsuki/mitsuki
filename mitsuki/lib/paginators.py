# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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
  ActionRow,
  StringSelectMenu,
  StringSelectOption,
  Client,
  Embed,
  ComponentCommand,
  ModalCommand,
  ModalContext,
)

from mitsuki import settings
from attrs import define, field
from typing import Union, List, Optional, Callable, Coroutine


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

  extra_components: List[ActionRow] = field(repr=False, factory=list)


  def __attrs_post_init__(self):
    super().__attrs_post_init__()

    if settings.emoji:
      self.first_button_emoji = settings.emoji.page_first
      self.back_button_emoji = settings.emoji.page_previous
      self.next_button_emoji = settings.emoji.page_next
      self.last_button_emoji = settings.emoji.page_last

    if len(self.pages) > 3:
      self.callback = self.callback_cmd
      self.show_callback_button = True
      self.callback_button_emoji = settings.emoji.page_goto
      self.client.add_modal_callback(
        ModalCommand(
          name=f"PageNo:{self._uuid}",
          callback=self._on_pageno,
          listeners=[
            f"{self._uuid}|pageno",
          ],
        )
      )


  def create_components(self, disable: bool = False):
    if disable and self._timeout_task:
      self._timeout_task.run = False
    return super().create_components(disable)


  def to_dict(self) -> dict:
    source = super().to_dict()
    if len(self.extra_components) > 0:
      source["components"].extend([c.to_dict() for c in self.extra_components])
    return source


  async def callback_cmd(self, ctx: ComponentContext):
    # Reset the timeout timer
    if self._timeout_task:
      self._timeout_task.ping.set()

    await ctx.send_modal(
      modal=Modal(
        ShortText(
          label="Page number",
          custom_id="page_no",
          placeholder=f"Number from 1 to {len(self.pages)}",
        ),
        title="Go to Page",
        custom_id=f"{self._uuid}|pageno",
      )
    )


  async def _on_pageno(self, ctx: ModalContext):
    if self._timeout_task:
      # Exit if paginator times out
      if not self._timeout_task.run:
        await ctx.send(f"Interaction timed out", ephemeral=True)
        return

      # Reset the timeout timer
      self._timeout_task.ping.set()

    page_no_s = ctx.responses["page_no"].strip()
    if not page_no_s.isnumeric():
      # Response is not a number
      await ctx.send(f"Not a valid page number", ephemeral=True)
      return
    page_no = int(page_no_s)
    if not (0 < page_no <= len(self.pages)):
      # Out of range
      await ctx.send(f"Page number out of range", ephemeral=True)
      return
    if page_no - 1 == self.page_index:
      # Same page
      await ctx.edit(ctx.message)
    else:
      self.page_index = page_no - 1
      await ctx.defer(edit_origin=True)
      await ctx.edit(ctx.message, **self.to_dict())


@define(eq=False, order=False, hash=False, kw_only=False)
class SelectionPaginator(Paginator):
  selection_values: List[Union[StringSelectOption, str]] = field(repr=False, factory=list)
  selection_per_page: int = field(repr=False, default=6)
  selection_placeholder: str = field(repr=False, default="Select value...")
  selection_callback: Callable[..., Coroutine] = field(repr=False, default=None)


  def __attrs_post_init__(self) -> None:
    self.client.add_component_callback(
      ComponentCommand(
        name=f"Paginator:{self._uuid}",
        callback=self._on_button,
        listeners=[
          f"{self._uuid}|select",
          f"{self._uuid}|first",
          f"{self._uuid}|back",
          f"{self._uuid}|callback",
          f"{self._uuid}|next",
          f"{self._uuid}|last",
          f"{self._uuid}|selector",
        ],
      )
    )

    if settings.emoji:
      self.first_button_emoji = settings.emoji.page_first
      self.back_button_emoji = settings.emoji.page_previous
      self.next_button_emoji = settings.emoji.page_next
      self.last_button_emoji = settings.emoji.page_last

    if len(self.pages) > 3:
      self.callback = self.callback_cmd
      self.show_callback_button = True
      self.callback_button_emoji = settings.emoji.page_goto
      self.client.add_modal_callback(
        ModalCommand(
          name=f"PageNo:{self._uuid}",
          callback=self._on_pageno,
          listeners=[
            f"{self._uuid}|pageno",
          ],
        )
      )


  def create_components(self, disable: bool = False):
    if disable and self.hide_buttons_on_stop:
      return []

    selection = []
    if len(self.selection_values) > 0 and self.selection_callback:
      selection = [ActionRow(StringSelectMenu(
        *(
          selection_value if isinstance(selection_value, StringSelectOption)
          else StringSelectOption(
            label=str(selection_value),
            value=str(selection_value),
          )
          for selection_value in self.selection_values[
            self.page_index * self.selection_per_page : (self.page_index + 1) * self.selection_per_page
          ]
        ),
        placeholder=self.selection_placeholder,
        disabled=disable,
        custom_id=f"{self._uuid}|selector"
      ))]
    return selection + super().create_components(disable=disable)


  async def _on_button(self, ctx: ComponentContext, *args, **kwargs):
    if ctx.author.id != self.author_id:
      return (
        await ctx.send(self.wrong_user_message, ephemeral=True)
        if self.wrong_user_message
        else await ctx.defer(edit_origin=True)
      )

    if self._timeout_task:
      self._timeout_task.ping.set()

    match ctx.custom_id.split("|")[1]:
      case "first":
        self.page_index = 0
      case "last":
        self.page_index = len(self.pages) - 1
      case "next":
        if (self.page_index + 1) < len(self.pages):
          self.page_index += 1
      case "back":
        if self.page_index >= 1:
          self.page_index -= 1
      case "select":
        self.page_index = int(ctx.values[0])
      case "selector":
        if self.selection_callback:
          return await self.selection_callback(ctx)
      case "callback":
        if self.callback:
          return await self.callback(ctx)

    await ctx.edit_origin(**self.to_dict())
    return None