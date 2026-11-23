"""Load admin-managed integration credentials before bot modules are imported."""
from __future__ import annotations
import json
import os
from pathlib import Path

from paths import DATA_DIR

SETTINGS_FILE = DATA_DIR / "admin" / "integrations.json"

ENV_KEYS = {
    "telegram_token": "TELEGRAM_TOKEN",
    "twitch_client_id": "TWITCH_CLIENT_ID",
    "twitch_client_secret": "TWITCH_CLIENT_SECRET",
    "twitch_bot_nick": "TWITCH_BOT_NICK",
    "twitch_bot_id": "TWITCH_BOT_ID",
    "twitch_oauth": "TWITCH_OAUTH",
    "discord_token": "DISCORD_BOT_TOKEN",
    "lolka_token": "LOLKA_BOT_TOKEN",
    "discord_channel_id": "DISCORD_CHANNEL_ID",
    "lolka_channel_id": "LOLKA_CHANNEL_ID",
}

def read_integration_settings() -> dict:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def apply_integration_settings() -> None:
    for key, env_name in ENV_KEYS.items():
        value = read_integration_settings().get(key)
        if isinstance(value, str) and value.strip():
            os.environ[env_name] = value.strip()

def save_integration_settings(values: dict, clear: list[str] | None = None) -> dict:
    current = read_integration_settings()
    for key in ENV_KEYS:
        value = values.get(key)
        if isinstance(value, str) and value.strip():
            current[key] = value.strip()
    for key in clear or []:
        if key in ENV_KEYS:
            current.pop(key, None)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(SETTINGS_FILE)
    return current

def integration_status() -> dict:
    settings = read_integration_settings()
    return {
        key: bool(settings.get(key) or os.getenv(env_name))
        for key, env_name in ENV_KEYS.items()
    }
