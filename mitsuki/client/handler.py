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
import interactions.api.events as events
import interactions.client.errors as errors

import os
import sys
from functools import partial
from typing import Union
from enum import StrEnum

from mitsuki.logger import logger
from mitsuki.lib.errors import MitsukiSoftException
from mitsuki.lib.messages import load_message
from mitsuki.lib.userdata import db_migrate
from mitsuki.lib.emoji import init_emoji
from mitsuki import APP_PATH, init_event


class Templates(StrEnum):
  ERROR_COOLDOWN = "error_cooldown"
  ERROR_CONCURRENCY = "error_concurrency"
  ERROR_CHECK = "error_command_perms"
  ERROR_ARGUMENT = "error_argument"
  ERROR_SERVER = "error_server"
  ERROR = "error"


def _invoker(ctx: ipy.BaseContext) -> str:
  if ctx.guild:
    return f"@{ctx.guild_id}/{ctx.channel_id}/{ctx.author_id}"
  return f"@{ctx.author_id}"


def _format_traceback(e: Exception) -> str:
  """
  Format the application error message to be sent to the Discord interaction.

  The lowest stack trace that comes from the Mitsuki application is used to generate the message.

  Example:
    ```
    mitsuki.lib.commands:send:266: DiscordError: ...
    ```

  Args:
    e: Raised exception instance
  
  Returns:
    Error message string indicating where the error occured
  """

  # Look for the Mitsuki source
  tb = e.__traceback__
  use_tb = tb
  mitsuki_tb = None
  mitsuki_path = os.path.dirname(os.path.abspath(APP_PATH))

  # dirname(abspath(APP_PATH)) is the path to mitsuki/__init__.py
  while tb is not None:
    if mitsuki_path in tb.tb_frame.f_code.co_filename:
      mitsuki_tb = tb
    use_tb = mitsuki_tb or tb
    tb = tb.tb_next

  if mitsuki_tb:
    e_path = (
      use_tb.tb_frame.f_code.co_filename  # /path/to/err_code.py
      .replace(mitsuki_path, "mitsuki")   # Module path -> `mitsuki`
      .replace("\\", ".")                 # Directory (Windows) -> `.`
      .replace("/", ".")                  # Directory (POSIX/macOS) -> `.`
      .rsplit(".", maxsplit=1)[0]         # .py ->
      .replace(".__init__", "")           # /__init__.py ->
    ) if mitsuki_tb else ""
    e_coname = use_tb.tb_frame.f_code.co_name
    e_lineno = use_tb.tb_lineno
    error_repr = (
      f"{e_path}:{e_coname}:{e_lineno}: "
      f"{type(e).__name__}: "
      f"{str(e)}"
    )
  else:
    error_repr = (
      f"{type(e).__name__}: "
      f"{str(e)}"
    ) if use_tb else repr(e)
  return error_repr


class ClientHandlerMixin:
  @ipy.listen(events.Startup)
  async def on_startup(self, event: ipy.events.Startup):
    await db_migrate()
    await init_emoji(event.bot)
    init_event.set()


  @ipy.listen(events.Ready)
  async def on_ready(self):
    print(f"Serving as {self.user.tag} ({self.user.id}) @ {len(self.guilds)} guild(s)")


  @ipy.listen(events.CommandCompletion)
  async def on_command_completion(self, event: events.CommandCompletion) -> None:
    ctx = event.ctx

    if len(ctx.kwargs) > 0:
      kwargs = {k: str(v) for k, v in ctx.kwargs.items()}
      self.logger.info(f"{_invoker(ctx)}: Command /{ctx.invoke_target} {kwargs}")
    else:
      self.logger.info(f"{_invoker(ctx)}: Command /{ctx.invoke_target}")


  @ipy.listen(events.ComponentCompletion)
  async def on_component_completion(self, event: events.ComponentCompletion) -> None:
    ctx = event.ctx

    if len(ctx.values) > 0:
      self.logger.info(f"{_invoker(ctx)}: Component {ctx.custom_id} {event.ctx.values}")
    else:
      self.logger.info(f"{_invoker(ctx)}: Component {ctx.custom_id}")


  @ipy.listen(events.AutocompleteCompletion)
  async def on_autocomplete_completion(self, event: events.AutocompleteCompletion) -> None:
    ctx = event.ctx

    self.logger.info(f"{_invoker(ctx)}: Autocomplete /{ctx.invoke_target} '{ctx.input_text}'")


  @ipy.listen(events.ModalCompletion)
  async def on_modal_completion(self, event: events.ModalCompletion) -> None:
    ctx = event.ctx

    self.logger.info(f"{_invoker(ctx)}: Modal {ctx.custom_id} {event.ctx.responses}")


  @ipy.listen(events.CommandError, disable_default_listeners=True)
  async def on_command_error(self, event: events.CommandError) -> None:
    await self.error_handler(event)


  @ipy.listen(events.ComponentError, disable_default_listeners=True)
  async def on_component_error(self, event: events.ComponentError) -> None:
    await self.error_handler(event)


  @ipy.listen(events.ModalError, disable_default_listeners=True)
  async def on_modal_error(self, event: events.ModalError) -> None:
    await self.error_handler(event)


  async def error_handler(self, event: Union[events.CommandError, events.ComponentError, events.ModalError]) -> None:
    # default ephemeral to true unless it's an unknown exception
    ephemeral = True
    ctx_load_message = partial(load_message, user=event.ctx.author)

    if isinstance(event.error, MitsukiSoftException):
      ephemeral = event.error.EPHEMERAL
      message = ctx_load_message(event.error.TEMPLATE, data=event.error.data)

    elif isinstance(event.error, errors.CommandOnCooldown):
      cooldown_seconds = int(event.error.cooldown.get_cooldown_time())
      message = ctx_load_message(Templates.ERROR_COOLDOWN, data={"cooldown_seconds": cooldown_seconds})

    elif isinstance(event.error, errors.MaxConcurrencyReached):
      message = ctx_load_message(Templates.ERROR_CONCURRENCY)

    elif isinstance(event.error, errors.CommandCheckFailure):
      message = ctx_load_message(Templates.ERROR_CHECK)

    elif isinstance(event.error, errors.BadArgument):
      message = ctx_load_message(Templates.ERROR_ARGUMENT, data={"message": str(event.error)})

    elif isinstance(event.error, errors.HTTPException) and (
      isinstance(event.error.code, int) and (500 <= event.error.code < 600)
    ):
      error_repr = str(event.error)
      self.logger.exception(error_repr, exc_info=(type(event.error), event.error, event.error.__traceback__))
      message = ctx_load_message(Templates.ERROR_SERVER, data={"error_repr": error_repr})
      ephemeral = False

    else:
      error_repr = _format_traceback(event.error)
      self.logger.exception(error_repr, exc_info=(type(event.error), event.error, event.error.__traceback__))
      message = ctx_load_message(Templates.ERROR, data={"error_repr": error_repr})
      ephemeral = False

    if isinstance(event.ctx, ipy.InteractionContext):
      await event.ctx.send(**message.to_dict(), components=[], ephemeral=ephemeral)