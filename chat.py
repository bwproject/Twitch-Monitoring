# chat.py

import json
import logging
import asyncio

from pathlib import Path

from dotenv import load_dotenv
from twitchio.ext import commands


try:
    from bot3.command_loader import get_all_commands
except ImportError:
    from command_loader import get_all_commands


load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent


def _resolve(*names):

    for base in (BASE_DIR, BASE_DIR.parent):

        path = base.joinpath(*names)

        if path.exists():

            return path

    return BASE_DIR.joinpath(*names)


CONFIG_FILE = _resolve("chat_config.json")
STREAMERS_FILE = _resolve("streamers.json")

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
# JSON
# ============================================================

def load_json(file):

    if not file.exists():

        logger.warning(
            f"FILE NOT FOUND: {file.name}"
        )

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

CLIENT_ID = CONFIG.get(
    "client_id"
)

CLIENT_SECRET = CONFIG.get(
    "client_secret"
)

BOT_ID = CONFIG.get(
    "bot_id"
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

        channels = load_channels()


        logger.info(
            f"Подготовка подключения к каналам: {channels}"
        )


        super().__init__(

            token=OAUTH,

            client_id=CLIENT_ID,

            client_secret=CLIENT_SECRET,

            bot_id=BOT_ID,

            prefix=PREFIX,

            initial_channels=channels

        )


        self.bot_nick = BOT_NICK

        self.commands_cache = {}



    # ========================================================
    # READY
    # ========================================================

    async def event_ready(
        self
    ):

        logger.info(
            "✅ Успешная авторизация Twitch"
        )


        logger.info(
            f"BOT: {self.bot_nick}"
        )


        logger.info(
            f"Подключен к стримерам: {load_channels()}"
        )



    # ========================================================
    # JOIN
    # ========================================================

    async def event_joined_channel(
        self,
        channel
    ):

        name = channel.name.lower()


        self.commands_cache[name] = get_all_commands(
            name
        )


        logger.info(
            f"✅ Подключен к чату стримера: {name}"
        )


        logger.info(
            f"Команды: {list(self.commands_cache[name].keys())}"
        )



    # ========================================================
    # MESSAGE
    # ========================================================

    async def event_message(
        self,
        message
    ):


        if message.echo:

            return



        content = message.content.strip()



        if not content.startswith(
            PREFIX
        ):

            return



        channel = message.channel.name.lower()


        command = content.split()[0].lower()



        logger.info(
            f"Получена команда {command} "
            f"в {channel} "
            f"от {message.author.name}"
        )



        commands_list = get_all_commands(
            channel
        )


        logger.info(
            f"Доступные команды {channel}: {list(commands_list.keys())}"
        )



        data = commands_list.get(
            command
        )



        if not data:

            logger.info(
                f"Команда не найдена: {command}"
            )

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



        if not text:

            logger.warning(
                f"Команда {command} без текста"
            )

            return



        try:


            await message.channel.send(
                text
            )


            logger.info(
                f"✅ Ответ отправлен: {command}"
            )


        except Exception as e:


            logger.error(
                f"SEND ERROR {command}: {e}"
            )



# ============================================================
# START FROM BOT3
# ============================================================

async def start_chat_bot():


    if not all([

        BOT_NICK,

        OAUTH,

        CLIENT_ID,

        CLIENT_SECRET,

        BOT_ID

    ]):


        logger.error(
            "CHAT CONFIG ERROR"
        )

        return



    logger.info(
        "🚀 Запуск Twitch Chat Bot..."
    )


    bot = TwitchChatBot()


    await bot.start()



# ============================================================
# STANDALONE
# ============================================================

async def main():

    await start_chat_bot()



if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "CHAT STOPPED"
        )