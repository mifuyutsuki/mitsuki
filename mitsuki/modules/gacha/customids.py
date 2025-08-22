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


VIEW = CustomID("gacha_view")
"""View a card. (id: Card ID; select)"""

CARDS = CustomID("gacha_cards")
"""View a user's card collection in list view. (id: Target User)"""

GALLERY = CustomID("gacha_gallery")
"""View a user's card collection in deck view. (id: Target User)"""

PROFILE = CustomID("gacha_profile")
"""View a user's gacha profile. (id: Target User)"""

ROLL = CustomID("gacha_roll")
"""Roll a card. Caller must be the same as the user in ID. (id: User)"""

CARDS_ADMIN = CustomID("gacha_cards_admin")
"""View all cards in deck as admin. (no args)"""

VIEW_ADMIN = CustomID("gacha_view_admin")
"""View a card as admin. (id: Card ID)"""

RELOAD = CustomID("gacha_reload")
"""Reload the current roster. (no args; confirm)"""