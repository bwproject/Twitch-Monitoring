"""Telegram bot commands, including private Twitch subscriptions."""
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from os import getenv
from subscriptions import subscribe, unsubscribe, list_subscriptions


def register_command_handlers(dp):
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "<b>👋 Привет!</b>\\n\\n"
            "Это бот для мониторинга стримеров Twitch.\\n\\n"
            "Получайте личные уведомления о стримах командой /follow ИМЯ.\\n"
            "Управление подписками: /follows и /unfollow ИМЯ.\\n\\n"
            "Посмотрите доступные команды: /help",
            parse_mode="HTML"
        )

    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        await message.answer(
            "<b>📜 Доступные команды</b>\\n\\n"
            "🔔 Личные подписки (в личной переписке):\\n"
            "/follow ИМЯ — подписаться на стримера\\n"
            "/unfollow ИМЯ — отменить подписку\\n"
            "/follows — список подписок\\n\\n"
            "🔧 Управление уведомлениями в чатах:\\n"
            "/webadmin — открыть панель управления\\n"
            "/streamerslist — список каналов\\n"
            "/notify — настройки уведомлений для чата\\n\\n"
            "📝 Редактирование сообщений стримера:\\n"
            "/edit — изменить шаблоны\\n"
            "/test ИМЯ — тест уведомлений\\n\\n"
            "/start — информация о боте\\n"
            "/help — список команд",
            parse_mode="HTML"
        )

    @dp.message(Command("follow"))
    async def cmd_follow(message: types.Message):
        if message.chat.type != "private":
            await message.reply("Для личной подписки напишите мне в личные сообщения.")
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /follow TwitchЛогин")
            return
        ok, reply = subscribe("telegram", message.from_user.id, parts[1])
        await message.answer(("✅ " if ok else "ℹ️ ") + reply)

    @dp.message(Command("unfollow"))
    async def cmd_unfollow(message: types.Message):
        if message.chat.type != "private":
            await message.reply("Эта команда работает в личных сообщениях.")
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /unfollow TwitchЛогин")
            return
        ok, reply = unsubscribe("telegram", message.from_user.id, parts[1])
        await message.answer(("✅ " if ok else "ℹ️ ") + reply)

    @dp.message(Command("follows"))
    async def cmd_follows(message: types.Message):
        if message.chat.type != "private":
            await message.reply("Список личных подписок доступен в личных сообщениях.")
            return
        names = list_subscriptions("telegram", message.from_user.id)
        if names:
            text = "📺 Ваши подписки:\\n" + "\\n".join("• @" + name for name in names)
        else:
            text = "У вас пока нет подписок. Используйте /follow TwitchЛогин."
        await message.answer(text)

    @dp.message(Command("webadmin"))
    async def cmd_webadmin(message: types.Message):
        webapp_url = getenv("TWITCH_WEBAPP_URL", "https://webapp.projectbw.ru/twitch/")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📺 Twitch Manager", web_app=WebAppInfo(url=webapp_url))
        ]])
        await message.answer("⚙️ Открыть панель управления Twitch:", reply_markup=keyboard)
