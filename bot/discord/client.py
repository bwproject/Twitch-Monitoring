"""Discord text-channel notification client."""
from __future__ import annotations
import asyncio
class DiscordNotificationClient:
    def __init__(self) -> None:
        import discord
        intents = discord.Intents.none()
        intents.guilds = True
        self.client = discord.Client(intents=intents)
    async def start(self, token: str) -> None:
        await self.client.start(token)
    async def send(self, channel_id: str, message: str) -> None:
        await asyncio.wait_for(self.client.wait_until_ready(), timeout=15)
        channel = self.client.get_channel(int(channel_id))
        if channel is None:
            channel = await self.client.fetch_channel(int(channel_id))
        await channel.send(message)
    async def close(self) -> None:
        await self.client.close()
