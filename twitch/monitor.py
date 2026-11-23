# twitch.py

import asyncio
import json
import logging
import os

from pathlib import Path
from datetime import datetime, timezone

try:
    from runtime_status import update as update_runtime_status
except ImportError:
    def update_runtime_status(*args, **kwargs):
        pass


from .api import get_streamer_status, get_streamers_status

logger = logging.getLogger("twitch_monitor")

# ============================================================
# PATHS
# ============================================================

from paths import TWITCH_STREAMERS_FILE, TWITCH_STREAMER_CONFIG_DIR

STREAMERS_FILE = TWITCH_STREAMERS_FILE

STREAMERS = []
_last_mtime = None


# ============================================================
# LOAD STREAMERS
# ============================================================

def load_streamers():
    global STREAMERS

    if not STREAMERS_FILE.exists():
        STREAMERS = []
        logger.warning("streamers.json отсутствует")
        return

    try:
        with STREAMERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            STREAMERS = []
            return

        result = []

        for streamer in data:
            name = streamer.get("name")

            if not name:
                continue

            custom_file = TWITCH_STREAMER_CONFIG_DIR / f"{name}.json"

            if custom_file.exists():
                try:
                    with custom_file.open("r", encoding="utf-8") as sf:
                        custom = json.load(sf)

                    if isinstance(custom, dict):
                        result.append(custom)
                        logger.info(
                            f"Используется {custom_file.name}"
                        )
                        continue

                except Exception as e:
                    logger.error(
                        f"{custom_file}: {e}"
                    )

            result.append(streamer)

        STREAMERS = result

        logger.info(
            f"STREAMERS LOADED: {[x.get('name') for x in STREAMERS]}"
        )

    except Exception as e:
        logger.exception(
            f"LOAD ERROR: {e}"
        )
        STREAMERS = []


# ============================================================
# WATCH FILE
# ============================================================

async def watch_streamers_file(interval=5):
    global _last_mtime

    while True:
        try:
            if STREAMERS_FILE.exists():

                mtime = STREAMERS_FILE.stat().st_mtime

                if _last_mtime is None or mtime != _last_mtime:
                    _last_mtime = mtime
                    load_streamers()

        except Exception as e:
            logger.exception(
                f"WATCH ERROR: {e}"
            )

        await asyncio.sleep(interval)


# ============================================================
# MONITOR
# ============================================================

async def send_event(bot, notifier, streamer, event, **values):
    """Send a Twitch event to all configured Telegram, Discord and Lolka destinations."""
    name = str(streamer.get("name", "")).lower()
    template = streamer.get("messages", {}).get(event, "")
    if not template:
        return
    try:
        message = template.format(name=name, url=f"https://twitch.tv/{name}", **values)
    except (KeyError, ValueError) as exc:
        logger.error("MESSAGE TEMPLATE ERROR %s/%s: %s", name, event, exc)
        return
    if notifier is not None:
        await notifier.send_personal_event(name, message, telegram_bot=bot)
    for channel in streamer.get("channels", []):
        if not channel.get(f"notify_{event}", True):
            continue
        chat_id = channel.get("chat_id")
        if chat_id and bot is not None:
            try:
                await bot.send_message(chat_id, message, parse_mode="HTML")
            except Exception as exc:
                logger.error("%s SEND ERROR %s: %s", event.upper(), name, exc)
        if notifier is not None:
            await notifier.send("discord", channel.get("discord_channel_id"), message)
            await notifier.send("lolka", channel.get("lolka_channel_id"), message)



async def monitor(
    bot,
    client_id,
    client_secret,
    interval=30,
    notifier=None
):

    state = {}
    initialized = False

    while True:

        try:

            if not STREAMERS:
                logger.warning(
                    "STREAMERS пустой"
                )

                await asyncio.sleep(interval)
                continue


            names = [
                s["name"].lower()
                for s in STREAMERS
            ]

            logger.info(
                f"CHECK: {names}"
            )


            online = get_streamers_status(names)
            update_runtime_status("twitch_monitor", state="connected", last_check=datetime.now(timezone.utc).isoformat(), streamers=names, error=None)


            for streamer in STREAMERS:

                name = streamer["name"].lower()

                messages = streamer.get(
                    "messages",
                    {}
                )

                url = f"https://twitch.tv/{name}"


                if name not in state:
                    state[name] = {
                        "online": False,
                        "title": "",
                        "game": "",
                        "started_at": "",
                        "start_time": None,
                        "peak_viewers": 0
                    }


                st = state[name]


                # ==================================================
                # ONLINE
                # ==================================================

                if name in online:

                    data = online[name]

                    title = data.get(
                        "title",
                        ""
                    )

                    game = data.get(
                        "game_name",
                        ""
                    )

                    viewers = data.get(
                        "viewer_count",
                        0
                    )

                    started_at = data.get(
                        "started_at",
                        ""
                    )


                    # ==============================================
                    # ПЕРВЫЙ ЗАПУСК БОТА
                    # НЕ ОТПРАВЛЯЕМ TELEGRAM
                    # ==============================================

                    if not initialized:

                        st["online"] = True
                        st["title"] = title
                        st["game"] = game
                        st["started_at"] = started_at
                        st["start_time"] = datetime.now(
                            timezone.utc
                        )
                        st["peak_viewers"] = viewers

                        continue


                    # ==============================================
                    # НОВЫЙ СТРИМ
                    # ==============================================

                    if (
                        not st["online"]
                        or st["started_at"] != started_at
                    ):

                        logger.info(
                            f"START STREAM {name}"
                        )

                        st["online"] = True
                        st["title"] = title
                        st["game"] = game
                        st["started_at"] = started_at
                        st["start_time"] = datetime.now(
                            timezone.utc
                        )
                        st["peak_viewers"] = viewers


                        await send_event(bot, notifier, streamer, "start", title=title, game=game)

                    else:
                        if title != st["title"]:
                            logger.info("TITLE CHANGE %s", name)
                            await send_event(bot, notifier, streamer, "title_change", old_title=st["title"], title=title, old_game=st["game"], game=game)
                        if game != st["game"]:
                            logger.info("GAME CHANGE %s", name)
                            await send_event(bot, notifier, streamer, "game_change", old_title=st["title"], title=title, old_game=st["game"], game=game)
                        st["title"] = title
                        st["game"] = game
                        if viewers > st["peak_viewers"]:
                            st["peak_viewers"] = viewers
                # ==================================================
                # OFFLINE
                # ==================================================

                else:

                    if not st["online"]:
                        continue


                    logger.info(
                        f"END STREAM {name}"
                    )


                    duration = (
                        datetime.now(
                            timezone.utc
                        )
                        -
                        st["start_time"]
                    )


                    sec = int(
                        duration.total_seconds()
                    )


                    hours, rem = divmod(
                        sec,
                        3600
                    )

                    minutes = rem // 60


                    dur = (
                        f"{hours}ч {minutes}мин"
                    )


                    await send_event(bot, notifier, streamer, "end", title=st["title"], duration=dur, peak_viewers=st["peak_viewers"])


                    st["online"] = False
                    st["title"] = ""
                    st["game"] = ""
                    st["started_at"] = ""
                    st["start_time"] = None
                    st["peak_viewers"] = 0


            # после первого полного прохода
            # включаем уведомления

            if not initialized:

                initialized = True

                logger.info(
                    "TWITCH MONITOR INITIALIZED"
                )


        except Exception as e:
            update_runtime_status("twitch_monitor", state="error", error=str(e))
            logger.exception(
                f"MONITOR ERROR: {e}"
            )


        await asyncio.sleep(
            interval
        )
