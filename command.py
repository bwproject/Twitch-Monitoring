# command.py

from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from os import getenv

def register_command_handlers(dp):

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "<b>👋 Привет!</b>\n\n"
            "Это бот для мониторинга стримеров Twitch.\n\n"
            "Он автоматически отслеживает:\n"
            "• начало стрима\n"
            "• смену названия\n"
            "• смену категории\n"
            "• окончание стрима\n\n"
            "А также отправляет уведомления в выбранные Telegram-чаты.\n\n"
            "Посмотри доступные команды: /help",
            parse_mode="HTML"
        )

    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        await message.answer(
            "<b>📜 Доступные команды</b>\n\n"
            "🔧 Управление уведомлениями:\n"
            "/webadmin"
            "/streamerslist"
            "/notify — изменить настройки уведомлений для этого чата\n\n"
            "📝 Редактирование сообщений стримера:\n"
            "/edit — изменить шаблоны сообщений стримера\n"
            "/test ИМЯ — тест всех уведомлений по стримеру\n\n"
            "ℹ️ Служебные:\n"
            "/start — информация о боте\n"
            "/help — список команд\n",
            parse_mode="HTML"
        )


    # ---------------------------------------------------------
    # /webadmin
    # ---------------------------------------------------------
    @dp.message(Command("webadmin"))
    async def cmd_webadmin(message: types.Message):

        WEBAPP_URL = getenv(
            "TWITCH_WEBAPP_URL",
            "https://webapp.projectbw.ru/twitch/"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📺 Twitch Manager",
                        web_app=WebAppInfo(
                            url=WEBAPP_URL
                        )
                    )
                ]
            ]
        )


        await message.answer(
            "⚙️ Открыть панель управления Twitch:",
            reply_markup=keyboard
        )
