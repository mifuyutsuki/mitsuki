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


  def __attrs_post_init__(self):
    super().__attrs_post_init__()
    self.id = uuid.uuid4()


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
        # TODO: "Go to page" modal
        pass
      case _:
        raise ValueError("Unexpected paginator custom id action: '{}'".format(custom_id))

    edit_kwargs = self._generate()
    message = await ctx.edit_origin(**edit_kwargs)
    await reset_timeout(message.id)
    self._send_kwargs = edit_kwargs
    self._message = message


  def _generate(self):
    if not self.is_components_v2:
      raise ValueError("Components v2 is required by this paginator")

    pages_context = self.get_pages_context()
    context = self.get_master_context() | self.get_context()

    if len(pages_context) == 0:
      components = utils.subst_components(self.components_on_empty(), context)
    else:
      pages = 1 + ((len(pages_context) - 1) // self.entries_per_page)

      # This pattern allows for _nav_callback() to set page_index = -1
      # without knowing len(pages_context)
      if not (0 <= self.page_index < len(pages_context)):
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
        disabled=True # TODO: pages < 4
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