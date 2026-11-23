# bot3.py

import sys
import os
import asyncio
import logging

from dotenv import load_dotenv

# Load local .env before reading any configuration.
load_dotenv()

USE_PROXY = os.getenv("USE_PROXY", "false").strip().lower() in ("1", "true", "yes", "on")

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from fastapi import FastAPI
import uvicorn


# ---------------------- PATH ----------------------

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)


# ---------------------- IMPORTS ----------------------

from admin import register_admin_handlers
from command import register_command_handlers

from chat import start_chat_bot

from twitch import (
    monitor,
    watch_streamers_file,
    register_twitch_api_handler
)

from chat import (
    start_chat_bot
)

from webapp import configure_web_app

try:
    from proxsybot import init_proxy, proxy_watcher
except ImportError:
    # Proxy integration is optional; the repository can run without it.
    async def init_proxy():
        return None

    async def proxy_watcher():
        while True:
            await asyncio.sleep(3600)


# ---------------------- ENV ----------------------

load_dotenv()


TWITCH_CLIENT_ID = os.getenv(
    "TWITCH_CLIENT_ID"
)

TWITCH_CLIENT_SECRET = os.getenv(
    "TWITCH_CLIENT_SECRET"
)

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN"
)


CHECK_INTERVAL = int(
    os.getenv(
        "CHECK_INTERVAL",
        30
    )
)

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "1047"))


# ---------------------- LOGGER ----------------------

LOG_DIR = "logs"

LOG_FILE = os.path.join(
    LOG_DIR,
    "monitor.log"
)

os.makedirs(
    LOG_DIR,
    exist_ok=True
)


logger = logging.getLogger(
    "twitch_monitor"
)

logger.setLevel(
    logging.INFO
)


formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


file_handler = logging.FileHandler(
    LOG_FILE,
    encoding="utf-8"
)

file_handler.setFormatter(
    formatter
)


console_handler = logging.StreamHandler()

console_handler.setFormatter(
    formatter
)


logger.addHandler(
    file_handler
)

logger.addHandler(
    console_handler
)



# ---------------------- TELEGRAM BOT ----------------------

async def create_bot():

    try:

        proxy = None


        if USE_PROXY:

            try:

                proxy = await init_proxy()

            except Exception as e:

                logger.error(
                    f"[PROXY INIT ERROR] {e}"
                )


        if proxy:

            try:

                session = AiohttpSession(
                    proxy=proxy
                )


                logger.info(
                    f"[PROXY] Используется: {proxy}"
                )


            except Exception as e:

                logger.error(
                    f"[PROXY ERROR] {e}"
                )

                session = AiohttpSession()


        else:

            logger.info(
                "[PROXY] Бот запущен без прокси"
            )

            session = AiohttpSession()



        return Bot(
            token=TELEGRAM_TOKEN,
            session=session
        )


    except Exception as e:

        logger.error(
            f"[BOT CREATE ERROR] {e}"
        )

        return Bot(
            token=TELEGRAM_TOKEN,
            session=AiohttpSession()
        )



# ---------------------- WEBHOOK ----------------------

async def safe_delete_webhook(bot):

    for i in range(3):

        try:

            await bot.delete_webhook(
                drop_pending_updates=True,
                request_timeout=20
            )


            logger.info(
                "Webhook удалён"
            )

            return


        except TelegramNetworkError as e:

            logger.warning(
                f"[WEBHOOK RETRY {i+1}] {e}"
            )


            await asyncio.sleep(
                3
            )


        except Exception as e:

            logger.error(
                f"[WEBHOOK ERROR] {e}"
            )

            return



# ---------------------- MAIN ----------------------

async def main():

    print(
        "BOT BW STARTED"
    )

    # Run the WebApp API in parallel with Telegram and Twitch workers.
    web_app = FastAPI(title="Twitch Monitoring API")
    configure_web_app(web_app)
    web_server = uvicorn.Server(
        uvicorn.Config(web_app, host=WEB_HOST, port=WEB_PORT, log_level="info")
    )
    web_task = asyncio.create_task(web_server.serve())
    logger.info("Web API listening on %s:%s", WEB_HOST, WEB_PORT)


    if USE_PROXY:

        asyncio.create_task(
            proxy_watcher()
        )



    # ==============================
    # TWITCH CHAT BOT
    # ==============================

    try:

        asyncio.create_task(
            start_chat_bot()
        )


        logger.info(
            "Twitch chat bot запущен"
        )


    except Exception as e:

        logger.error(
            f"TWITCH CHAT START ERROR: {e}"
        )



    # ==============================
    # TELEGRAM BOT
    # ==============================

    bot = await create_bot()


    await safe_delete_webhook(
        bot
    )


    logger.info(
        "Запускаем polling..."
    )



    dp = Dispatcher(
        storage=MemoryStorage()
    )



    # ---------------- handlers ----------------

    register_command_handlers(
        dp
    )


    register_admin_handlers(
        dp
    )


    register_twitch_api_handler(
        dp
    )



    # ---------------- watchers ----------------

    asyncio.create_task(
        watch_streamers_file(
            CHECK_INTERVAL
        )
    )



    asyncio.create_task(
        monitor(
            bot,
            TWITCH_CLIENT_ID,
            TWITCH_CLIENT_SECRET,
            CHECK_INTERVAL
        )
    )



    try:

        await dp.start_polling(
            bot
        )


    finally:

        web_server.should_exit = True
        await web_task
        await bot.session.close()


        logger.info(
            "Bot stopped"
        )



# ---------------------- START ----------------------

if __name__ == "__main__":

    asyncio.run(
        main()
    )