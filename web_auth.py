from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BOT_DATA_DIR", str(BASE_DIR / "data"))).resolve()
AUTH_DIR = DATA_DIR / "admin"
USERS_FILE = AUTH_DIR / "users.json"
SESSION_SECRET_FILE = AUTH_DIR / "session_secret"


def _env_user(username: str, password: str, role: str, streamer: str = "") -> dict[str, Any] | None:
    if not username or not password:
        return None
    return {
        "username": username,
        "password": password,
        "role": role,
        "streamers": [x.strip().lower() for x in streamer.split(",") if x.strip()],
        "enabled": True,
    }


def _legacy_hash_matches(password: str, encoded: str) -> bool:
    """Read old PBKDF2 hashes so existing accounts keep working during migration."""
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def _configured_passwords() -> dict[str, str]:
    configured: dict[str, str] = {}
    admin_name = os.getenv("WEB_ADMIN_USERNAME", "admin").strip()
    admin_password = os.getenv("WEB_ADMIN_PASSWORD", "")
    if admin_name and admin_password:
        configured[admin_name] = admin_password
    for number in (1, 2):
        username = os.getenv(f"WEB_USER{number}_USERNAME", "").strip()
        password = os.getenv(f"WEB_USER{number}_PASSWORD", "")
        if username and password:
            configured[username] = password
    return configured


def init_admin_storage() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSION_SECRET_FILE.exists():
        SESSION_SECRET_FILE.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        try:
            SESSION_SECRET_FILE.chmod(0o600)
        except OSError:
            pass

    if USERS_FILE.exists():
        return

    users = []
    admin_name = os.getenv("WEB_ADMIN_USERNAME", "admin").strip()
    admin_password = os.getenv("WEB_ADMIN_PASSWORD", "")
    if not admin_password:
        admin_password = secrets.token_urlsafe(14)
        print(f"[WEB ADMIN] Сгенерирован пароль для {admin_name}: {admin_password}")
        print("[WEB ADMIN] Сохраните пароль сейчас; он не будет показан повторно.")

    users.append(_env_user(admin_name, admin_password, "admin"))
    for number in (1, 2):
        username = os.getenv(f"WEB_USER{number}_USERNAME", "").strip()
        password = os.getenv(f"WEB_USER{number}_PASSWORD", "")
        streamers = os.getenv(f"WEB_USER{number}_STREAMERS", "")
        if username and password:
            users.append(_env_user(username, password, "user", streamers))

    USERS_FILE.write_text(json.dumps({"users": users}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        USERS_FILE.chmod(0o600)
    except OSError:
        pass


def get_session_secret() -> str:
    init_admin_storage()
    return SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()


def load_users() -> list[dict[str, Any]]:
    init_admin_storage()
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        users = data.get("users", []) if isinstance(data, dict) else []
        if not isinstance(users, list):
            return []

        # Migrate accounts whose current passwords are available in .env.
        configured = _configured_passwords()
        changed = False
        for user in users:
            username = str(user.get("username", ""))
            if username in configured and user.get("password") != configured[username]:
                user.pop("password_hash", None)
                user["password"] = configured[username]
                changed = True
        if changed:
            save_users(users)
        return users
    except (OSError, ValueError):
        return []


def save_users(users: list[dict[str, Any]]) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    temp = USERS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps({"users": users}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(USERS_FILE)


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    for user in load_users():
        if not user.get("enabled", True):
            continue
        if not hmac.compare_digest(str(user.get("username", "")), username):
            continue

        stored_password = user.get("password")
        valid = (
            isinstance(stored_password, str)
            and hmac.compare_digest(stored_password, password)
        )
        if not valid and isinstance(user.get("password_hash"), str):
            valid = _legacy_hash_matches(password, user["password_hash"])

        if valid:
            return {
                "username": user["username"],
                "role": user.get("role", "user"),
                "streamers": user.get("streamers", []),
            }
    return None
