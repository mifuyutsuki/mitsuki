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
import attrs
import uuid

from typing import Optional, Union, List, Any
from enum import IntEnum

from mitsuki.logger import logger
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import PlaceholderComponent, reset_timeout


class DividerStyle(IntEnum):
  NONE = 0
  HIDDEN = 1
  SMALL = 2
  LARGE = 3


@attrs.define(slots=False)
class BasePaginatorMixin:
  id: uuid.UUID = attrs.field(init=False)
  _entries: int = attrs.field(init=False)


  def __attrs_post_init__(self):
    super().__attrs_post_init__()
    self.id = uuid.uuid4()


  def components(self) -> Optional[List[Union[ipy.BaseComponent, "PlaceholderComponent"]]]:
    return [PaginatorNavPlaceholder()]


  def components_on_empty(self) -> List[ipy.BaseComponent]:
    return self.components()


  def embeds_on_empty(self) -> Optional[List[ipy.Embed]]:
    return None


  def content_on_empty(self) -> Optional[str]:
    return None


  def get_master_context(self) -> dict[str, Any]:
    return super().get_master_context() | {"uuid": self.id}


  def get_pages_context(self) -> list[dict[str, Any]]:
    return []


  async def _post_send(self, timeout: Optional[float] = None, **kwargs):
    await super()._post_send()
    if timeout and timeout > 0:
      self.client.add_component_callback(
        ipy.ComponentCommand(
          name=f"Paginator:{self.id}",
          callback=self._nav_callback,
          listeners=[
            f"{self.id}|first",
            f"{self.id}|prev",
            f"{self.id}|next",
            f"{self.id}|last",
            f"{self.id}|pageno",
          ],
        )
      )
      self.client.add_modal_callback(
        ipy.ModalCommand(
          name=f"PaginatorGoto:{self.id}",
          callback=self._pageno_response,
          listeners=[
            f"{self.id}|pageno",
          ],
        )
      )


  async def _nav_callback(self, ctx: ipy.ComponentContext):
    match custom_id := ctx.custom_id.split("|")[-1]:
      case "first":
        self.page_index = 0
      case "prev":
        self.page_index = max(0, self.page_index - 1)
      case "next":
        self.page_index += 1
      case "last":
        self.page_index = -1
      case "pageno":
        return await self._pageno_prompt(ctx)
      case _:
        raise ValueError("Unexpected paginator custom id action: '{}'".format(custom_id))

    edit_kwargs = self._generate()
    message = await ctx.edit_origin(**edit_kwargs)
    await reset_timeout(message.id)
    self._send_kwargs = edit_kwargs
    self._message = message


  async def _pageno_prompt(self, ctx: ipy.ComponentContext):
    await ctx.send_modal(
      modal=ipy.Modal(
        ipy.ShortText(
          label="Page number",
          custom_id="page_no",
          placeholder=f"Number from 1 to {self.pages}",
        ),
        title="Go to Page",
        custom_id=f"{self.id}|pageno",
      )
    )
    await reset_timeout(self.message.id)


  async def _pageno_response(self, ctx: ipy.ModalContext, page_no: str):
    if self.is_disabled:
      return await ctx.send("Interaction has timed out.", ephemeral=True)

    try:
      page_no = int(page_no)
    except Exception:
      return await ctx.send("Not a valid page number.", ephemeral=True)

    if not (0 < page_no <= self.pages):
      return await ctx.send("Page number out of range.", ephemeral=True)

    if page_no - 1 == self.page_index:
      # Same page
      message = await ctx.edit(ctx.message)
    else:
      self.page_index = page_no - 1
      edit_kwargs = self._generate()
      message = await ctx.edit(ctx.message, **edit_kwargs)
      self._send_kwargs = edit_kwargs
    await reset_timeout(message)
    self._message = message


class PaginatorNavPlaceholder(PlaceholderComponent):
  def subst(self, context: dict[str, Any], **kwargs) -> List[ipy.BaseComponent]:
    id, page, pages = context["uuid"], int(context["page"]), int(context["pages"])

    return [ipy.ActionRow(
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_FIRST),
        custom_id="{}|first".format(id),
        disabled=page <= 1
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_PREVIOUS),
        custom_id="{}|prev".format(id),
        disabled=page <= 1
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        label="{}/{}".format(page, pages),
        custom_id="{}|pageno".format(id),
        disabled=pages < 4
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_NEXT),
        custom_id="{}|next".format(id),
        disabled=page >= pages
      ),
      ipy.Button(
        style=ipy.ButtonStyle.GRAY,
        emoji=get_emoji(AppEmoji.PAGE_LAST),
        custom_id="{}|last".format(id),
        disabled=page >= pages
      ),
    )]