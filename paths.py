"""Central application paths and one-time migration of legacy root-level data."""
from __future__ import annotations
import json, os, re, shutil
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent
def _resolve_data_dir() -> Path:
    raw = Path(os.getenv("BOT_DATA_DIR", "data")).expanduser()
    return raw.resolve() if raw.is_absolute() else (ROOT_DIR / raw).resolve()
DATA_DIR = _resolve_data_dir()
TWITCH_DATA_DIR = DATA_DIR / "twitch"
TWITCH_STREAMERS_FILE = TWITCH_DATA_DIR / "streamers.json"
TWITCH_STREAMER_CONFIG_DIR = TWITCH_DATA_DIR / "streamers"
TWITCH_CACHE_FILE = TWITCH_DATA_DIR / "cache.json"
TWITCH_CHAT_DIR = TWITCH_DATA_DIR / "chat"
TWITCH_CHAT_CONFIG_FILE = TWITCH_CHAT_DIR / "chat_config.json"
TWITCH_CHAT_COMMANDS_DIR = TWITCH_CHAT_DIR / "commands"
ADMIN_DATA_DIR = DATA_DIR / "admin"
APPLICATIONS_FILE = DATA_DIR / "applications.json"
WEB_DIR = ROOT_DIR / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
LOG_DIR = ROOT_DIR / "logs"
def _copy_if_missing(source: Path, destination: Path) -> None:
    if source.is_file() and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
def ensure_data_layout() -> None:
    """Create runtime folders and migrate old root-level JSON files without overwriting data."""
    for directory in (TWITCH_DATA_DIR, TWITCH_STREAMER_CONFIG_DIR, TWITCH_CHAT_DIR,
                      TWITCH_CHAT_COMMANDS_DIR, ADMIN_DATA_DIR, DATA_DIR / "applications"):
        directory.mkdir(parents=True, exist_ok=True)
    _copy_if_missing(ROOT_DIR / "streamers.json", TWITCH_STREAMERS_FILE)
    _copy_if_missing(ROOT_DIR / "twitch_cache.json", TWITCH_CACHE_FILE)
    _copy_if_missing(ROOT_DIR / "chat_config.json", TWITCH_CHAT_CONFIG_FILE)
    _copy_if_missing(ROOT_DIR / "global_commands.json", TWITCH_CHAT_COMMANDS_DIR / "global_commands.json")
    try:
        streamers = json.loads(TWITCH_STREAMERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        streamers = []
    if isinstance(streamers, list):
        for item in streamers:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip().lower()
            if re.fullmatch(r"[a-z0-9_]{1,25}", name):
                _copy_if_missing(ROOT_DIR / f"{name}.json", TWITCH_STREAMER_CONFIG_DIR / f"{name}.json")
    for legacy in ROOT_DIR.glob("*_commands.json"):
        if legacy.is_file():
            _copy_if_missing(legacy, TWITCH_CHAT_COMMANDS_DIR / legacy.name)
ensure_data_layout()
