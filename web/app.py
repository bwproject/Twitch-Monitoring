from __future__ import annotations
import json, re, os, uuid, hmac, hashlib, time
from urllib.parse import parse_qsl
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
from web.auth import authenticate, get_session_secret, load_users, save_users
from runtime_status import snapshot as runtime_status_snapshot
from runtime_config import save_integration_settings, integration_status
from twitch.api import get_streamer_status, get_live_preview
from paths import ROOT_DIR, TWITCH_STREAMERS_FILE, TWITCH_STREAMER_CONFIG_DIR, APPLICATIONS_FILE, TEMPLATES_DIR

BASE_DIR = ROOT_DIR
STREAMERS_FILE = TWITCH_STREAMERS_FILE
ADMIN_HTML = TEMPLATES_DIR / "admin.html"
TWITCH_WEBAPP_HTML = TEMPLATES_DIR / "twitch" / "index.html"
router=APIRouter()
def configure_web_app(app):
    app.add_middleware(SessionMiddleware,secret_key=get_session_secret(),session_cookie="twitch_admin_session",
                       same_site="lax",https_only=os.getenv("WEB_COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes", "on"),max_age=43200)
    app.include_router(router)
def current_user(request):
    """Resolve the signed-in account against current server-side permissions."""
    session_user = request.session.get("user")
    if not isinstance(session_user, dict) or not session_user.get("username"):
        return None
    username = str(session_user["username"])
    account = next((item for item in load_users()
                    if str(item.get("username", "")) == username), None)
    if not account or not account.get("enabled", True):
        request.session.clear()
        return None
    return {
        "username": account["username"],
        "role": account.get("role", "user"),
        "streamers": [str(x).strip().lower() for x in account.get("streamers", [])],
    }
def require_user(request): return current_user(request)
def load_json(file):
    try:
        with file.open("r",encoding="utf-8") as f: return json.load(f)
    except (OSError,ValueError) as exc:
        print("[WEBAPP JSON ERROR]",file,exc); return None
def save_json(file,data):
    file.parent.mkdir(parents=True,exist_ok=True)
    temp=file.with_suffix(file.suffix+".tmp")
    with temp.open("w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
    temp.replace(file)
def get_streamer_file(name):
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,50}",name): raise ValueError("Некорректное имя стримера")
    return TWITCH_STREAMER_CONFIG_DIR / f"{name}.json"
def load_streamers():
    data=load_json(STREAMERS_FILE)
    return data if isinstance(data,list) else []

STREAMER_ORDER_FILE = STREAMERS_FILE.parent / "streamer_order.json"
def ordered_streamers(items):
    """Apply the administrator's public display order; append newly added channels."""
    try:
        saved = load_json(STREAMER_ORDER_FILE)
    except Exception:
        saved = None
    if not isinstance(saved, list):
        saved = []
    by_name = {str(item.get("name", "")).strip().lower(): item for item in items
               if isinstance(item, dict) and item.get("name")}
    ordered = [by_name.pop(str(name).strip().lower()) for name in saved
               if str(name).strip().lower() in by_name]
    ordered.extend(item for item in items if isinstance(item, dict)
                   and str(item.get("name", "")).strip().lower() in by_name
                   and by_name.pop(str(item.get("name", "")).strip().lower(), None) is not None)
    return ordered
def load_streamer(name):
    custom=get_streamer_file(name)
    if custom.exists():
        data=load_json(custom)
        if isinstance(data,dict): return data
    for item in load_streamers():
        if str(item.get("name","")).lower()==name.lower(): return item
    return None
def save_streamer(data):
    name=str(data.get("name","")).strip().lower()
    save_json(get_streamer_file(name),data)
def can_edit(user,name):
    return bool(user and (
        user.get("role") == "admin"
        or name.strip().lower() in user.get("streamers", [])
    ))

def telegram_webapp_user_id(request: Request) -> int | None:
    """Validate Telegram Mini App initData; never trust a client-supplied user ID."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not init_data or not token:
        return None
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
        received_hash = fields.pop("hash")
        auth_date = int(fields["auth_date"])
        now = int(time.time())
        if auth_date > now + 30 or now - auth_date > 86400:
            return None
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None
        telegram_user = json.loads(fields["user"])
        return int(telegram_user["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

def telegram_owns_streamer(request: Request, name: str):
    telegram_id = telegram_webapp_user_id(request)
    if telegram_id is None:
        return None
    streamer = load_streamer(name)
    if not streamer:
        return None
    owner_value = streamer.get("tg_id")
    if owner_value in (None, ""):
        master = next((item for item in load_streamers()
                       if str(item.get("name", "")).lower() == name.lower()), None)
        owner_value = master.get("tg_id") if master else None
        if owner_value not in (None, ""):
            streamer = dict(streamer)
            streamer["tg_id"] = owner_value
    try:
        owner_id = int(owner_value or 0)
    except (TypeError, ValueError):
        return None
    return streamer if owner_id == telegram_id else None
@router.get("/", include_in_schema=False)
async def landing_page(): return FileResponse(TEMPLATES_DIR / "index.html")

@router.get("/status", include_in_schema=False)
async def public_status():
    status = runtime_status_snapshot()
    return {
        "telegram": {"state": status["telegram"]["state"], "label": status["telegram"].get("label")},
        "discord": {"state": status["discord"]["state"], "username": status["discord"].get("username")},
        "lolka": {"state": status["lolka"]["state"], "username": status["lolka"].get("username")},
        "twitch_chat": {"state": status["twitch_chat"]["state"], "username": status["twitch_chat"].get("username"), "channels": status["twitch_chat"].get("channels", [])},
        "twitch_monitor": {"state": status["twitch_monitor"]["state"], "last_check": status["twitch_monitor"].get("last_check")},
    }

@router.get("/admin/api/status")
async def admin_runtime_status(request: Request):
    if not require_user(request):
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    return runtime_status_snapshot()

@router.get("/public/streamers", include_in_schema=False)
async def public_streamers():
    """Public list of configured Twitch channels, profile images and live/offline previews."""
    items = ordered_streamers(load_streamers())
    names = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("login") or item.get("username") or "").strip().lower()
        if re.fullmatch(r"[a-zA-Z0-9_]{1,50}", name) and name not in names:
            names.append(name)
    if not names:
        return {"streamers": [], "live": []}

    api = __import__("twitch.api", fromlist=["get_streamers_status", "get_twitch_api"])
    try:
        statuses = await run_in_threadpool(api.get_streamers_status, names)
    except Exception as exc:
        print("[PUBLIC STREAMERS STATUS ERROR]", exc)
        statuses = {}

    # Helix /users provides profile avatars and optional offline channel banners.
    try:
        users = await run_in_threadpool(api.get_twitch_api().fetch_users, names)
    except Exception as exc:
        print("[PUBLIC STREAMERS USERS ERROR]", exc)
        users = {}

    result = []
    for name in names:
        status = statuses.get(name) or {}
        profile = users.get(name) or {}
        online = bool(status.get("online") or (status.get("offline") is False and status.get("started_at")))
        live_thumb = str(status.get("thumbnail_url") or "")
        if live_thumb:
            live_thumb = live_thumb.replace("{width}", "640").replace("{height}", "360")

        avatar = str(profile.get("profile_image_url") or status.get("profile_image_url") or "")
        offline_preview = str(profile.get("offline_image_url") or status.get("offline_image_url") or "")
        # A profile avatar is a reliable fallback when a channel has no custom offline banner.
        preview = live_thumb if online and live_thumb else (offline_preview or avatar)
        result.append({
            "name": name,
            "display_name": profile.get("display_name") or status.get("user_name") or status.get("user_login") or name,
            "is_live": online,
            "title": status.get("title") or "",
            "game_name": status.get("game_name") or "",
            "viewer_count": int(status.get("viewer_count") or 0),
            "started_at": status.get("started_at") or "",
            "avatar_url": avatar,
            "thumbnail_url": live_thumb,
            "preview_url": preview,
            "url": f"https://twitch.tv/{name}",
        })
    return {"streamers": result, "live": [item for item in result if item["is_live"]]}
 
@router.get("/apply", include_in_schema=False)
async def application_page(): return FileResponse(TEMPLATES_DIR / "apply.html")

@router.get("/admin",include_in_schema=False)
@router.get("/admin/login",include_in_schema=False)
async def admin_page(): return FileResponse(ADMIN_HTML)
@router.post("/admin/api/login")
async def admin_login(request:Request):
    try:
        data=await request.json()
        user=authenticate(str(data.get("username","")),str(data.get("password","")))
    except Exception: user=None
    if not user: return JSONResponse({"ok":False,"error":"Неверный логин или пароль"},status_code=401)
    request.session.clear(); request.session["user"]=user
    return {"ok":True,"user":{"username":user["username"],"role":user["role"]}}
@router.post("/admin/api/logout")
async def admin_logout(request:Request):
    request.session.clear(); return {"ok":True}
@router.get("/admin/api/me")
async def admin_me(request:Request):
    user=require_user(request)
    if not user: return JSONResponse({"error":"Требуется вход"},status_code=401)
    return {"username":user["username"],"role":user["role"]}
@router.get("/admin/api/streamers")
async def admin_streamers(request:Request):
    user=require_user(request)
    if not user: return JSONResponse({"error":"Требуется вход"},status_code=401)
    items=ordered_streamers(load_streamers())
    if user.get("role")!="admin":
        allowed=set(user.get("streamers",[])); items=[x for x in items if str(x.get("name","")).lower() in allowed]
    return [{"name":x.get("name")} for x in items if x.get("name")]


@router.put("/admin/api/streamers/order")
async def admin_update_streamer_order(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Менять порядок стримеров может только администратор"}, status_code=403)
    try:
        payload = await request.json()
        names = payload.get("order") if isinstance(payload, dict) else None
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError("Ожидается список Twitch-логинов")
        names = [name.strip().lower() for name in names]
        if len(names) != len(set(names)):
            raise ValueError("В списке есть повторяющиеся каналы")
        current = {str(item.get("name", "")).strip().lower() for item in load_streamers()
                   if isinstance(item, dict) and item.get("name")}
        if set(names) != current:
            raise ValueError("Список каналов изменился. Обновите страницу и попробуйте снова.")
        save_json(STREAMER_ORDER_FILE, names)
        return {"ok": True, "order": names}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@router.post("/admin/api/streamers")
async def admin_add_streamer(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Добавлять Twitch-каналы может только администратор"}, status_code=403)

    try:
        payload = await request.json()
        name = str(payload.get("name", "")).strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9_]{1,25}", name):
            raise ValueError("Укажите корректный Twitch-логин (латинские буквы, цифры и _, до 25 символов).")

        existing = load_streamers()
        if any(str(item.get("name", "")).lower() == name for item in existing):
            return JSONResponse({"error": f"Канал @{name} уже добавлен."}, status_code=409)

        # Confirm that this login is a real Twitch account before writing any files.
        preview = await run_in_threadpool(get_live_preview, name)
        streamer = {
            "name": preview.get("login", name),
            "preview": True,
            "channels": [],
            "messages": {
                "start": "🟢 <b><a href=\"{url}\">{name}</a></b> начал трансляцию!\n🟢 Категория: <b>{game}</b>\n🟢 Название: <i>{title}</i>",
                "title_change": "Сменил название: <b><a href=\"{url}\">{name}</a></b>\nС \"<i>{old_title}</i>\" на \"<i>{title}</i>\"",
                "game_change": "Сменил категорию: <b><a href=\"{url}\">{name}</a></b>\nС \"<b>{old_game}</b>\" на \"<b>{game}</b>\"",
                "end": "🔴 <b><a href=\"{url}\">{name}</a></b> завершил трансляцию.\nДлительность: <b>{duration}</b>\nПиковый онлайн: <b>{peak_viewers}</b>"
            }
        }

        config_file = get_streamer_file(name)
        if config_file.exists():
            return JSONResponse({"error": "Файл настроек этого канала уже существует. Проверьте конфигурацию."}, status_code=409)

        save_json(config_file, streamer)
        try:
            existing.append({"name": streamer["name"], "preview": True, "channels": [], "messages": streamer["messages"]})
            save_json(STREAMERS_FILE, existing)
        except Exception:
            config_file.unlink(missing_ok=True)
            raise

        return {"ok": True, "streamer": {"name": streamer["name"]}, "twitch": preview}
    except LookupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        print("[ADMIN ADD STREAMER ERROR]", exc)
        return JSONResponse({"error": "Не удалось добавить канал. Проверьте настройки Twitch API и журнал сервера."}, status_code=502)


@router.get("/admin/api/twitch/{name}")
async def admin_twitch_preview(name: str, request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if not can_edit(user, name):
        return JSONResponse({"error": "Нет доступа к этому стримеру"}, status_code=403)
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,50}", name):
        return JSONResponse({"error": "Некорректный Twitch-логин"}, status_code=400)
    try:
        return await run_in_threadpool(get_live_preview, name)
    except LookupError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except Exception as exc:
        print("[ADMIN TWITCH PREVIEW ERROR]", name, exc)
        return JSONResponse({"error": str(exc)}, status_code=502)

@router.get("/admin/api/streamer/{name}")
async def admin_get_streamer(name:str,request:Request):
    user=require_user(request)
    if not user: return JSONResponse({"error":"Требуется вход"},status_code=401)
    if not can_edit(user,name): return JSONResponse({"error":"Нет доступа к этому стримеру"},status_code=403)
    data=load_streamer(name)
    if not data: return JSONResponse({"error":"Стример не найден"},status_code=404)
    return data
@router.put("/admin/api/streamer/{name}")
async def admin_update_streamer(name:str,request:Request):
    user=require_user(request)
    if not user: return JSONResponse({"error":"Требуется вход"},status_code=401)
    if not can_edit(user,name): return JSONResponse({"error":"Нет доступа к этому стримеру"},status_code=403)
    try:
        data=await request.json()
        if not isinstance(data,dict): raise ValueError("Ожидается объект")
        original=load_streamer(name)
        if not original: return JSONResponse({"error":"Стример не найден"},status_code=404)
        data["name"] = original["name"]
        if user.get("role") != "admin":
            owner_id = original.get("tg_id")
            if owner_id in (None, ""):
                master = next((item for item in load_streamers()
                               if str(item.get("name", "")).lower() == name.lower()), None)
                owner_id = master.get("tg_id") if master else None
            data["tg_id"] = owner_id
        save_streamer(data); return {"ok":True}
    except (ValueError,TypeError) as exc:
        return JSONResponse({"ok":False,"error":str(exc)},status_code=400)

@router.get("/admin/api/settings/integrations")
async def admin_get_integration_settings(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Только администратор"}, status_code=403)
    return {"configured": integration_status()}

@router.put("/admin/api/settings/integrations")
async def admin_update_integration_settings(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Только администратор"}, status_code=403)
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Ожидается JSON-объект")
        values = data.get("values", {})
        clear = data.get("clear", [])
        if not isinstance(values, dict) or not isinstance(clear, list):
            raise ValueError("Некорректный формат настроек")
        allowed = {"telegram_token", "twitch_client_id", "twitch_client_secret", "twitch_bot_nick", "twitch_bot_id", "twitch_oauth", "discord_token", "lolka_token", "discord_channel_id", "lolka_channel_id"}
        if any(key not in allowed for key in values) or any(key not in allowed for key in clear):
            raise ValueError("Неизвестный параметр")
        if any(not isinstance(value, str) for value in values.values()):
            raise ValueError("Значения должны быть строками")
        saved = save_integration_settings(values, clear)
        return {"ok": True, "configured": {key: bool(saved.get(key) or os.getenv(env_name)) for key, env_name in {
            "telegram_token": "TELEGRAM_TOKEN", "twitch_client_id": "TWITCH_CLIENT_ID",
            "twitch_client_secret": "TWITCH_CLIENT_SECRET", "twitch_bot_nick": "TWITCH_BOT_NICK",
            "twitch_bot_id": "TWITCH_BOT_ID", "twitch_oauth": "TWITCH_OAUTH", "discord_token": "DISCORD_BOT_TOKEN", "lolka_token": "LOLKA_BOT_TOKEN",
            "discord_channel_id": "DISCORD_CHANNEL_ID", "lolka_channel_id": "LOLKA_CHANNEL_ID"
        }.items()}, "restart_required": True}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@router.post("/api/applications")
async def submit_application(request: Request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Некорректная заявка")
        twitch_login = str(data.get("twitch_login", "")).strip()
        contact = str(data.get("contact", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{1,50}", twitch_login):
            raise ValueError("Укажите корректный Twitch-логин")
        if not contact or len(contact) > 160:
            raise ValueError("Укажите контакт для обратной связи")
        platform = str(data.get("platform", "telegram"))
        if platform not in {"telegram", "discord", "lolka", "all"}:
            raise ValueError("Неизвестная платформа")
        items = load_json(APPLICATIONS_FILE)
        if not isinstance(items, list):
            items = []
        item = {"id": uuid.uuid4().hex[:12], "created_at": datetime.now(timezone.utc).isoformat(),
                "twitch_login": twitch_login, "contact": contact, "platform": platform,
                "channel": str(data.get("channel", "")).strip()[:200],
                "message": str(data.get("message", "")).strip()[:1000], "status": "new"}
        items.append(item)
        save_json(APPLICATIONS_FILE, items)
        return {"ok": True, "id": item["id"]}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@router.get("/admin/api/applications")
async def admin_applications(request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Только администратор"}, status_code=403)
    items = load_json(APPLICATIONS_FILE)
    return items if isinstance(items, list) else []

@router.post("/admin/api/applications/{application_id}/status")
async def admin_application_status(application_id: str, request: Request):
    user = require_user(request)
    if not user:
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    if user.get("role") != "admin":
        return JSONResponse({"error": "Только администратор"}, status_code=403)
    try:
        data = await request.json()
        status = str(data.get("status", ""))
        if status not in {"new", "reviewing", "accepted", "rejected"}:
            raise ValueError("Недопустимый статус")
        items = load_json(APPLICATIONS_FILE)
        if not isinstance(items, list):
            items = []
        target = next((x for x in items if x.get("id") == application_id), None)
        if target is None:
            return JSONResponse({"error": "Заявка не найдена"}, status_code=404)
        target["status"] = status
        save_json(APPLICATIONS_FILE, items)
        return {"ok": True}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

@router.get("/admin/api/users")
async def admin_list_users(request:Request):
    user=require_user(request)
    if not user: return JSONResponse({"error":"Требуется вход"},status_code=401)
    if user.get("role")!="admin": return JSONResponse({"error":"Только администратор"},status_code=403)
    return [{"username":x.get("username"),"role":x.get("role"),"streamers":x.get("streamers",[]),"enabled":x.get("enabled",True)} for x in load_users()]
@router.post("/admin/api/users")
async def admin_save_user(request:Request):
    actor=require_user(request)
    if not actor: return JSONResponse({"error":"Требуется вход"},status_code=401)
    if actor.get("role")!="admin": return JSONResponse({"error":"Только администратор"},status_code=403)
    try:
        data=await request.json(); username=str(data.get("username","")).strip(); role=str(data.get("role","user"))
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,40}",username): raise ValueError("Логин: 3–40 символов, латиница, цифры, . _ -")
        if role not in ("admin","user"): raise ValueError("Недопустимая роль")
        users=load_users(); target=next((x for x in users if x.get("username")==username),None)
        if not target: target={"username":username,"enabled":True}; users.append(target)
        target["role"]=role; target["streamers"]=sorted({str(x).lower() for x in data.get("streamers",[])})
        target["enabled"]=bool(data.get("enabled",True)); password=str(data.get("password",""))
        if password:
            if len(password)<10: raise ValueError("Пароль должен быть не короче 10 символов")
            target.pop("password_hash", None); target["password"]=password
        elif not target.get("password") and not target.get("password_hash"): raise ValueError("Для нового пользователя укажите пароль")
        save_users(users); return {"ok":True}
    except (ValueError,TypeError) as exc:
        return JSONResponse({"ok":False,"error":str(exc)},status_code=400)
@router.get("/preview/{name}")
async def preview(name: str, request: Request):
    user = require_user(request)
    if user:
        allowed = can_edit(user, name)
    else:
        allowed = telegram_owns_streamer(request, name) is not None
    if not allowed:
        return JSONResponse({"error": "Нет доступа к этому стримеру"}, status_code=403)
    streamer = load_streamer(name)
    if not streamer:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        twitch = get_streamer_status(name) or {}
    except Exception as exc:
        print("[WEBAPP TWITCH ERROR]", exc)
        twitch = {}
    return {"name": streamer.get("name", name), "url": f"https://twitch.tv/{name}",
            "title": twitch.get("title", ""), "game": twitch.get("game_name", ""),
            "viewer_count": twitch.get("viewer_count", 0), "started_at": twitch.get("started_at", ""),
            "thumbnail_url": twitch.get("thumbnail_url", ""), "offline": twitch.get("offline", True),
            "old_title": streamer.get("old_title", ""), "old_game": streamer.get("old_game", ""),
            "duration": streamer.get("duration", "0"), "peak_viewers": streamer.get("peak_viewers", 0)}
# Telegram Mini App endpoints require a valid Telegram-signed initData value.
@router.get("/twitch", include_in_schema=False)
@router.get("/twitch/", include_in_schema=False)
async def twitch_webapp_page(): return FileResponse(TWITCH_WEBAPP_HTML)

@router.get("/streamers")
async def streamers(request: Request):
    telegram_id = telegram_webapp_user_id(request)
    if telegram_id is None:
        return JSONResponse({"error": "Требуется авторизация Telegram"}, status_code=401)
    owned = []
    for item in load_streamers():
        if not item.get("name"):
            continue
        try:
            is_owner = int(item.get("tg_id", 0)) == telegram_id
        except (TypeError, ValueError):
            is_owner = False
        if is_owner:
            owned.append({"name": item["name"], "file": get_streamer_file(item["name"]).exists()})
    return owned

@router.get("/streamer/{name}")
async def get_streamer(name: str, request: Request):
    data = telegram_owns_streamer(request, name)
    if data is None:
        return JSONResponse({"error": "Нет доступа к этому стримеру"}, status_code=403)
    return data

@router.post("/streamer/{name}")
async def update_streamer(name: str, request: Request):
    original = telegram_owns_streamer(request, name)
    if original is None:
        return JSONResponse({"ok": False, "error": "Нет доступа к этому стримеру"}, status_code=403)
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return JSONResponse({"ok": False, "error": "JSON должен быть объектом"}, status_code=400)
        updated = dict(original)
        incoming_messages = data.get("messages")
        if isinstance(incoming_messages, dict):
            messages = dict(original.get("messages", {}))
            for key in ("start", "title_change", "game_change", "end"):
                value = incoming_messages.get(key)
                if isinstance(value, str):
                    messages[key] = value[:10000]
            updated["messages"] = messages
        if isinstance(data.get("preview"), bool):
            updated["preview"] = data["preview"]
        incoming_channels = data.get("channels")
        if isinstance(incoming_channels, list):
            requested = {}
            for channel in incoming_channels:
                if isinstance(channel, dict):
                    requested.setdefault(str(channel.get("chat_id", "")), []).append(channel)
            merged_channels = []
            for channel in original.get("channels", []):
                if not isinstance(channel, dict):
                    continue
                saved_channel = dict(channel)
                candidates = requested.get(str(channel.get("chat_id", "")), [])
                candidate = candidates.pop(0) if candidates else {}
                for field in ("notify_start", "notify_title_change", "notify_game_change", "notify_end"):
                    if isinstance(candidate.get(field), bool):
                        saved_channel[field] = candidate[field]
                merged_channels.append(saved_channel)
            updated["channels"] = merged_channels
        # name, tg_id, channel IDs and every other protected field come from server data.
        updated["name"] = original["name"]
        updated["tg_id"] = original.get("tg_id")
        save_streamer(updated)
        return {"ok": True, "file": f"{name}.json"}
    except (ValueError, TypeError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
