"""Live runtime state for the web status page."""
from datetime import datetime, timezone

STATUS = {
    "telegram": {"state": "starting", "label": None, "error": None},
    "twitch_chat": {"state": "starting", "username": None, "channels": [], "error": None},
    "twitch_monitor": {"state": "starting", "last_check": None, "streamers": [], "error": None},
}

def update(service, **values):
    STATUS[service].update(values)
    STATUS[service]["updated_at"] = datetime.now(timezone.utc).isoformat()

def snapshot():
    return {key: dict(value) for key, value in STATUS.items()}
