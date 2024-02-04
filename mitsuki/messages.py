# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

import interactions as ipy
from yaml import safe_load
from typing import Optional, List
from string import Template
from urllib.parse import urlparse
from copy import deepcopy


_messages: Optional[dict] = None


def load(source_file: str):
  global _messages
  with open(source_file, encoding="UTF-8") as f:
    _messages = safe_load(f)


def message(
  message_name: str,
  format: Optional[dict] = None,
  user: Optional[ipy.BaseUser] = None,
  **kwargs
):
  global _messages
  
  _format = format if format else {}
  _format = _assign_user_to_format(_format, user)

  message_data = _init_message_data(
    message_name,
    format=_format,
    user=user,
    **kwargs
  )
  message_data = _assign_format(message_data, format=_format)
  embed_data   = _process_message_data(message_data)
  
  return ipy.Embed(**embed_data)


def message_with_fields(
  message_name: str,
  field_formats: List[dict],
  fields_per_embed: int = 6,
  base_format: Optional[dict] = None,
  user: Optional[ipy.BaseUser] = None,
  **kwargs
):
  base_message_data = _init_message_data(
    message_name,
    format=base_format,
    **kwargs
  )

  field_data = base_message_data.get("field")

  _base_format = base_format if base_format else {}
  _base_format = _assign_user_to_format(_base_format, user)

  embeds = []
  cursor = 0
  page   = 1
  pages  = (max(0, len(field_formats) - 1) // fields_per_embed) + 1

  while cursor < len(field_formats):
    # message_data may have nested dicts, use deepcopy
    message_data = deepcopy(base_message_data)
    format = _base_format.copy()
    format.update(page=page, pages=pages)

    fields = []
    if isinstance(field_data, dict):
      for idx in range(cursor, cursor + fields_per_embed):
        try:
          field_format = field_formats[idx]
        except IndexError:
          break

        field_format.update(**format)
        field = field_data.copy()
        field = _assign_format(field, format=field_format)
        fields.append(field)
    
    message_data["fields"] = fields
    message_data = _assign_format(message_data, format=format)
    embed_data   = _process_message_data(message_data)
    embeds.append(ipy.Embed(**embed_data))
    
    cursor += fields_per_embed
    page += 1

  return embeds


def username_from_user(user: ipy.BaseUser):
  if user.discriminator == "0":
    return user.username
  else:
    return f"{user.username}#{user.discriminator}"
  

def _init_message_data(
  message_name: str,
  format: Optional[dict] = None,
  **kwargs  
):
  global _messages
  _format = format if format else {}

  # Get default
  message_data_get: dict = _messages.get("default")
  if isinstance(message_data_get, dict):
    message_data = message_data_get.copy()
  else:
    message_data = {}
  
  # Get <message_name>
  message_data_get = _messages.get(message_name)
  if isinstance(message_data_get, dict):  
    message_data.update(message_data_get)
  else:
    raise KeyError(
      f"Message '{message_name}' not found or invalid"
    )
  
  # Get overrides
  message_data.update(**kwargs)
  
  # Assign format fields e.g. ${shards}
  return message_data


def _process_message_data(message_data: dict):
  title       = message_data.get("title")
  url         = message_data.get("url")
  description = message_data.get("description")
  color       = message_data.get("color")

  url = url if _is_valid_url(url) else None
  
  _author_data = message_data.get("author")
  author = None
  if isinstance(_author_data, dict):
    _url = _author_data.get("url")
    _url = _url if _is_valid_url(_url) else None
    _icon_url = _author_data.get("icon_url")
    _icon_url = _icon_url if _is_valid_url(_icon_url) else None

    author = ipy.EmbedAuthor(
      name=_author_data.get("name"),
      url=_url,
      icon_url=_icon_url
    )

  _thumbnail_data = message_data.get("thumbnail")
  thumbnail = None
  if isinstance(_thumbnail_data, str):
    if len(_thumbnail_data) > 0 and _is_valid_url(_thumbnail_data):
      thumbnail = ipy.EmbedAttachment(url=_thumbnail_data)
    
  _image_data = message_data.get("image")
  image = ""
  if isinstance(_image_data, str):
    if len(_image_data) > 0 and _is_valid_url(_image_data):
      image = ipy.EmbedAttachment(url=_image_data)
  images = [image] if image else []
  
  _footer_data = message_data.get("footer")
  footer = None
  if isinstance(_footer_data, dict):
    _icon_url = _footer_data.get("icon_url")
    _icon_url = _icon_url if _is_valid_url(_icon_url) else None

    footer = ipy.EmbedFooter(
      text=_footer_data.get("text"),
      icon_url=_icon_url
    )
  
  _fields_data = message_data.get("fields")
  fields = []
  if isinstance(_fields_data, list):
    for field_data in _fields_data:
      if isinstance(field_data, dict):
        fields.append(ipy.EmbedField(
          name=field_data.get("name"),
          value=field_data.get("value"),
          inline=field_data.get("inline")
        ))
  
  return dict(
    title=title,
    description=description,
    color=color,
    url=url,
    images=images,
    fields=fields,
    author=author,
    thumbnail=thumbnail,
    footer=footer
  )


def _assign_format(
  data: dict,
  format: Optional[dict] = None,
  recursion_level: int = 0
):
  if format is None:
    return data
  if len(format) <= 0:
    return data
  
  formatted_data = data.copy()
  for key, value in data.items():
    if isinstance(value, dict) and recursion_level < 1:
      formatted_value = _assign_format(value, format, recursion_level+1)
    elif isinstance(value, str):
      formatted_value = Template(value).safe_substitute(**format)
    else:
      formatted_value = value
    formatted_data[key] = formatted_value
  
  return formatted_data


def _assign_user_to_format(format: dict, user: Optional[ipy.BaseUser] = None):
  _format = deepcopy(format)
  
  # Get username, usericon
  if user is not None:
    _format.update(username=username_from_user(user), usericon=user.avatar_url)
  return _format


def _is_valid_url(url: Optional[str]):
  # Good enough approach - robust alternative from Django is rather long
  if not isinstance(url, str):
    return False
  
  parsed = urlparse(url)
  return (
    parsed.scheme in ("http", "https", "ftp", "ftps") and
    len(parsed.netloc) > 0
  )