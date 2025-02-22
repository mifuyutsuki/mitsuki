# Copyright (c) 2024-2025 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from mitsuki.lib.commands import CustomID


class CustomIDs:
  SCHEDULE_MANAGE = CustomID("schedule_manage")
  """Manage Schedules. (no args)"""

  SCHEDULE_CREATE = CustomID("schedule_create")
  """Create a Schedule. (no args; modal)"""

  SCHEDULE_VIEW = CustomID("schedule_view")
  """View a Schedule. (id: Schedule ID/key; select)"""

  CONFIGURE = CustomID("schedule_configure")
  """Configure a Schedule. (id: Schedule ID)"""

  CONFIGURE_TITLE = CustomID("schedule_configure_title")
  """Rename the title of a Schedule. (id: Schedule ID; modal)"""

  CONFIGURE_FORMAT = CustomID("schedule_configure_format")
  """Set the posting format text of a Schedule. (id: Schedule ID; modal)"""

  CONFIGURE_ACTIVE = CustomID("schedule_configure_active")
  """Activate or deactivate a Schedule. (id: Schedule ID)"""

  CONFIGURE_PIN = CustomID("schedule_configure_pin")
  """Enable or disable pinning the latest message (requires extra permissions). (id: Schedule ID)"""

  CONFIGURE_DISCOVERABLE = CustomID("schedule_configure_discoverable")
  """[FUTURE] Show or hide messages in this Schedule to publicly accessible /schedule view. (id: Schedule ID)"""

  CONFIGURE_CHANNEL = CustomID("schedule_configure_channel")
  """Set where the Schedule should be posted. (id: Schedule ID; select)"""

  CONFIGURE_ROLES = CustomID("schedule_configure_roles")
  """Set roles other than admins that can manage messages in a Schedule. (id: Schedule ID; select [multiple])"""

  CONFIGURE_ROLES_CLEAR = CustomID("schedule_configure_roles|clear")
  """Clear manager roles of a Schedule. (id: Schedule ID)"""

  # TODO: Non-daily routines
  CONFIGURE_ROUTINE = CustomID("schedule_configure_routine")
  """Set the posting time of a Schedule. (id: Schedule ID; modal)"""

  MESSAGE_ADD = CustomID("schedule_message_add")
  """Add a message to a Schedule. (id: Schedule ID/key; modal)"""

  MESSAGE_LIST = CustomID("schedule_message_list")
  """View list of all messages in a Schedule. (id: Schedule ID/key)"""

  MESSAGE_LIST_BACKLOG = CustomID("schedule_message_list_backlog")
  """View list of backlogged messages in a Schedule. (id: Schedule ID/key)"""

  MESSAGE_LIST_POSTED = CustomID("schedule_message_list_posted")
  """View list of posted messages in a Schedule. (id: Schedule ID/key)"""

  MESSAGE_VIEW = CustomID("schedule_message_view")
  """View a message in a Schedule. (id: Message ID; select)"""

  MESSAGE_EDIT = CustomID("schedule_message_edit")
  """Edit a message in a Schedule. (id: Message ID; modal)"""

  MESSAGE_DELETE = CustomID("schedule_message_delete")
  """Delete a message in a Schedule. (id: Message ID; confirm)"""

  MESSAGE_REORDER = CustomID("schedule_message_reorder")
  """Reorder a message in a queue-type Schedule. (id: Message ID; modal)"""

  MESSAGE_REORDER_FRONT = CustomID("schedule_message_reorder|front")
  """Reorder a message to front of a queue-type Schedule. (id: Message ID)"""
  
  MESSAGE_REORDER_BACK = CustomID("schedule_message_reorder|back")
  """Reorder a message to back of a queue-type Schedule. (id: Message ID)"""