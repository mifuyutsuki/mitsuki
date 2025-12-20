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
from mitsuki.lib.view.paginators import BasePaginatorMixin, DividerStyle


@attrs.define(slots=False)
class SectionPaginatorMixin(BasePaginatorMixin):
  """
  Component-based multifield paginator.

  Each field entry is rendered as a series of components given by `section()`,
  which must be implemented to use this paginator.

  To use this paginator, the view must use v2 components (embeds and content
  being unset), using the following placeholder components:
  - `SectionPaginatorContentPlaceholder`, which would be substituted by page
    entries given by overridable method `section()`, and
  - `PaginatorNavPlaceholder`, which displays page navigation buttons.
  """

  entries_per_page: int = attrs.field(kw_only=True, default=5)
  page_index: int = attrs.field(kw_only=True, default=0)
  divider_style: DividerStyle = attrs.field(kw_only=True, default=DividerStyle.NONE)


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


  def section(self) -> List[ipy.BaseComponent]:
    raise NotImplementedError("Implementation of this method is required to use this paginator")


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
        section=self.section(),
        divider_style=self.divider_style,
      )

    return {"components": components, "files": self.files(), "allowed_mentions": ipy.AllowedMentions.none()}


class SectionPaginatorContentPlaceholder(PlaceholderComponent):
  def subst(
    self,
    context: dict[str, Any],
    *,
    pages_context: list[dict[str, Any]],
    page_index: int,
    per_page: int,
    section: List[ipy.BaseComponent],
    divider_style: DividerStyle = DividerStyle.NONE,
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

        match divider_style:
          case DividerStyle.LARGE:
            results.append(ipy.SeparatorComponent(divider=True, spacing=ipy.SeparatorSpacingSize.LARGE))
          case DividerStyle.SMALL:
            results.append(ipy.SeparatorComponent(divider=True, spacing=ipy.SeparatorSpacingSize.SMALL))
          case DividerStyle.HIDDEN:
            results.append(ipy.SeparatorComponent(divider=False))
          case _:
            pass

    # Last separator is always small, as it separates the paginated section from the rest
    # A: When pages_context and section are both not empty
    try:
      # When divider style is not NONE (added above)
      if isinstance(results[-1], ipy.SeparatorComponent):
        results[-1] = ipy.SeparatorComponent(divider=True)
      # When divider style is NONE
      elif divider_style == DividerStyle.NONE:
        results.append(ipy.SeparatorComponent(divider=True))
    # B: When either pages_context or section is empty
    except IndexError:
      pass

    return results