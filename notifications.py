"""Independent lifecycle and fan-out for optional Discord and Lolka bots."""
from __future__ import annotations
import asyncio, html, logging, os, re
from bot.discord.client import DiscordNotificationClient
from bot.lolka.client import LolkaNotificationClient
from runtime_status import update as update_runtime_status
log = logging.getLogger("twitch_monitor.notifications")
def to_platform_text(value: str) -> str:
    text = value or ""
    text = re.sub(r"<a\s+href=[\"']([^\"']+)[\"']\s*>(.*?)</a>", r"[\2](\1)", text, flags=re.I | re.S)
    text = re.sub(r"</?(?:b|strong)>", "**", text, flags=re.I)
    text = re.sub(r"</?(?:i|em)>", "*", text, flags=re.I)
    text = re.sub(r"</?code>", chr(96), text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()
class CrossPlatformNotifier:
    """Starts Discord and Lolka independently; either platform may be absent."""
    def __init__(self) -> None:
        self.tokens = {"discord": os.getenv("DISCORD_BOT_TOKEN", "").strip(),
                       "lolka": os.getenv("LOLKA_BOT_TOKEN", "").strip()}
        self.factories = {"discord": DiscordNotificationClient, "lolka": LolkaNotificationClient}
        self.clients = {}
        self.tasks: list[asyncio.Task] = []
    async def start(self) -> None:
        for platform, token in self.tokens.items():
            if not token:
                log.info("%s bot not configured — skipped", platform.capitalize())
                update_runtime_status(platform, state="disabled", error=None)
                continue
            try:
                client = self.factories[platform]()
                self.clients[platform] = client
                update_runtime_status(platform, state="connecting", error=None)
                self.tasks.append(asyncio.create_task(self._run_client(platform, client, token),
                                                       name=f"{platform}-notification-bot"))
            except Exception as exc:
                update_runtime_status(platform, state="error", error=str(exc))
                log.exception("Could not initialize %s bot; continuing", platform)
    async def _run_client(self, platform: str, client, token: str) -> None:
        try:
            await client.start(token)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            update_runtime_status(platform, state="error", error=str(exc))
            log.exception("%s bot stopped unexpectedly; other services continue", platform)
        else:
            update_runtime_status(platform, state="stopped", error=None)
    async def send(self, platform: str, channel_id, message: str) -> None:
        if not channel_id:
            return
        client = self.clients.get(platform)
        if client is None:
            return
        try:
            await client.send(str(channel_id).strip(), to_platform_text(message))
            log.info("%s notification sent to channel %s", platform, channel_id)
        except Exception:
            log.exception("Failed to send %s notification to channel %s", platform, channel_id)
    async def close(self) -> None:
        for platform, client in list(self.clients.items()):
            try:
                await client.close()
            except Exception:
                log.exception("Error closing %s bot", platform)
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
