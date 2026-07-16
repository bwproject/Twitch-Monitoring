# chat.py

import json
import logging
import asyncio

from pathlib import Path

from dotenv import load_dotenv
from twitchio.ext import commands

try:
    from bot3.command_loader import (
        get_all_commands
    )

except ImportError:
    from command_loader import (
        get_all_commands
    )


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "chat_config.json"

STREAMERS_FILE = BASE_DIR / "streamers.json"

LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(
    exist_ok=True
)

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
# JSON
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
# CHANNELS
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


            if not isinstance(
                item,
                dict
            ):

                continue


            name = item.get(
                "name"
            )


            if name:

                result.append(
                    name.lower()
                )


    return result



# ============================================================
# TWITCH CHAT BOT
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
            f"CHAT ONLINE: {self.nick}"
        )


        logger.info(
            f"CHANNELS: {load_channels()}"
        )



    async def event_joined_channel(
        self,
        channel
    ):

        name = channel.name.lower()


        self.commands_cache[name] = get_all_commands(
            name
        )


        logger.info(
            f"JOINED {name}"
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



        # обновляем команды

        commands_list = get_all_commands(
            channel
        )



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

    if not BOT_NICK or not OAUTH:

        logger.error(
            "CHAT CONFIG ERROR"
        )

        return


    bot = TwitchChatBot()


    await bot.start()



if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )


    except KeyboardInterrupt:

        logger.info(
            "CHAT STOPPED"
        )