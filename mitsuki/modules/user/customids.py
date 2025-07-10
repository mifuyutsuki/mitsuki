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


USER_INFO = CustomID("user_info")
"""View user information. (id: User ID)"""

USER_INFO_GLOBAL = CustomID("user_info|global")
"""View user information, using this user's main profile. (id: User ID)"""

USER_INFO_SERVER = CustomID("user_info|server")
"""View user information, using this user's server profile. (id: User ID)"""

USER_AVATAR = CustomID("user_avatar")
"""View avatar of a user. (id: User ID)"""

USER_AVATAR_GLOBAL = CustomID("user_avatar|global")
"""View main avatar of a user. (id: User ID)"""

USER_AVATAR_SERVER = CustomID("user_avatar|server")
"""View server avatar of a user. (id: User ID)"""