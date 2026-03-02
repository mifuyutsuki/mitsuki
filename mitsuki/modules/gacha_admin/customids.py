# Copyright (c) 2024-2026 Mifuyu (mifuyutsuki@proton.me)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

from mitsuki.lib.commands import CustomID


ROSTER_UPLOAD = CustomID("gacha_admin_upload|roster")
"""Upload the selected gacha roster. (args: Submitter UUID)"""

SEASON_UPLOAD = CustomID("gacha_admin_upload|season")
"""Upload the selected gacha season. (args: Submitter UUID)"""