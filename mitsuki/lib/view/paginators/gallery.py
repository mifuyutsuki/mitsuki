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
from mitsuki.lib.view.paginators import BasePaginatorMixin


@attrs.define(slots=False)
class GalleryPaginatorMixin(BasePaginatorMixin):
  """
  Single page per entry 'gallery' paginator.

  Each entry is rendered as a single page of this paginator, which may either
  be embed-based or component-based.

  By default, `components()` is set to a single `PaginatorNavPlaceholder` which
  contains page navigation buttons, typically used for embed-based paginators.
  To add extra components or use v2 components, use `PaginatorNavPlaceholder`
  explicitly in `components()` to show these buttons.
  """

  page_index: int = attrs.field(kw_only=True, default=0)


  @property
  def entries(self):
    try:
      return self._entries
    except Exception:
      self._entries = len(self.get_pages_context())
      return self._entries


  @property
  def pages(self):
    return self.entries


  def _generate(self):
    pages_context = self.get_pages_context()
    context = self.get_master_context() | self.get_context()

    if len(pages_context) == 0:
      if content := self.content_on_empty():
        content = utils.subst(context, content)

      if embeds := self.embeds_on_empty():
        for embed in embeds:
          embed = utils.subst_embed(embed)

      if components := self.components_on_empty():
        components = utils.subst_components(components, context, pages_context=pages_context)

    else:
      # This pattern allows for _nav_callback() to set page_index = -1
      # without knowing len(pages_context)
      if not (0 <= self.page_index < self.pages):
        self.page_index = self.pages - 1

      context |= pages_context[self.page_index]
      context |= {
        "page": self.page_index + 1,
        "pages": self.pages,
      }

      if content := self.content():
        content = utils.subst(context, content)

      if embeds := self.embeds():
        for embed in embeds:
          embed = utils.subst_embed(embed)

      if components := self.components():
        components = utils.subst_components(components, context, pages_context=pages_context)

    return {
      "content": content,
      "embeds": embeds,
      "components": components,
      "files": self.files(),
      "allowed_mentions": ipy.AllowedMentions.none(),
    }