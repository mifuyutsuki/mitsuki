import interactions as ipy
from yaml import safe_load
from typing import Optional
from string import Template


class Messages(dict):
  pass
    
messages: Optional[Messages] = None


def load(source_file: str):
  global messages
  with open(source_file, encoding="UTF-8") as f:
    messages = safe_load(f)


def generate(message_name: str, format: Optional[dict] = None, **kwargs):
  global messages

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

  # Assign format fields e.g. ${username}
  message_data = _assign_format(message_data, format)
  
  # -----------------------------------------------------------------
  # Handle keys

  title       = message_data.get("title")
  url         = message_data.get("url")
  description = message_data.get("description")
  color       = message_data.get("color")
  
  _author_data = message_data.get("author")
  author = None
  if isinstance(_author_data, dict):
    author = ipy.EmbedAuthor(
      name=_author_data.get("name"),
      url=_author_data.get("url"),
      icon_url=_author_data.get("icon_url")
    )

  _thumbnail_data = message_data.get("thumbnail")
  thumbnail = None
  if isinstance(_thumbnail_data, str):
    if len(_thumbnail_data) > 0:
      thumbnail = ipy.EmbedAttachment(url=_thumbnail_data)
    
  _image_data = message_data.get("image")
  image = None
  if isinstance(_image_data, str):
    if len(_image_data) > 0:
      image = ipy.EmbedAttachment(url=_image_data)
  
  _footer_data = message_data.get("footer")
  footer = None
  if isinstance(_footer_data, dict):
    footer = ipy.EmbedFooter(
      text=_footer_data.get("text"),
      icon_url=_footer_data.get("icon_url")
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
    images=[image],
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