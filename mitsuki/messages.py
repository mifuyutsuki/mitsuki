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
from mitsuki import settings
from mitsuki.utils import escape_text
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


class Message:
  content: Optional[str]
  embed: Optional[Embed]
  embeds: Optional[List[Embed]]

  def __init__(
    self,
    content: Optional[str] = None,
    embed: Optional[Embed] = None,
    embeds: Optional[List[Embed]] = None
  ):
    self.content = content
    self.embed = embed
    self.embeds = embeds
 

  def to_dict(self):
    """
    Generate kwargs for ctx.send().

    Returns:
        dict
    """
    return {
      "content": self.content,
      "embed": self.embed
    }


class MessageMan:
  _templates: Dict[str, MessageTemplate]
  _default: MessageTemplate


  def __init__(self, template_file: Optional[FileName] = None):
    if template_file:
      self.load(template_file)

  
  def load(self, template_file: FileName):
    """
    Load or reload a message templates file (YAML).

    Args:
        template_file: Name of YAML template file.
    """
    self._templates = self._load(template_file)
    self._default   = self._load_template("default")

    logger.debug(
      f"Loaded {len(self._templates)} message templates from file: '{template_file}'"
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

    logger.debug(
      f"Added/modified {len(templates)} message templates from file: '{template_file}'"
    )
  

  def message(
    self,
    template_name: str,
    data: Optional[dict] = None,
    user: Optional[BaseUser] = None,
    target_user: Optional[BaseUser] = None,
    escape_data_values: List[str] = [],
    **template_kwargs
  ) -> Message:
    """
    Generate a message from a message template and its data.

    The generated Message object may be passed as arguments to ctx.send() using
    Message.to_dict().

    Args:
        template_name: Name of message template obtained from template file
        data: Data to insert to the template
        user: User to include to data
        target_user: Target user to include to data
        escape_data_values: Data entries to be Markdown-escaped

    Kwargs:
        template_kwargs: Template overrides
    
    Returns:
        Message: Message object to be passed to send()
    
    Raises:
        ValueError: Message template 'name' does not exist in loaded file.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")
    
    data = data or {}
    if user:
      data |= user_data(user)
    if target_user:
      data |= target_user_data(target_user)

    template  = deepcopy(self._default)
    template |= self._load_template(template_name)
    template  = _assign_data(template, data, escapes=escape_data_values)
    template |= template_kwargs

    content = template.get("content")

    return Message(
      content=str(content) if content else None,
      embed=_create_embed(template)
    )
  

  def multipage(
    self,
    template_name: str,
    pages_data: List[dict],
    base_data: Optional[dict] = None,
    user: Optional[BaseUser] = None,
    target_user: Optional[BaseUser] = None,
    escape_data_values: List[str] = [],
    **template_kwargs
  ) -> Message:
    """
    Generate multiple-page messages from a message template and a list of data
    for each page.

    Args:
        template_name: Name of message template obtained from template file
        pages_data: List of data for each page to be inserted to the template
        base_data: Data to insert for all pages to the template
        user: User to include to data
        target_user: Target user to include to data
        escape_data_values: Data entries to be Markdown-escaped

    Kwargs:
        template_kwargs: Template overrides for all pages
    
    Returns:
        Message: Message object to be passed to Paginator
    
    Raises:
        ValueError: Message template 'name' does not exist.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")

    base_data = base_data or {}
    if user:
      base_data |= user_data(user)
    if target_user:
      base_data |= target_user_data(target_user)
    
    base_template  = deepcopy(self._default)
    base_template |= self._load_template(template_name)
    base_template  = _assign_data(base_template, base_data, escapes=escape_data_values)
    
    content = base_template.get("content")

    # Iterate one embed per page
    embeds = []
    pages = len(pages_data)
    for page, page_data in enumerate(pages_data, start=1):
      page_template  = deepcopy(base_template)
      page_template  = _assign_data(
        page_template,
        page_data | {"page": page, "pages": pages},
        escapes=escape_data_values
      )
      page_template |= template_kwargs
      embeds.append(_create_embed(page_template))
    
    return Message(
      content=str(content) if content else None,
      embeds=embeds
    )
  

  def multifield(
    self,
    template_name: str,
    fields_data: List[dict],
    base_data: Optional[dict] = None,
    user: Optional[BaseUser] = None,
    target_user: Optional[BaseUser] = None,
    fields_per_page: int = 6,
    escape_data_values: List[str] = [],
    **template_kwargs
  ):
    """
    Generate multiple-page message with recurring fields from a message
    template and a list of data for each field.

    Args:
        template_name: Name of message template obtained from template file
        fields_data: List of data for each field to be inserted to the template
        base_data: Data to insert for all pages to the template
        user: User to include to data
        target_user: Target user to include to data
        fields_per_page: Number of fields for each page
        escape_data_values: Data entries to be Markdown-escaped

    Kwargs:
        template_kwargs: Template overrides for all pages
    
    Returns:
        Message: Message object to be passed to Paginator
    
    Raises:
        ValueError: Message template 'name' does not exist.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")

    base_data = base_data or {}
    if user:
      base_data |= user_data(user)
    if target_user:
      base_data |= target_user_data(target_user)
    
    base_template  = deepcopy(self._default)
    base_template |= self._load_template(template_name)
    base_template  = _assign_data(base_template, base_data, escapes=escape_data_values)
    field_template = base_template.get("field")

    content = base_template.get("content")

    # Discord maximum is 25 fields
    fields_per_page = min(25, fields_per_page)

    embeds = []
    
    # Iterate <fields_per_page> fields per page
    pages = (max(0, len(fields_data) - 1) // fields_per_page) + 1
    cursor, page = 0, 1
    while cursor < len(fields_data):
      page_template = deepcopy(base_template)

      fields = []
      for field_data in fields_data[cursor : cursor + fields_per_page]:
        field_data = base_data | field_data
        fields.append(_assign_data(field_template, field_data, escapes=escape_data_values))     

      page_template = _assign_data(
        page_template | {"fields": fields},
        base_data | {"page": page, "pages": pages},
        escapes=escape_data_values
      )
      page_template |= template_kwargs
      embeds.append(_create_embed(page_template))

      cursor += fields_per_page
      page += 1
    
    return Message(
      content=str(content) if content else None,
      embeds=embeds
    )


  def _load(self, template_file: FileName):
    with open(template_file, encoding="UTF-8") as f:
      templates = safe_load(f)
    if not isinstance(templates, Dict):
      raise ValueError(f"Message template file '{template_file}' is invalid")
    
    return templates


  def _load_template(self, name: str):
    return self._templates.get(name) or {}


# =============================================================================


BASE_MESSAGES_YAML = settings.mitsuki.messages_default
MESSAGES_YAML = settings.mitsuki.messages

root = MessageMan()

# For logging reasons, use load() on first instead of two modify() calls
if BASE_MESSAGES_YAML:
  root.load(BASE_MESSAGES_YAML)
  if MESSAGES_YAML:
    root.modify(MESSAGES_YAML)
elif MESSAGES_YAML:
  root.load(MESSAGES_YAML)
else:
  logger.warning(
    "No MESSAGES_YAML found, initializing root MessageMan with no templates"
  )


# =============================================================================


def load_message(
  template_name: str,
  data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  escape_data_values: List[str] = [],
  **template_kwargs
) -> Message:
  """
  Generate a message from a message template and its data.

  The generated Message object may be passed as arguments to ctx.send() using
  Message.to_dict().

  This function uses the root MessageMan, which is determined by MESSAGES_YAML
  and BASE_MESSAGES_YAML settings variables.

  Args:
      template_name: Name of message template obtained from template file
      data: Data to insert to the template
      user: User to include to data
      target_user: Target user to include to data
      escape_data_values: Data entries to be Markdown-escaped

  Kwargs:
      template_kwargs: Template overrides
  
  Returns:
      Message: Message object to be passed to send()
  
  Raises:
      ValueError: Message template 'name' does not exist in loaded file.
  """
  return root.message(
    template_name=template_name,
    data=data,
    user=user,
    target_user=target_user,
    escape_data_values=escape_data_values,
    **template_kwargs
  )


def load_multipage(
  template_name: str,
  pages_data: List[dict],
  base_data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  escape_data_values: List[str] = [],
  **template_kwargs
) -> Message:
  """
  Generate multiple-page messages from a message template and a list of data
  for each page.

  This function uses the root MessageMan, which is determined by MESSAGES_YAML
  and BASE_MESSAGES_YAML settings variables.

  Args:
      template_name: Name of message template obtained from template file
      pages_data: List of data for each page to be inserted to the template
      base_data: Data to insert for all pages to the template
      user: User to include to data
      target_user: Target user to include to data
      escape_data_values: Data entries to be Markdown-escaped

  Kwargs:
      template_kwargs: Template overrides for all pages
  
  Returns:
      Message: Message object to be passed to Paginator
  
  Raises:
      ValueError: Message template 'name' does not exist.
  """
  return root.multipage(
    template_name=template_name,
    pages_data=pages_data,
    base_data=base_data,
    user=user,
    target_user=target_user,
    escape_data_values=escape_data_values,
    **template_kwargs
  )


def load_multifield(
  template_name: str,
  fields_data: List[dict],
  base_data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  fields_per_page: int = 6,
  escape_data_values: List[str] = [],
  **template_kwargs
):
  """
  Generate multiple-page message with recurring fields from a message
  template and a list of data for each field.

  This function uses the root MessageMan, which is determined by MESSAGES_YAML
  and BASE_MESSAGES_YAML settings variables.

  Args:
      template_name: Name of message template obtained from template file
      fields_data: List of data for each field to be inserted to the template
      base_data: Data to insert for all pages to the template
      user: User to include to data
      target_user: Target user to include to data
      fields_per_page: Number of fields for each page
      escape_data_values: Data entries to be Markdown-escaped

  Kwargs:
      template_kwargs: Template overrides for all pages
  
  Returns:
      Message: Message object to be passed to Paginator
  
  Raises:
      ValueError: Message template 'name' does not exist.
  """
  return root.multifield(
    template_name=template_name,
    fields_data=fields_data,
    base_data=base_data,
    user=user,
    target_user=target_user,
    fields_per_page=fields_per_page,
    escape_data_values=escape_data_values,
    **template_kwargs
  )


def user_data(user: BaseUser):
  return {
    "username": user.tag,
    "usericon": user.avatar_url,
    "user": user.mention
  }


def target_user_data(user: BaseUser):
  return {
    "target_username": user.tag,
    "target_usericon": user.avatar_url,
    "target_user": user.mention
  }


# =============================================================================


def _assign_data(
  template: MessageTemplate,
  data: Optional[Dict[str, Any]] = None,
  escapes: List[str] = []
):
  if data is None:
    return template
  if len(data) <= 0:
    return template
  assigned = deepcopy(template)

  DEPTH = 3

  escaped_data = data.copy()
  for key, value in data.items():
    if key in escapes and isinstance(value, str):
      escaped_data[key] = escape_text(value)

  def _recurse_assign(temp: Any, recursions: int = 0):
    is_dict = isinstance(temp, Dict)
    is_list = isinstance(temp, List)
    assigned_temp = {} if is_dict else []

    if is_dict:
      seq = temp.items()
    elif is_list:
      seq = temp
    else:
      seq = []
    
    for s in seq:
      if is_dict:
        key, value = s
      else:
        value = s
      
      if isinstance(value, (Dict, List)) and recursions < DEPTH:
        assigned_value = _recurse_assign(value, recursions+1)
      elif isinstance(value, str):
        assigned_value = Template(value).safe_substitute(**escaped_data)
      else:
        assigned_value = value
      
      if is_dict:
        assigned_temp[key] = assigned_value
      elif is_list:
        assigned_temp.append(assigned_value)

    return assigned_temp
  
  assigned = _recurse_assign(assigned)
  return assigned


def _create_embed(template: MessageTemplate):
  title = template.get("title")
  description = template.get("description")
  color = int(template.get("color") or 0)
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

  author_get = template.get("author")
  author = EmbedAuthor(
    name=author_get.get("name"),
    url=_valid_url_or_none(author_get.get("url")),
    icon_url=_valid_url_or_none(author_get.get("icon_url"))
  ) if author_get else None

  thumbnail = EmbedAttachment(url=_valid_url_or_none(template.get("thumbnail")))

  image = EmbedAttachment(url=_valid_url_or_none(template.get("image")))
  images = [image]

  footer_get = template.get("footer")
  footer = EmbedFooter(
    text=footer_get.get("text") or "",
    icon_url=_valid_url_or_none(footer_get.get("icon_url"))
  ) if footer_get else None

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


def _is_valid_url(url: Optional[str]):
  # Good enough approach - robust alternative from Django is rather long
  if not isinstance(url, str):
    return False
  
  parsed = urlparse(url)
  return (
    parsed.scheme in ("http", "https", "ftp", "ftps") and
    len(parsed.netloc) > 0
  )
