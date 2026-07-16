# command_loader.py

import json
import logging

from pathlib import Path


logger = logging.getLogger(
    "twitch_chat"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

GLOBAL_COMMANDS_FILE = BASE_DIR / "global_commands.json"



# ============================================================
# CACHE
# ============================================================

_cache = {}

_mtimes = {}



# ============================================================
# LOAD JSON
# ============================================================

def load_json(file):

    if not file.exists():

        return {}


    try:

        with file.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        if isinstance(
            data,
            dict
        ):

            return data


    except Exception as e:

        logger.error(
            f"COMMAND LOAD ERROR {file.name}: {e}"
        )


    return {}



# ============================================================
# FILE CHECK
# ============================================================

def file_changed(file):


    if not file.exists():

        return False



    mtime = file.stat().st_mtime


    old = _mtimes.get(
        str(file)
    )


    if old != mtime:

        _mtimes[str(file)] = mtime

        return True



    return False



# ============================================================
# LOAD STREAMER COMMANDS
# ============================================================

def load_commands(
    streamer
):


    streamer = streamer.lower()



    global_file = GLOBAL_COMMANDS_FILE


    local_file = BASE_DIR / (
        f"{streamer}_commands.json"
    )



    need_reload = (

        streamer not in _cache

        or

        file_changed(global_file)

        or

        file_changed(local_file)

    )



    if not need_reload:

        return _cache.get(
            streamer,
            {}
        )



    commands = {}



    # ========================================
    # GLOBAL
    # ========================================

    global_commands = load_json(
        global_file
    )


    if isinstance(
        global_commands,
        dict
    ):

        commands.update(
            global_commands
        )



    # ========================================
    # STREAMER
    # ========================================

    local_commands = load_json(
        local_file
    )


    if isinstance(
        local_commands,
        dict
    ):

        commands.update(
            local_commands
        )



    _cache[streamer] = commands



    logger.info(
        f"COMMANDS LOADED {streamer}: {list(commands.keys())}"
    )


    return commands



# ============================================================
# GET COMMAND
# ============================================================

def get_command(
    streamer,
    command
):


    commands = load_commands(
        streamer
    )


    return commands.get(
        command.lower()
    )



# ============================================================
# GET ALL
# ============================================================

def get_all_commands(
    streamer
):


    return load_commands(
        streamer
    )
    
def get_all_commands(streamer):

    commands = load_commands(
        streamer
    )

    logger.info(
        f"CHECK COMMANDS {streamer}: {list(commands.keys())}"
    )

    return commands
