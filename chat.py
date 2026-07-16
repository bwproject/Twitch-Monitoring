# chat.py

import os
import json
import time
import logging
import asyncio

from pathlib import Path

from dotenv import load_dotenv
from twitchio.ext import commands


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "chat_config.json"
STREAMERS_FILE = BASE_DIR / "streamers.json"

GLOBAL_COMMANDS_FILE = BASE_DIR / "global_commands.json"

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "chat.log"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s",

    handlers=[

        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),

        logging.StreamHandler()

    ]

)

logger = logging.getLogger(
    "twitch_chat"
)


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

            return json.load(f)


    except Exception as e:

        logger.error(
            f"{file.name}: {e}"
        )

        return {}



# ============================================================
# CONFIG
# ============================================================

CONFIG = load_json(
    CONFIG_FILE
)


BOT_NICK = CONFIG.get(
    "bot_nick"
)

OAUTH = CONFIG.get(
    "oauth"
)

PREFIX = CONFIG.get(
    "prefix",
    "!"
)


# ============================================================
# STREAMERS
# ============================================================

def load_channels():

    data = load_json(
        STREAMERS_FILE
    )


    result = []


    if isinstance(
        data,
        list
    ):

        for item in data:

            if isinstance(
                item,
                dict
            ):

                name = item.get(
                    "name"
                )

                if name:

                    result.append(
                        name.lower()
                    )


    return result



# ============================================================
# COMMANDS
# ============================================================

def load_commands(streamer=None):


    commands = {}


    global_commands = load_json(
        GLOBAL_COMMANDS_FILE
    )


    if isinstance(
        global_commands,
        dict
    ):

        commands.update(
            global_commands
        )



    if streamer:

        file = BASE_DIR / f"{streamer}_commands.json"


        local = load_json(
            file
        )


        if isinstance(
            local,
            dict
        ):

            commands.update(
                local
            )


    return commands




# ============================================================
# TWITCH BOT
# ============================================================

class TwitchChatBot(
    commands.Bot
):


    def __init__(self):

        super().__init__(

            token=OAUTH,

            prefix=PREFIX,

            initial_channels=load_channels()

        )


        self.commands_cache = {}



    async def event_ready(
        self
    ):

        logger.info(
            f"CHAT BOT ONLINE: {self.nick}"
        )


        logger.info(
            f"CHANNELS: {load_channels()}"
        )



    async def event_joined_channel(
        self,
        channel
    ):

        name = channel.name.lower()


        self.commands_cache[name] = load_commands(
            name
        )


        logger.info(
            f"JOINED: {name}"
        )



    async def event_message(
        self,
        message
    ):


        if message.echo:

            return



        if not message.content.startswith(
            PREFIX
        ):

            return



        channel = message.channel.name.lower()


        command = message.content.split()[0].lower()



        if channel not in self.commands_cache:

            self.commands_cache[channel] = load_commands(
                channel
            )



        commands_list = self.commands_cache[channel]



        data = commands_list.get(
            command
        )



        if not data:

            return



        text = ""



        if isinstance(
            data,
            str
        ):

            text = data


        elif isinstance(
            data,
            dict
        ):

            text = data.get(
                "text",
                ""
            )



        if text:

            await message.channel.send(
                text
            )



# ============================================================
# START
# ============================================================

async def main():

    bot = TwitchChatBot()

    await bot.start()



if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "CHAT BOT STOPPED"
        )
