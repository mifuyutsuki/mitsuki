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


SERVER_INFO = CustomID("server_info")
"""View server info. (nominal args: Guild ID)"""

SERVER_EMOJIS_STATIC = CustomID("server_emoji_static")
"""View list of static server emojis. (nominal args: Guild ID)"""

SERVER_EMOJIS_ANIMATED = CustomID("server_emoji_animated")
"""View list of animated server emojis. (nominal args: Guild ID)"""

SERVER_STICKERS = CustomID("server_stickers")
"""View gallery of server stickers. (nominal args: Guild ID)"""