"""Discord and Lolka text notification clients."""
from __future__ import annotations
import asyncio
import html
import logging
import os
import re

log = logging.getLogger("twitch_monitor.notifications")

def to_platform_text(value: str) -> str:
    """Convert Telegram HTML templates to Markdown/plain text."""
    text = value or ""
    text = re.sub(r"<a\s+href=[\"']([^\"']+)[\"']\s*>(.*?)</a>", r"[\2](\1)", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:b|strong)>", "**", text, flags=re.I)
    text = re.sub(r"</?(?:i|em)>", "*", text, flags=re.I)
    text = re.sub(r"</?code>", "`", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()

class CrossPlatformNotifier:
    def __init__(self) -> None:
        self.discord_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        self.lolka_token = os.getenv("LOLKA_BOT_TOKEN", "").strip()
        self.discord = None
        self.lolka = None
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self.discord_token:
            try:
                import discord
                from discord.ext import commands
                intents = discord.Intents.none()
                intents.guilds = True
                self.discord = commands.Bot(command_prefix="!", intents=intents)
                self.tasks.append(asyncio.create_task(self._run_client("Discord", self.discord, self.discord_token), name="discord-notifier"))
                log.info("Discord notification bot is starting")
            except Exception:
                log.exception("Could not initialize Discord notification bot")
        if self.lolka_token:
            try:
                import lolka
                from lolka.ext import commands
                self.lolka = commands.Bot(command_prefix="!", intents=lolka.Intents.default())
                self.tasks.append(asyncio.create_task(self._run_client("Lolka", self.lolka, self.lolka_token), name="lolka-notifier"))
                log.info("Lolka notification bot is starting")
            except Exception:
                log.exception("Could not initialize Lolka notification bot")

    async def _run_client(self, platform: str, client, token: str) -> None:
        try:
            await client.start(token)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s notification bot stopped unexpectedly", platform)

    async def send(self, platform: str, channel_id, message: str) -> None:
        if not channel_id:
            return
        client = self.discord if platform == "discord" else self.lolka
        if client is None:
            return
        try:
            await asyncio.wait_for(client.wait_until_ready(), timeout=15)
            channel = client.get_channel(int(str(channel_id).strip()))
            if channel is None:
                fetch = getattr(client, "fetch_channel", None)
                if fetch is None:
                    raise RuntimeError("Клиент не поддерживает fetch_channel")
                channel = await fetch(int(str(channel_id).strip()))
            await channel.send(to_platform_text(message))
            log.info("%s notification sent to channel %s", platform, channel_id)
        except Exception:
            log.exception("Failed to send %s notification to channel %s", platform, channel_id)

    async def close(self) -> None:
        for client in (self.discord, self.lolka):
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    log.exception("Error closing notification client")
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
