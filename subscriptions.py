"""Persistent personal Twitch subscriptions for Telegram, Discord and Lolka DMs."""
from __future__ import annotations
import json
import re
from pathlib import Path
from paths import DATA_DIR, TWITCH_STREAMERS_FILE

SUBSCRIPTIONS_FILE = DATA_DIR / "personal_subscriptions.json"
PLATFORMS = {"telegram", "discord", "lolka"}
LOGIN_RE = re.compile(r"^[a-zA-Z0-9_]{1,50}$")

def _load() -> dict:
    try:
        data = json.loads(SUBSCRIPTIONS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def _save(data: dict) -> None:
    SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUBSCRIPTIONS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SUBSCRIPTIONS_FILE)

def known_streamer(name: str) -> str | None:
    name = str(name or "").strip().lstrip("@").lower()
    if not LOGIN_RE.fullmatch(name):
        return None
    try:
        items = json.loads(TWITCH_STREAMERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(items, list):
        return None
    return next((str(item.get("name", "")).lower() for item in items
                 if isinstance(item, dict) and str(item.get("name", "")).lower() == name), None)

def subscribe(platform: str, user_id: str | int, streamer: str) -> tuple[bool, str]:
    if platform not in PLATFORMS:
        return False, "Неизвестная платформа."
    name = known_streamer(streamer)
    if not name:
        return False, "Такого канала нет в списке мониторинга. Проверьте Twitch-логин."
    data = _load()
    user = str(user_id)
    items = data.setdefault(platform, {}).setdefault(user, [])
    if name in items:
        return False, f"Вы уже отслеживаете @{name}."
    items.append(name)
    _save(data)
    return True, f"Готово! Теперь вы получите личные уведомления о трансляциях @{name}."

def unsubscribe(platform: str, user_id: str | int, streamer: str) -> tuple[bool, str]:
    name = str(streamer or "").strip().lstrip("@").lower()
    data = _load()
    items = data.get(platform, {}).get(str(user_id), [])
    if name not in items:
        return False, f"Подписка на @{name} не найдена."
    items.remove(name)
    if not items:
        data.get(platform, {}).pop(str(user_id), None)
    _save(data)
    return True, f"Вы отписались от @{name}."

def list_subscriptions(platform: str, user_id: str | int) -> list[str]:
    return sorted(_load().get(platform, {}).get(str(user_id), []))

def subscribers(platform: str, streamer: str) -> list[str]:
    name = str(streamer).lower()
    return [user_id for user_id, names in _load().get(platform, {}).items() if name in names]
