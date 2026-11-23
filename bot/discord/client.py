"""Discord notification client with private Twitch subscription commands."""
from __future__ import annotations
import asyncio
from subscriptions import subscribe, unsubscribe, list_subscriptions

class DiscordNotificationClient:
    def __init__(self) -> None:
        import discord
        intents = discord.Intents.none()
        intents.guilds = True
        intents.dm_messages = True
        intents.messages = True
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_message(message):
            if message.author.bot or not isinstance(message.channel, discord.DMChannel):
                return
            parts = (message.content or "").strip().split(maxsplit=1)
            if not parts:
                return
            command = parts[0].lower()
            if command == "!follow":
                if len(parts) < 2:
                    await message.channel.send("Использование: !follow TwitchЛогин")
                else:
                    ok, result = subscribe("discord", message.author.id, parts[1])
                    await message.channel.send(("✅ " if ok else "ℹ️ ") + result)
            elif command == "!unfollow":
                if len(parts) < 2:
                    await message.channel.send("Использование: !unfollow TwitchЛогин")
                else:
                    ok, result = unsubscribe("discord", message.author.id, parts[1])
                    await message.channel.send(("✅ " if ok else "ℹ️ ") + result)
            elif command in ("!follows", "!help"):
                names = list_subscriptions("discord", message.author.id)
                listing = "\n".join("• @" + name for name in names) or "Пока пусто."
                await message.channel.send(
                    "📺 Личные подписки:\n" + listing +
                    "\n\n!follow ИМЯ — подписаться\n!unfollow ИМЯ — отписаться\n!follows — список"
                )

    async def start(self, token: str) -> None:
        await self.client.start(token)

    async def send(self, channel_id: str, message: str) -> None:
        await asyncio.wait_for(self.client.wait_until_ready(), timeout=15)
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(channel_id))
        await channel.send(message)

    async def send_dm(self, user_id: str, message: str) -> None:
        await asyncio.wait_for(self.client.wait_until_ready(), timeout=15)
        user = self.client.get_user(int(user_id))
        if user is None:
            user = await self.client.fetch_user(int(user_id))
        await user.send(message)

    async def close(self) -> None:
        await self.client.close()
