from __future__ import annotations
import json, re, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware
from web.auth import authenticate, get_session_secret, load_users, save_users
from runtime_status import snapshot as runtime_status_snapshot
from runtime_config import save_integration_settings, integration_status
try:
    from bot3.twitch_api import get_streamer_status, get_live_preview
except ImportError:
    from twitch_api import get_streamer_status, get_live_preview
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
def current_user(request): return request.session.get("user")
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
    return bool(user and (user.get("role")=="admin" or name.lower() in user.get("streamers",[])))
@router.get("/", include_in_schema=False)
async def landing_page(): return FileResponse(TEMPLATES_DIR / "index.html")

@router.get("/status", include_in_schema=False)
async def public_status():
    status = runtime_status_snapshot()
    return {
        "telegram": {"state": status["telegram"]["state"], "label": status["telegram"].get("label")},
        "twitch_chat": {"state": status["twitch_chat"]["state"], "username": status["twitch_chat"].get("username"), "channels": status["twitch_chat"].get("channels", [])},
        "twitch_monitor": {"state": status["twitch_monitor"]["state"], "last_check": status["twitch_monitor"].get("last_check")},
    }

@router.get("/admin/api/status")
async def admin_runtime_status(request: Request):
    if not require_user(request):
        return JSONResponse({"error": "Требуется вход"}, status_code=401)
    return runtime_status_snapshot()

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
    items=load_streamers()
    if user.get("role")!="admin":
        allowed=set(user.get("streamers",[])); items=[x for x in items if str(x.get("name","")).lower() in allowed]
    return [{"name":x.get("name")} for x in items if x.get("name")]

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
        data["name"]=original["name"]
        if user.get("role")!="admin": data["tg_id"]=original.get("tg_id")
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
        allowed = {"telegram_token", "twitch_client_id", "twitch_client_secret", "twitch_bot_nick", "twitch_bot_id", "twitch_oauth", "discord_token", "lolka_token"}
        if any(key not in allowed for key in values) or any(key not in allowed for key in clear):
            raise ValueError("Неизвестный параметр")
        if any(not isinstance(value, str) for value in values.values()):
            raise ValueError("Значения должны быть строками")
        saved = save_integration_settings(values, clear)
        return {"ok": True, "configured": {key: bool(saved.get(key) or os.getenv(env_name)) for key, env_name in {
            "telegram_token": "TELEGRAM_TOKEN", "twitch_client_id": "TWITCH_CLIENT_ID",
            "twitch_client_secret": "TWITCH_CLIENT_SECRET", "twitch_bot_nick": "TWITCH_BOT_NICK",
            "twitch_bot_id": "TWITCH_BOT_ID", "twitch_oauth": "TWITCH_OAUTH", "discord_token": "DISCORD_BOT_TOKEN", "lolka_token": "LOLKA_BOT_TOKEN"
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
async def preview(name:str):
    streamer=load_streamer(name)
    if not streamer: return JSONResponse({"error":"not found"},status_code=404)
    try: twitch=get_streamer_status(name) or {}
    except Exception as exc: print("[WEBAPP TWITCH ERROR]",exc); twitch={}
    return {"name":streamer.get("name",name),"url":f"https://twitch.tv/{name}","title":twitch.get("title",""),
            "game":twitch.get("game_name",""),"viewer_count":twitch.get("viewer_count",0),"started_at":twitch.get("started_at",""),
            "thumbnail_url":twitch.get("thumbnail_url",""),"offline":twitch.get("offline",True),
            "old_title":streamer.get("old_title",""),"old_game":streamer.get("old_game",""),
            "duration":streamer.get("duration","0"),"peak_viewers":streamer.get("peak_viewers",0)}
# Existing Telegram Mini App API retained.
@router.get("/twitch", include_in_schema=False)
@router.get("/twitch/", include_in_schema=False)
async def twitch_webapp_page(): return FileResponse(TWITCH_WEBAPP_HTML)

@router.get("/streamers")
async def streamers():
    return [{"name":x.get("name"),"file":get_streamer_file(x["name"]).exists()} for x in load_streamers() if x.get("name")]
@router.get("/streamer/{name}")
async def get_streamer(name:str):
    data=load_streamer(name)
    return data if data else JSONResponse({"error":"not found"},status_code=404)
@router.post("/streamer/{name}")
async def update_streamer(name:str,request:Request):
    try:
        data=await request.json()
        if not isinstance(data,dict): return JSONResponse({"ok":False,"error":"JSON must object"},status_code=400)
        data["name"]=name; save_streamer(data); return {"ok":True,"file":f"{name}.json"}
    except Exception as exc: return JSONResponse({"ok":False,"error":str(exc)},status_code=500)
