# Mitsuki

![](https://img.shields.io/badge/Mitsuki-4.3.0-blue)
![](https://img.shields.io/badge/Python-3.12-blue?logo=Python)
![](https://img.shields.io/github/license/mifuyutsuki/mitsuki)
![](https://img.shields.io/github/last-commit/mifuyutsuki/mitsuki/dev?label=last%20commit)

Created for the anime community **Comfy Camp Club** (CCC), Mitsuki is a fun Discord bot built in **interactions.py** with several fun and utility commands, including some which are tailor-made for the community. Features include...

* Club-exclusive card-collecting "gacha" game
* Queued message scheduler with Schedule
* Search already posted messages in a given Schedule
* In-bot configurable status messages with Presencer
* Current server info, including emoji and sticker list
* User info, including avatar and banner viewer

# Commands

* ☀️ **Available**: Available to use, typically only in servers e.g. `schedule`.
  * ☀️ **Exclusive**: Available to use exclusively in Exclusive Guild (Comfy Camp Club).
  * ☀️ **System**: Available to use exclusively in System Guild e.g. bot-wide settings.
* 🔬 **Experimental**: In testing phase, only available in System Guild.
* 📝 **Planning**: Planned in the future.

| Command | Availability | Description |
| --- | --- | --- |
| `gacha` | ☀️ Exclusive | An exclusive CCC-themed card collection game |
| `schedule` | ☀️ Available | Routine message scheduler, developed for Daily Questions |
| `server` | ☀️ Available | Server information, including server emoji and sticker details |
| `user` | ☀️ Available | User information, including avatar and banner information |
| `system` | ☀️ System | Bot information and configuration |
| `convert` | 📝 Planning | Convert a unit to another, e.g. meters to miles |
| `anilist` | 📝 Planning | View anime, manga, and characters via [AniList](https://anilist.co) |
| `animethemes` | 📝 Planning | View anime theme songs (OP, ED, etc.) via [AnimeThemes](https://animethemes.moe) |

# Setup

Requires **Python 3.12** or later. In production, Python 3.12 on Linux is used. To manage multiple Python versions in a single machine, we recommend [`pyenv`](https://github.com/pyenv/pyenv/).

Make sure `git` (unless downloading directly from GitHub) and `python3` (3.12 or later) are installed, and you have set up the bot and its **bot token** through [Discord Developer Portal](https://discord.com/developers/applications). You may want to prepare a "system" Discord server (internally known as System Guild) from which you can run `system` commands.

## Steps

1.  Clone this repository, either via GitHub or using `git clone`:

    ```bash
    git clone https://github.com/mifuyutsuki/mitsuki.git
    cd mitsuki
    ```

2.  Create and activate the virtual environment to isolate dependencies:
    ```bash
    # Python venv (use the right activate script according to your shell)
    python3 -m venv .venv
    source .venv/bin/activate

    # pyenv + pyenv-virtualenv (3.12)
    pyenv install 3.12
    pyenv local 3.12
    pyenv virtualenv 3.12 mitsuki-py3.12
    pyenv activate mitsuki-py3.12
    ```

3.  Install dependencies:
    ```bash
    # Production dependencies
    pip install -r requirements.txt

    # Development dependencies (optional) - additionally includes pytest and jurigged
    pip install -r requirements-dev.txt
    ```

4.  Create data and settings directories and files:
    ```bash
    mkdir data                                        # Directory for the SQLite database
    mkdir settings                                    # Directory for some bot settings
    cp defaults/settings.yaml settings/settings.yaml  # Customize bot settings if needed
    cp example.env .env                               # Discord bot token goes here
    ```

5.  Update the settings above using your text editor of choice:
    ```bash
    nvim .env
    nvim settings/settings.yaml
    ```

6.  Run the bot:
    ```bash
    # Production mode
    python3 run.py

    # Development mode (runs jurigged for hot code reloading)
    python3 run.py dev
    ```