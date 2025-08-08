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

from mitsuki.logger import logger
from mitsuki.lib.emoji import AppEmoji, get_emoji
from mitsuki.lib.view import PlaceholderComponent, reset_timeout, add_timeout, utils


@attrs.define(slots=False)
class SectionPaginatorMixin:
  entries_data: list[dict[str, Any]] = attrs.field(kw_only=True, factory=list)
  entries_per_page: int = attrs.field(kw_only=True, default=5)
  page_index: int = attrs.field(kw_only=True, default=0)

  id: uuid.UUID = attrs.field(init=False)
  _entries: int = attrs.field(init=False)


  def __attrs_post_init__(self):
    super().__attrs_post_init__()
    self.id = uuid.uuid4()


  @property
  def entries(self):
    try:
      return self._entries
    except Exception:
      self._entries = len(self.get_pages_context())
      return self._entries


  @property
  def pages(self):
    return 1 + ((self.entries - 1) // self.entries_per_page)


  def components_on_empty(self) -> List[ipy.BaseComponent]:
    return self.components()


  def get_master_context(self) -> dict[str, Any]:
    return super().get_master_context() | {"uuid": self.id}


  def get_pages_context(self) -> list[dict[str, Any]]:
    return []


  def section(self) -> List[Union[ipy.SectionComponent, ipy.TextDisplayComponent]]:
    raise NotImplementedError("Section format is required to use this paginator")


  async def _post_send(self, timeout: Optional[float] = None, **kwargs):
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


  def _generate(self):
    if not self.is_components_v2:
      raise ValueError("Components v2 is required by this paginator")

    pages_context = self.get_pages_context()
    context = self.get_master_context() | self.get_context()

    if len(pages_context) == 0:
      components = utils.subst_components(self.components_on_empty(), context)
    else:
      pages = 1 + ((self.entries - 1) // self.entries_per_page)

      # This pattern allows for _nav_callback() to set page_index = -1
      # without knowing len(pages_context)
      if not (0 <= self.page_index < self.entries):
        self.page_index = pages - 1

      context |= {
        "page": self.page_index + 1,
        "pages": pages,
      }
      components = utils.subst_components(
        self.components(), context,
        pages_context=pages_context,
        page_index=self.page_index,
        per_page=self.entries_per_page,
        section=self.section()
      )

    return {"components": components, "files": self.files()}


class SectionPaginatorContentPlaceholder(PlaceholderComponent):
  def subst(
    self,
    context: dict[str, Any],
    *,
    pages_context: list[dict[str, Any]],
    page_index: int,
    per_page: int,
    section: List[ipy.BaseComponent]
  ) -> List[ipy.BaseComponent]:
    results = []

    for page_context in pages_context[per_page * page_index : per_page * (page_index + 1)]:
      this_context = context | page_context
      for c in section:
        if isinstance(c, PlaceholderComponent):
          raise ValueError("Cannot nest a placeholder component inside another placeholder component")

        add_c = utils.subst_component(c, this_context)
        if isinstance(add_c, list):
          results.extend(add_c)
        elif add_c:
          results.append(add_c)
      results.append(ipy.SeparatorComponent(divider=True))

    return results


class SectionPaginatorNavPlaceholder(PlaceholderComponent):
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