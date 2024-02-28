# Copyright (c) 2024 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from interactions import (
  BaseUser,
  Embed,
  EmbedAuthor,
  EmbedAttachment,
  EmbedField,
  EmbedFooter,
)
from yaml import safe_load

from typing import (
  TypeAlias,
  Optional,
  Union,
  List,
  Dict,
  Any
)
from string import Template
from urllib.parse import urlparse
from copy import deepcopy
from os import PathLike


import logging
logger = logging.getLogger(__name__)


FileName: TypeAlias = Union[str, bytes, PathLike]
MessageTemplate: TypeAlias = Dict[str, Any]


class Messages:
  _templates: Dict[str, MessageTemplate]
  _default: MessageTemplate


  def __init__(self, template_file: FileName):
    self.reload(template_file)

  
  def reload(self, template_file: FileName):
    """
    Reload a message templates file (YAML).

    Args:
        template_file: Name of YAML template file.
    """
    self._templates = self._load(template_file)
    self._default   = self._load_template("default")

    num_templates = len(self._templates)
    logger.debug(
      f"Loaded {num_templates} message templates from file: '{template_file}'"
    )
  

  def modify(self, template_file: FileName):
    """
    Modify current message templates using a message templates file.

    If a particular template exists in the file, the existing template will be
    overwritten.

    Args:
        template_file: Name of YAML template file.
    """
    templates = self._load(template_file)
    self._templates.update(templates)

    num_templates = len(templates)
    logger.debug(
      f"Added/modified {num_templates} message templates from file: '{template_file}'"
    )
  

  def message(self, name: str, data: Optional[dict] = None, **kwargs):
    """
    Generate a message from a message template and its data.
    """
    if name not in self._templates.keys():
      raise ValueError(f"Message template '{name}' is invalid or does not exist")
    
    data = data or {}
    template  = deepcopy(self._default)
    template |= self._load_template(name)
    template  = _assign_data(template, data)
    template |= kwargs

    return _create_embed(template)
  

  def message_with_pages(
    self,
    name: str,
    pages_data: List[dict],
    base_data: Optional[dict] = None,
    colors: Optional[List[Union[str, int]]] = None,
    **kwargs
  ):
    if name not in self._templates.keys():
      raise ValueError(f"Message template '{name}' is invalid or does not exist")

    base_data = base_data or {}
    
    template  = deepcopy(self._default)
    template |= self._load_template(name)
    template  = _assign_data(template, base_data)

    colors = colors or []
    if len(colors) < len(pages_data):
      colors.append([
        self._default.get("color") for _ in range(len(pages_data) - len(colors))
      ])

    embeds = []
    pages = len(pages_data)
    for page, page_data in enumerate(pages_data, start=1):
      page_template  = deepcopy(template)
      page_template  = _assign_data(
        page_template,
        page_data | {"page": page, "pages": pages}
      )
      page_template |= kwargs
      embeds.append(_create_embed(page_template))
    
    return embeds
  

  # def message_with_fields(
  #   self,
  #   name: str,
  #   fields_data: List[dict],
  #   base_data: Optional[dict] = None,
  #   fields_per_page: int = 6,
  #   **kwargs
  # ):
  #   if name not in self._templates.keys():
  #     raise ValueError(f"Message template '{name}' is invalid or does not exist")

  #   base_data = base_data or {}
    
  #   template  = deepcopy(self._default)
  #   template |= self._load_template(name)
  #   template  = _assign_data(template, base_data)

  #   field_template = template.get("field")
  #   embeds = []
  #   pages = (max(0, len(fields_data) - 1) // fields_per_page) + 1

  #   cursor, page = 0, 1
  #   while cursor < len(fields_data):
  #     page_template = deepcopy(template)

  #     fields = []
  #     for field_data in fields_data[cursor : cursor + fields_per_page]:
  #       page_data = base_data | field_data

  #     page_template  = _assign_data(
  #       page_template,
  #       page_data | {"page": page, "pages": pages}
  #     )

  #     cursor += fields_per_page
  #     page += 1


  def _load(self, template_file: FileName):
    with open(template_file, encoding="UTF-8") as f:
      templates = safe_load(f)
    if not isinstance(templates, Dict):
      raise ValueError(f"Message template file '{template_file}' is invalid")
    
    return templates


  def _load_template(self, name: str):
    return self._templates.get(name) or {}


def _assign_data(
  template: MessageTemplate,
  data: Optional[dict] = None
):
  if data is None:
    return template
  if len(data) <= 0:
    return template
  assigned = deepcopy(template)

  DEPTH = 1

  def _recurse_assign(temp: Any, recursions: int = 0):
    assigned_temp: MessageTemplate = {}

    for key, value in temp.items():
      if isinstance(value, Dict) and recursions < DEPTH:
        assigned_value = _recurse_assign(value, recursions+1)
      elif isinstance(value, str):
        assigned_value = Template(value).safe_substitute(**data)
      else:
        assigned_value = value
      assigned_temp[key] = assigned_value

    return assigned_temp
  
  assigned = _recurse_assign(assigned)
  return assigned


def _create_embed(template: MessageTemplate):
  title = template.get("title")
  description = template.get("description")
  color = template.get("color")
  url = _valid_url_or_none(template.get("url"))

  fields_get = template.get("fields") or []
  fields = []
  for field_get in fields_get:
    if isinstance(field_get, Dict):
      field = EmbedField(
        name=field_get.get("name") or "",
        value=field_get.get("value") or "",
        inline=bool(field_get.get("inline"))
      )
      fields.append(field)

  author_get = template.get("author") or {}
  author = EmbedAuthor(
    name=author_get.get("name"),
    url=_valid_url_or_none(author_get.get("url")),
    icon_url=_valid_url_or_none(author_get.get("icon_url"))
  )

  thumbnail = EmbedAttachment(url=_valid_url_or_none(template.get("thumbnail")))

  image = EmbedAttachment(url=_valid_url_or_none(template.get("image")))
  images = [image]

  footer_get = template.get("footer") or {}
  footer = EmbedFooter(
    text=footer_get.get("text") or "",
    icon_url=_valid_url_or_none(footer_get.get("icon_url"))
  )

  return Embed(
    title=title,
    description=description,
    color=color,
    url=url,
    fields=fields,
    author=author,
    thumbnail=thumbnail,
    images=images,
    footer=footer
  )


def _valid_url_or_none(url: str):
  return url if _is_valid_url(url) else None


_messages: Optional[dict] = None


def load(source_file: str):
  global _messages
  with open(source_file, encoding="UTF-8") as f:
    _messages = safe_load(f)


def message(
  message_name: str,
  format: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  **kwargs
):
  _format = format or {}
  _format = _assign_user_to_format(_format, user)

  message_data = _init_message_data(
    message_name,
    format=_format,
    user=user,
    **kwargs
  )
  message_data = _assign_format(message_data, format=_format)
  embed_data   = _process_message_data(message_data)
  
  return Embed(**embed_data)


def message_with_pages(
  message_name: str,
  page_formats: List[dict],
  base_format: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  **kwargs
):
  base_message_data = _init_message_data(
    message_name,
    format=base_format,
    **kwargs
  )
  
  _base_format = base_format or {}
  _base_format = _assign_user_to_format(_base_format, user)

  embeds = []
  pages  = len(page_formats)
  for page, page_format in enumerate(page_formats, start=1):
    # message_data may have nested dicts, use deepcopy
    message_data = deepcopy(base_message_data)

    format = _base_format.copy()
    format.update({
      "page": page,
      "pages": pages
    })
    format.update(page_format)
    
    message_data = _assign_format(message_data, format=format)
    embed_data   = _process_message_data(message_data)
    embeds.append(Embed(**embed_data))
  
  return embeds


def message_with_fields(
  message_name: str,
  field_formats: List[dict],
  fields_per_embed: int = 6,
  base_format: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  **kwargs
):
  base_message_data = _init_message_data(
    message_name,
    format=base_format,
    **kwargs
  )

  field_data = base_message_data.get("field")

  _base_format = base_format or {}
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
    embeds.append(Embed(**embed_data))
    
    cursor += fields_per_embed
    page += 1

  return embeds


def username_from_user(user: BaseUser):
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

    author = EmbedAuthor(
      name=_author_data.get("name"),
      url=_url,
      icon_url=_icon_url
    )

  _thumbnail_data = message_data.get("thumbnail")
  thumbnail = None
  if isinstance(_thumbnail_data, str):
    if len(_thumbnail_data) > 0 and _is_valid_url(_thumbnail_data):
      thumbnail = EmbedAttachment(url=_thumbnail_data)
    
  _image_data = message_data.get("image")
  image = ""
  if isinstance(_image_data, str):
    if len(_image_data) > 0 and _is_valid_url(_image_data):
      image = EmbedAttachment(url=_image_data)
  images = [image] if image else []
  
  _footer_data = message_data.get("footer")
  footer = None
  if isinstance(_footer_data, dict):
    _icon_url = _footer_data.get("icon_url")
    _icon_url = _icon_url if _is_valid_url(_icon_url) else None

    footer = EmbedFooter(
      text=_footer_data.get("text"),
      icon_url=_icon_url
    )
  
  _fields_data = message_data.get("fields")
  fields = []
  if isinstance(_fields_data, list):
    for field_data in _fields_data:
      if isinstance(field_data, dict):
        fields.append(EmbedField(
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


def _assign_user_to_format(format: dict, user: Optional[BaseUser] = None):
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