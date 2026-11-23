"""Telegram command for checking Twitch Helix API connectivity."""
from aiogram import types
from aiogram.filters import Command
from twitch.api import get_streamers_status


def register_twitch_api_handler(dp):
    @dp.message(Command("twitchapi"))
    async def twitch_api_test(message: types.Message):
        try:
            result = get_streamers_status(["ninja"])
            await message.answer("✅ Twitch API OK\n" f"Онлайн: {len(result)}")
        except Exception as exc:
            await message.answer(f"❌ ERROR: {exc}")
