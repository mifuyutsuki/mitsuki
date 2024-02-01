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
from typing import Optional
from string import Template
from urllib.parse import urlparse


class Messages(dict):
  pass
    
messages: Optional[Messages] = None


def load(source_file: str):
  global messages
  with open(source_file, encoding="UTF-8") as f:
    messages = safe_load(f)


def generate(
  message_name: str,
  format: Optional[dict] = None,
  user: Optional[ipy.BaseUser] = None,
  **kwargs
):
  global messages
  _format = format if format else {}

  # -----------------------------------------------------------------
  # Grab message data from yaml data and kwargs

  # Get default
  message_data_get: dict = messages.get("default")
  if isinstance(message_data_get, dict):
    message_data = message_data_get.copy()
  else:
    message_data = {}
  
  # Get <message_name>
  message_data_get = messages.get(message_name)
  if isinstance(message_data_get, dict):  
    message_data.update(message_data_get)
  else:
    raise KeyError(
      f"Message '{message_name}' not found or invalid"
    )
  
  # Get overrides
  message_data.update(**kwargs)

  # Get username, usericon
  if user is not None:
    _format.update(username=username_from_user(user), usericon=user.avatar_url)
  
  # Assign format fields e.g. ${shards}
  message_data = _assign_format(message_data, _format)
  
  # -----------------------------------------------------------------
  # Handle keys

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
      fields.append(ipy.EmbedField(
        name=field_data.get("name"),
        value=field_data.get("value"),
        inline=field_data.get("inline")
      ))
  
  return ipy.Embed(
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


def username_from_user(user: ipy.BaseUser):
  if user.discriminator == "0":
    return user.username
  else:
    return f"{user.username}#{user.discriminator}"


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


def _is_valid_url(url: Optional[str]):
  # Good enough approach - robust alternative from Django is rather long
  if not isinstance(url, str):
    return False
  
  parsed = urlparse(url)
  return (
    parsed.scheme in ("http", "https", "ftp", "ftps") and
    len(parsed.netloc) > 0
  )