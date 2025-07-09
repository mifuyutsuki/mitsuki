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


USER_INFO = CustomID("info_user")
"""View user information. (id: User ID)"""

USER_AVATAR = CustomID("info_avatar")
"""View avatar of a user. (id: User ID)"""

USER_AVATAR_GLOBAL = CustomID("info_avatar|global")
"""View global avatar of a user. (id: User ID)"""

USER_AVATAR_SERVER = CustomID("info_avatar|server")
"""View server avatar of a user. (id: User ID)"""