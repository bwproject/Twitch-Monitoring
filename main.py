"""ProjectBW Twitch Monitoring application entry point."""
from __future__ import annotations
import asyncio, logging, os, sys
from dotenv import load_dotenv
from paths import LOG_DIR, ROOT_DIR, ensure_data_layout
load_dotenv(ROOT_DIR / ".env")
ensure_data_layout()
from runtime_config import apply_integration_settings
apply_integration_settings()
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
import uvicorn
from telegram_bot.admin import register_admin_handlers
from telegram_bot.commands import register_command_handlers
from telegram_bot.twitch_api import register_twitch_api_handler
from twitch import monitor, watch_streamers_file
from twitch.chat import start_chat_bot
from web.app import configure_web_app
from runtime_status import update as update_runtime_status
from notifications import CrossPlatformNotifier
try:
    from proxsybot import init_proxy, proxy_watcher
except ImportError:
    async def init_proxy():
        return None
    async def proxy_watcher():
        while True:
            await asyncio.sleep(3600)
USE_PROXY = os.getenv("USE_PROXY", "false").strip().lower() in ("1", "true", "yes", "on")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "1047"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("twitch_monitor")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
class ColoredConsoleFormatter(logging.Formatter):
    COLORS = {logging.DEBUG: "\033[90m", logging.INFO: "\033[32m", logging.WARNING: "\033[33m",
              logging.ERROR: "\033[31m", logging.CRITICAL: "\033[1;31m"}
    RESET = "\033[0m"
    def format(self, record):
        line = super().format(record)
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{line}{self.RESET if color else ''}"
file_handler = logging.FileHandler(LOG_DIR / "monitor.log", encoding="utf-8")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredConsoleFormatter(
    "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False
async def create_bot() -> Bot:
    proxy = None
    if USE_PROXY:
        try:
            proxy = await init_proxy()
        except Exception:
            logger.exception("[PROXY INIT ERROR]")
    if proxy:
        try:
            session = AiohttpSession(proxy=proxy)
            logger.info("[PROXY] Используется: %s", proxy)
        except Exception:
            logger.exception("[PROXY ERROR]")
            session = AiohttpSession()
    else:
        logger.info("[PROXY] Бот запущен без прокси")
        session = AiohttpSession()
    return Bot(token=TELEGRAM_TOKEN, session=session)
async def safe_delete_webhook(bot: Bot) -> None:
    for attempt in range(3):
        try:
            await bot.delete_webhook(drop_pending_updates=True, request_timeout=20)
            logger.info("Webhook удалён")
            return
        except TelegramNetworkError as exc:
            logger.warning("[WEBHOOK RETRY %s] %s", attempt + 1, exc)
            await asyncio.sleep(3)
        except Exception:
            logger.exception("[WEBHOOK ERROR]")
            return
def _watch_task(task: asyncio.Task, service: str | None = None) -> None:
    if task.cancelled():
        return
    try:
        error = task.exception()
    except asyncio.CancelledError:
        return
    if error is not None:
        logger.error("Фоновая задача %s завершилась с ошибкой: %s", task.get_name(), error,
                     exc_info=(type(error), error, error.__traceback__))
        if service:
            update_runtime_status(service, state="error", error=str(error))
    elif service:
        update_runtime_status(service, state="stopped", error=None)
async def main() -> None:
    print("BOT BW STARTED")
    background_tasks: list[asyncio.Task] = []
    bot: Bot | None = None
    notifier = CrossPlatformNotifier()
    def spawn(coro, name: str, service: str | None = None) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(lambda done: _watch_task(done, service))
        background_tasks.append(task)
        return task
    web_app = FastAPI(title="Twitch Monitoring API")
    configure_web_app(web_app)
    web_server = uvicorn.Server(uvicorn.Config(
        web_app, host=WEB_HOST, port=WEB_PORT, log_level="info", use_colors=True))
    spawn(web_server.serve(), "web-api")
    logger.info("Web API listening on %s:%s", WEB_HOST, WEB_PORT)
    if USE_PROXY:
        spawn(proxy_watcher(), "proxy-watcher")
    spawn(start_chat_bot(), "twitch-chat-bot", "twitch_chat")
    logger.info("Twitch chat worker scheduled")
    await notifier.start()
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN не задан — Telegram-бот пропущен")
        update_runtime_status("telegram", state="disabled", error=None)
    else:
        try:
            bot = await create_bot()
            await safe_delete_webhook(bot)
            me = await bot.get_me()
            update_runtime_status("telegram", state="connected", label=me.username or me.full_name, error=None)
            dispatcher = Dispatcher(storage=MemoryStorage())
            register_command_handlers(dispatcher)
            register_admin_handlers(dispatcher)
            register_twitch_api_handler(dispatcher)
            spawn(dispatcher.start_polling(bot), "telegram-polling", "telegram")
            logger.info("Telegram bot запущен: @%s", me.username)
        except Exception as exc:
            update_runtime_status("telegram", state="error", error=str(exc))
            logger.exception("TELEGRAM START ERROR — продолжаем без Telegram")
            if bot is not None:
                try:
                    await bot.session.close()
                except Exception:
                    logger.exception("TELEGRAM SESSION CLOSE ERROR")
                bot = None
    spawn(watch_streamers_file(CHECK_INTERVAL), "streamers-file-watcher")
    spawn(monitor(bot, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, CHECK_INTERVAL, notifier=notifier), "twitch-monitor")
    try:
        await asyncio.Event().wait()
    finally:
        web_server.should_exit = True
        for task in background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:
                logger.exception("TELEGRAM SESSION CLOSE ERROR")
        await notifier.close()
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("BOT STOPPED")
