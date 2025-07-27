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


SYSTEM_PRESENCES = CustomID("system_presences")
"""
View a list of bot presences in rotation. (no args)
"""

SYSTEM_PRESENCES_ADD = CustomID("system_presences_add")
"""
Add a bot presence into the rotation. (no args; modal)

Example usage
* `system_presences_add|prompt`       - Show modal
* `system_presences_add|response`     - Respond to modal
"""

SYSTEM_PRESENCES_EDIT = CustomID("system_presences_edit")
"""
Edit a bot presence in the rotation. (id: Presence ID; modal/select)

Example usage:
* `system_presences_edit:5`           - Edit presence (button)
* `system_presences_edit|select`      - Edit presence (select menu)
* `system_presences_edit|prompt:5`    - Show modal
* `system_presences_edit|response:5`  - Respond to modal
"""

SYSTEM_PRESENCES_DELETE = CustomID("system_presences_delete")
"""
Delete a bot presence out of the rotation. (id: Presence ID; confirm)

Example usage:
* `system_presences_delete|confirm:5` - Confirmation message
* `system_presences_delete:5`         - Delete
"""