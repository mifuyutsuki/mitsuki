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
import re

import asyncio
import contextlib
from copy import copy
from urllib.parse import urlparse
from string import Template
from typing import Optional, Union, List, Any


class PlaceholderComponent:
  def subst(self, context: dict[str, Any], *args, **kwargs) -> List[ipy.BaseComponent]:
    raise NotImplementedError


def disable_components(components: List[ipy.BaseComponent], hide: bool = False) -> List[ipy.BaseComponent]:
  new_components = []

  for c in components:
    if add_c := disable_component(c, hide=hide):
      new_components.append(add_c)

  return new_components


def disable_component(component: ipy.BaseComponent, hide: bool = False) -> Optional[ipy.BaseComponent]:
  result = component
  match result:
    case ipy.ActionRow():
      result.components = disable_components(result.components, hide=hide)
      if len(result.components) == 0:
        result = None  

    case ipy.BaseSelectMenu():
      if hide:
        result = None
      else:
        result.disabled = True

    case ipy.Button():
      if result.style == ipy.ButtonStyle.LINK:
        pass
      elif hide:
        result = None
      else:
        result.disabled = True

    case ipy.ContainerComponent():
      result.components = disable_components(result.components, hide=hide)

    case ipy.SectionComponent():
      if isinstance(result.accessory, ipy.Button):
        if hide:
          result = ipy.TextDisplayComponent("\n".join([c.content for c in result.components]))
        else:
          result.accessory.disabled = True

    case _:
      pass
  
  return result


def subst[T](data: dict, target: Optional[T] = None) -> Optional[T]:
  if isinstance(target, str):
    return Template(target).safe_substitute(**data)
  elif target:
    return target
  return None


def subst_components(components: list, context: dict[str, Any], **kwargs):
  results = []

  for c in components:
    add_c = subst_component(c, context, **kwargs)

    if isinstance(add_c, list):
      results.extend(add_c)
    elif add_c:
      results.append(add_c)

  return results


def subst_component(component, context: dict, **kwargs):
  try:
    result = copy(component)
  except Exception:
    result = component

  match result:
    case ipy.ActionRow():
      result.components = subst_components(result.components, context, **kwargs)

    case ipy.Button():
      result.label = subst(context, result.label)
      result.url = subst(context, result.url)
      result.custom_id = subst(context, result.custom_id)

    case ipy.BaseSelectMenu():
      # ipy.(String|User|Role|Mentionable|Channel)SelectMenu
      result.placeholder = subst(context, result.placeholder)
      result.custom_id = subst(context, result.custom_id)

    case ipy.ContainerComponent():
      result.components = subst_components(result.components, context, **kwargs)

    case ipy.TextDisplayComponent():
      result.content = subst(context, result.content)

    case ipy.MediaGalleryComponent():
      result.items = subst_components(result.items, context, **kwargs)

    case ipy.MediaGalleryItem():
      if valid_media_item := subst_component(result.media, context, **kwargs):
        result.media = valid_media_item
        result.description = subst(context, result.description)
      else:
        result = None

    case ipy.ThumbnailComponent():
      if valid_media_item := subst_component(result.media, context, **kwargs):
        result.media = valid_media_item
        result.description = subst(context, result.description)
      else:
        result = None

    case ipy.UnfurledMediaItem():
      if valid_media_url := get_valid_url(subst(context, result.url)):
        result.url = valid_media_url
      else:
        result = None

    case ipy.SeparatorComponent():
      pass

    case ipy.FileComponent():
      pass

    case ipy.SectionComponent():
      if valid_accessory := subst_component(result.accessory, context, **kwargs):
        result.components = subst_components(result.components, context, **kwargs)
        result.accessory = valid_accessory
      else:
        result = ipy.TextDisplayComponent("\n".join([c.content for c in result.components]))

    case PlaceholderComponent():
      result = result.subst(context, **kwargs)

    case _:
      # (ipy.SeparatorComponent, ipy.FileComponent, ...)
      result = None

  return result


def subst_embed(embed: ipy.Embed, context: dict):
  result = ipy.Embed()

  if embed.author:
    result.set_author(
      name=subst(context, embed.author.name),
      url=subst(context, embed.author.url),
      icon_url=subst(context, embed.author.icon_url),
    )

  if embed.title:
    result.title = subst(context, embed.title)

  if embed.description:
    result.description = subst(context, embed.description)

  if embed.url:
    result.url = get_valid_url(subst(context, embed.url))

  if embed.thumbnail:
    if valid_url := get_valid_url(subst(context, embed.thumbnail.url)):
      result.set_thumbnail(valid_url)

  if embed.image:
    if valid_url := get_valid_url(subst(context, embed.image.url)):
      result.set_image(valid_url)

  if embed.footer:
    result.set_footer(
      text=subst(context, embed.footer.text),
      icon_url=get_valid_url(subst(context, embed.footer.icon_url)),
    )

  if embed.color:
    result.color = subst(context, embed.color)

  for field in embed.fields:
    result.add_field(
      name=subst(context, field.name),
      value=subst(context, field.value),
      inline=field.inline,
    )


def is_valid_url(url: str) -> bool:
  parsed = urlparse(url)
  return parsed.scheme in ("http", "https", "ftp", "ftps") and len(parsed.netloc) > 0


def get_valid_url(url: str) -> Optional[str]:
  if is_valid_url(url):
    return url