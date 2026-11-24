"""Lolka notification client with private Twitch subscription commands."""
from __future__ import annotations
import asyncio
from subscriptions import subscribe, unsubscribe, list_subscriptions
from runtime_status import update as update_runtime_status

class LolkaNotificationClient:
    def __init__(self) -> None:
        import lolka
        from lolka.ext import commands
        intents = lolka.Intents.default()
        try:
            intents.message_content = True
        except Exception:
            pass
        self.client = commands.Bot(command_prefix="!", intents=intents)

        @self.client.event
        async def on_ready():
            user = getattr(self.client, "user", None)
            update_runtime_status("lolka", state="connected", username=getattr(user, "name", None), error=None)

        @self.client.event
        async def on_message(message):
            if getattr(message.author, "bot", False):
                return
            if getattr(message, "guild", None) is not None:
                return
            parts = (getattr(message, "content", "") or "").strip().split(maxsplit=1)
            if not parts:
                return
            command = parts[0].lower()
            if command == "!follow":
                if len(parts) < 2:
                    await message.channel.send("Использование: !follow TwitchЛогин")
                else:
                    ok, result = subscribe("lolka", message.author.id, parts[1])
                    await message.channel.send(("✅ " if ok else "ℹ️ ") + result)
            elif command == "!unfollow":
                if len(parts) < 2:
                    await message.channel.send("Использование: !unfollow TwitchЛогин")
                else:
                    ok, result = unsubscribe("lolka", message.author.id, parts[1])
                    await message.channel.send(("✅ " if ok else "ℹ️ ") + result)
            elif command in ("!follows", "!help"):
                names = list_subscriptions("lolka", message.author.id)
                listing = "\n".join("• @" + name for name in names) or "Пока пусто."
                await message.channel.send(
                    "📺 Личные подписки:\n" + listing +
                    "\n\n!follow ИМЯ — подписаться\n!unfollow ИМЯ — отписаться\n!follows — список"
                )

    async def start(self, token: str) -> None:
        await self.client.start(token)

    async def send(self, channel_id: str, message: str) -> None:
        wait_ready = getattr(self.client, "wait_until_ready", None)
        if wait_ready is not None:
            await asyncio.wait_for(wait_ready(), timeout=15)
        else:
            for _ in range(30):
                if self.client.is_ready():
                    break
                await asyncio.sleep(0.5)
            if not self.client.is_ready():
                raise TimeoutError("Lolka bot did not become ready within 15 seconds")
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            fetch_channel = getattr(self.client, "fetch_channel", None)
            if fetch_channel is None:
                raise RuntimeError("Lolka client does not support fetch_channel")
            channel = await fetch_channel(int(channel_id))
        await channel.send(message)

    async def send_dm(self, user_id: str, message: str) -> None:
        wait_ready = getattr(self.client, "wait_until_ready", None)
        if wait_ready is not None:
            await asyncio.wait_for(wait_ready(), timeout=15)
        user = self.client.get_user(int(user_id))
        if user is None:
            fetch_user = getattr(self.client, "fetch_user", None)
            if fetch_user is None:
                raise RuntimeError("Lolka client does not support fetch_user")
            user = await fetch_user(int(user_id))
        await user.send(message)

    async def close(self) -> None:
        await self.client.close()
