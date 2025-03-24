# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

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
  process_color,
)
from yaml import safe_load
from attrs import define, asdict as _asdict

from mitsuki import settings, logger
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
from pathlib import Path
from contextlib import suppress

FileName: TypeAlias = Union[str, bytes, PathLike]


@define
class Message:
  content: Optional[str] = None
  embed: Optional[Embed] = None
  embeds: Optional[List[Embed]] = None

  def to_dict(self):
    """
    Generate kwargs for ctx.send().

    Returns:
        dict
    """
    return _asdict(self, recurse=False)


class MessageMan:
  _templates: Dict[str, Dict[str, Any]] = {}
  _strings: Dict[str, str] = {}
  _strings_blanks: Dict[str, str] = {}
  _default: Optional[Dict[str, Any]] = None
  colors: Dict[str, int] = {}


  def __init__(self, template_file: Optional[FileName] = None):
    if template_file:
      self.load(template_file)


  @classmethod
  def from_file(cls, template_file: FileName):
    return cls(template_file)


  @classmethod
  def from_dir(cls, template_dir: FileName):
    base = cls()
    base.load_dir(template_dir)
    return base


  def load_dir(self, template_dir: FileName, modify: bool = False):
    """
    Load or reload message template files in a given directory.

    Args:
        template_dir: Path to directory containing template files.
        modify: Whether to modify existing templates or load anew
    """
    p = Path(template_dir)

    default_template_path = None
    if not modify:
      if (p / "defaults.yaml").exists():
        default_template_path = p / "defaults.yaml"
      elif (p / "messages.yaml").exists():
        default_template_path = p / "messages.yaml"

      if default_template_path:
        self.load(str(default_template_path))
      else:
        self._clear()

    for template_path in [f for f in p.rglob("*") if f.suffix.lower() in {".yaml", ".yml"}]:
      if default_template_path and template_path == default_template_path:
        continue
      try:
        self.modify(str(template_path))
      except OSError:
        logger.exception(f"Unable to open template file '{str(template_path)}'")
        continue
      except Exception:
        logger.exception(f"Cannot load template file '{str(template_path)}'")
        continue


  def load(self, template_file: FileName):
    """
    Load or reload a message templates file (YAML).

    Args:
        template_file: Name of YAML template file.
    """
    self._clear()

    templates = self._load(template_file)
    for k, v in templates.items():
      if isinstance(v, str):
        self._strings |= {k: v}
        self._strings_blanks |= {k: ""}
      else:
        self._templates |= {k: v}

    if "default" in templates.keys():
      self._default = templates["default"]
    if "_colors" in templates.keys():
      self.colors = templates["_colors"]

    logger.debug(
      f"Loaded {len(self._templates)} message templates from file: '{template_file}'"
    )
    logger.debug(
      f"Loaded {len(self._strings)} string templates from file: '{template_file}'"
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
    for k, v in templates.items():
      if isinstance(v, str):
        self._strings |= {k: v}
        self._strings_blanks |= {k: ""}
      else:
        self._templates |= {k: v}

    if "default" in templates.keys():
      self._default = self._load_template("default")

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
    use_string_templates: List[str] = [],
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
        use_string_templates: String templates to be shown, otherwise blanked

    Kwargs:
        template_kwargs: Template overrides

    Returns:
        Message: Message object to be passed to send()

    Raises:
        ValueError: Message template 'name' does not exist in loaded file.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")
    
    string_data  = self._strings_blanks.copy()
    string_data |= {k: v for k, v in self._strings.items() if k in use_string_templates}

    data = data or {}
    if user:
      data |= user_data(user)
    if target_user:
      data |= target_user_data(target_user)

    loaded_templates = self._load_template(template_name)
    if not isinstance(loaded_templates, list):
      loaded_templates = [loaded_templates]

    content   = None
    embeds    = []
    for loaded in loaded_templates:
      if isinstance(loaded.get("base_template"), str):
        default = self._load_template(loaded["base_template"], copy=True)
      else:
        default = self._load_template("default", copy=True)

      template  = default | loaded
      template  = _assign_data(template, string_data)
      template  = _assign_data(template, data, escapes=escape_data_values)
      template |= template_kwargs

      content = content or template.get("content")
      if em := _create_embed(template, color_data=self.colors):
        embeds.append(em)

    return Message(
      content=str(content) if content else None,
      embeds=embeds
    )


  def multipage(
    self,
    template_name: str,
    pages_data: List[dict],
    base_data: Optional[dict] = None,
    user: Optional[BaseUser] = None,
    target_user: Optional[BaseUser] = None,
    escape_data_values: List[str] = [],
    use_string_templates: List[str] = [],
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
        use_string_templates: String templates to be shown, otherwise blanked

    Kwargs:
        template_kwargs: Template overrides for all pages

    Returns:
        Message: Message object to be passed to Paginator

    Raises:
        ValueError: Message template 'name' does not exist.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")

    string_data  = self._strings_blanks.copy()
    string_data |= {k: v for k, v in self._strings.items() if k in use_string_templates}

    base_data = base_data or {}
    if user:
      base_data |= user_data(user)
    if target_user:
      base_data |= target_user_data(target_user)

    loaded = self._load_template(template_name)
    if isinstance(loaded.get("base_template"), str):
      default = self._load_template(loaded["base_template"], copy=True)
    else:
      default = self._load_template("default", copy=True)

    base_template = default | loaded
    base_template = _assign_data(base_template, string_data)
    base_template = _assign_data(base_template, base_data, escapes=escape_data_values)

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
      if em := _create_embed(page_template, color_data=self.colors):
        embeds.append(em)

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
    use_string_templates: List[str] = [],
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
        use_string_templates: String templates to be shown, otherwise blanked

    Kwargs:
        template_kwargs: Template overrides for all pages

    Returns:
        Message: Message object to be passed to Paginator

    Raises:
        ValueError: Message template 'name' does not exist.
    """
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")

    string_data  = self._strings_blanks.copy()
    string_data |= {k: v for k, v in self._strings.items() if k in use_string_templates}

    base_data = base_data or {}
    if user:
      base_data |= user_data(user)
    if target_user:
      base_data |= target_user_data(target_user)

    loaded = self._load_template(template_name)
    if isinstance(loaded.get("base_template"), str):
      default = self._load_template(loaded["base_template"], copy=True)
    else:
      default = self._load_template("default", copy=True)

    base_template  = default | loaded
    base_template  = _assign_data(base_template, string_data)
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
      if em := _create_embed(page_template, color_data=self.colors):
        embeds.append(em)

      cursor += fields_per_page
      page += 1

    return Message(
      content=str(content) if content else None,
      embeds=embeds
    )


  def multiline(
    self,
    template_name: str,
    lines_data: Dict[str, List[Dict[str, Any]]],
    base_data: Optional[dict] = None,
    user: Optional[BaseUser] = None,
    target_user: Optional[BaseUser] = None,
    escape_data_values: List[str] = [],
    use_string_templates: List[str] = [],
    **template_kwargs
  ):
    if template_name not in self._templates.keys():
      raise ValueError(f"Message template '{template_name}' is invalid or does not exist")

    string_data  = self._strings_blanks.copy()
    string_data |= {k: v for k, v in self._strings.items() if k in use_string_templates}

    base_data = base_data or {}
    if user:
      base_data |= user_data(user)
    if target_user:
      base_data |= target_user_data(target_user)

    loaded_templates = self._load_template(template_name)
    if not isinstance(loaded_templates, list):
      loaded_templates = [loaded_templates]

    content   = None
    embeds    = []
    for loaded in loaded_templates:
      if isinstance(loaded.get("base_template"), str):
        default = self._load_template(loaded["base_template"], copy=True)
      else:
        default = self._load_template("default", copy=True)

      template  = default | loaded
      template  = _assign_data(template, string_data)
      template  = _assign_data(template, base_data, escapes=escape_data_values)

      # message_template = {
      #   ...,
      #   multiline: [
      #     {id: m_1, value: "this string"},
      #     {id: m_2, value: "this_string"}
      #   ]
      # }

      # lines_data = {
      #   m_1: [
      #     {a: 1, b: 1},
      #     {a: 2, b: 3}
      #   ],
      #   m_2: ...
      # }

      multiline_settings = template.get("multiline")
      multiline_assigned = {m["id"]: "" for m in multiline_settings if m.get("id")}
      for m in multiline_settings:
        m_id = m.get("id")
        m_value = m.get("value")
        if m_id not in multiline_assigned.keys():
          continue
        if m_id not in lines_data.keys():
          continue
        if not isinstance(m_value, str):
          continue

        multiline_assigns = [
          _assign_string(_assign_string(m_value, string_data), base_data | line_data, escapes=escape_data_values)
          for line_data in lines_data[m_id]
        ]
        if len(multiline_assigns) > 0:
          if m.get("inline") and m.get("separator"):
            multiline_assigned[m_id] = m["separator"].join(multiline_assigns)
          else:
            multiline_assigned[m_id] = (" " if m.get("inline") else "\n").join(multiline_assigns)
        elif value_ifnone := m.get("value_ifnone"):
            multiline_assigned[m_id] = value_ifnone

      template  = _assign_data(template, multiline_assigned)
      template |= template_kwargs

      content = content or template.get("content")
      if em := _create_embed(template, color_data=self.colors):
        embeds.append(em)

    return Message(
      content=str(content) if content else None,
      embeds=embeds
    )


  def _load(self, template_file: FileName):
    with open(template_file, encoding="UTF-8") as f:
      source_templates: Dict[str, Any] = safe_load(f)
    if not isinstance(source_templates, Dict):
      raise ValueError(f"Message template file '{template_file}' is invalid")

    templates = {}
    namespace = ""
    if isinstance(source_templates.get("_namespace"), str):
      namespace = source_templates["_namespace"] + "_"
    if isinstance(source_templates.get("_colors"), Dict):
      templates["_colors"] = source_templates["_colors"]
    if len(namespace) > 1 and "_" in source_templates.keys():
      templates[namespace.removesuffix("_")] = source_templates["_"]
    templates |= {namespace + k: v for k, v in source_templates.items() if not k.startswith("_")}

    return templates


  def _load_template(self, name: str, copy: bool = False):
    get = self._templates.get(name)
    if copy:
      return deepcopy(get) if get else {}
    else:
      return get or {}


  def _clear(self):
    self._templates = {}
    self._strings = {}
    self._strings_blanks = {}
    self._default = None


# =============================================================================


BASE_MESSAGES_YAML = settings.mitsuki.messages_default
CUSTOM_MESSAGES_YAML = settings.mitsuki.messages
BASE_MESSAGES_DIR = settings.mitsuki.messages_dir
CUSTOM_MESSAGES_DIR = settings.mitsuki.messages_custom_dir


def _defined(s: Optional[str]):
  return s is not None and len(s.strip()) > 0


def load_templates(raise_on_error: bool = False):
  new_root = MessageMan()

  if _defined(BASE_MESSAGES_DIR):
    # messages_dir specified
    new_root.load_dir(BASE_MESSAGES_DIR)
    if _defined(CUSTOM_MESSAGES_DIR):
      new_root.load_dir(CUSTOM_MESSAGES_DIR, modify=True)

  elif _defined(BASE_MESSAGES_YAML):
    # messages_dir unspecified, messages_default specified
    new_root.load(BASE_MESSAGES_YAML)
    if _defined(CUSTOM_MESSAGES_YAML):
      new_root.modify(CUSTOM_MESSAGES_YAML)

  elif _defined(CUSTOM_MESSAGES_YAML):
    # messages_dir and messages_default unspecified, messages specified
    new_root.load(CUSTOM_MESSAGES_YAML)

  else:
    logger.error("Message template settings not set")
    if raise_on_error:
      raise ValueError("No path to message templates specified in settings.yaml")

  return new_root


templates = load_templates()


def set_templates(template: MessageMan):
  global templates
  templates = template


# =============================================================================


def load_message(
  template_name: str,
  data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  escape_data_values: List[str] = [],
  use_string_templates: List[str] = [],
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
      use_string_templates: String templates to be shown, otherwise blanked

  Kwargs:
      template_kwargs: Template overrides

  Returns:
      Message: Message object to be passed to send()

  Raises:
      ValueError: Message template 'name' does not exist in loaded file.
  """
  return templates.message(
    template_name=template_name,
    data=data,
    user=user,
    target_user=target_user,
    escape_data_values=escape_data_values,
    use_string_templates=use_string_templates,
    **template_kwargs
  )


def load_multipage(
  template_name: str,
  pages_data: List[dict],
  base_data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  escape_data_values: List[str] = [],
  use_string_templates: List[str] = [],
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
      use_string_templates: String templates to be shown, otherwise blanked

  Kwargs:
      template_kwargs: Template overrides for all pages

  Returns:
      Message: Message object to be passed to Paginator

  Raises:
      ValueError: Message template 'name' does not exist.
  """
  return templates.multipage(
    template_name=template_name,
    pages_data=pages_data,
    base_data=base_data,
    user=user,
    target_user=target_user,
    escape_data_values=escape_data_values,
    use_string_templates=use_string_templates,
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
  use_string_templates: List[str] = [],
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
      use_string_templates: String templates to be shown, otherwise blanked

  Kwargs:
      template_kwargs: Template overrides for all pages

  Returns:
      Message: Message object to be passed to Paginator

  Raises:
      ValueError: Message template 'name' does not exist.
  """
  return templates.multifield(
    template_name=template_name,
    fields_data=fields_data,
    base_data=base_data,
    user=user,
    target_user=target_user,
    fields_per_page=fields_per_page,
    escape_data_values=escape_data_values,
    use_string_templates=use_string_templates,
    **template_kwargs
  )


def load_multiline(
  template_name: str,
  lines_data: Dict[str, List[Dict[str, Any]]],
  base_data: Optional[dict] = None,
  user: Optional[BaseUser] = None,
  target_user: Optional[BaseUser] = None,
  escape_data_values: List[str] = [],
  use_string_templates: List[str] = [],
  **template_kwargs
):
  return templates.multiline(
    template_name=template_name,
    lines_data=lines_data,
    base_data=base_data,
    user=user,
    target_user=target_user,
    escape_data_values=escape_data_values,
    use_string_templates=use_string_templates,
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
  template: Dict[str, Any],
  data: Optional[Dict[str, Any]] = None,
  escapes: List[str] = []
):
  if data is None:
    return template
  if len(data) <= 0:
    return template
  assigned = deepcopy(template)

  DEPTH = 3

  # Process data:
  # - Escape values in the escapes key list
  # - Convert boolean values to yes/no emoji
  processed_data = data.copy()
  for key, value in data.items():
    if key in escapes and isinstance(value, str):
      processed_data[key] = escape_text(value)
    if isinstance(value, bool):
      processed_data[key] = str(settings.emoji.yes) if value else str(settings.emoji.no)

  # Recursive assignment of data to the template in ${} placeholders
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
        assigned_value = Template(value).safe_substitute(**processed_data).strip()
      else:
        assigned_value = value

      if is_dict:
        assigned_temp[key] = assigned_value
      elif is_list:
        assigned_temp.append(assigned_value)

    return assigned_temp

  assigned = _recurse_assign(assigned)
  return assigned


def _assign_string(string: str, data: Dict[str, Any], escapes: List[str] = []):
  escaped_data = data.copy()
  for key, value in data.items():
    if key in escapes and isinstance(value, str):
      escaped_data[key] = escape_text(value)

  return Template(string).safe_substitute(**escaped_data).strip()


def _create_embed(template: Dict[str, Any], color_data: Optional[Dict[str, int]] = None):
  title = template.get("title")
  description = template.get("description")

  color_get = template.get("color")
  color = None
  if isinstance(color_get, int):
    color = color_get
  elif isinstance(color_get, str) and not color_get.strip().startswith("$"):
    if color_get.isnumeric():
      color = int(color_get)
    elif color_data:
      color = color_data.get(color_get.strip())
    if color is None:
      with suppress(ValueError):
        color = process_color(color_get.strip())

  url = _valid_url_or_none(template.get("url"))

  fields_get = template.get("fields") or []
  fields = []
  for field_get in fields_get:
    if isinstance(field_get, Dict):
      name = field_get.get("name") or ""
      value = field_get.get("value") or ""
      if len(name.strip()) <= 0 or len(value.strip()) <= 0:
        continue
      fields.append(EmbedField(
        name=name.strip(),
        value=value.strip(),
        inline=bool(field_get.get("inline"))
      ))

  author = None
  author_get = template.get("author")
  if author_get and len(author_get.get("name").strip() or "") > 0:
    author = EmbedAuthor(
      name=author_get["name"],
      url=_valid_url_or_none(author_get.get("url")),
      icon_url=_valid_url_or_none(author_get.get("icon_url"))
    )

  thumbnail = None
  if thumbnail_url := _valid_url_or_none(template.get("thumbnail")):
    thumbnail = EmbedAttachment(url=thumbnail_url)

  images = []
  if image_url := _valid_url_or_none(template.get("image")):
    images = [EmbedAttachment(url=image_url)]

  footer = None
  footer_get = template.get("footer")
  if footer_get and len(footer_get.get("text").strip() or "") > 0:
    footer = EmbedFooter(
      text=footer_get["text"].strip(),
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
  ) if title or description or fields or author or images or footer else None


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
