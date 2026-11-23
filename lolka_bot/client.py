"""Lolka text-channel notification client."""
from __future__ import annotations
import asyncio
class LolkaNotificationClient:
    def __init__(self) -> None:
        import lolka
        from lolka.ext import commands
        self.client = commands.Bot(command_prefix="!", intents=lolka.Intents.default())
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
    async def close(self) -> None:
        await self.client.close()
