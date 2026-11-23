from __future__ import annotations
import json, re, os
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from web_auth import authenticate, get_session_secret, load_users, save_users
try:
    from bot3.twitch_api import get_streamer_status
except ImportError:
    from twitch_api import get_streamer_status
BASE_DIR=Path(__file__).resolve().parent
STREAMERS_FILE=BASE_DIR/"streamers.json"
ADMIN_HTML=BASE_DIR/"twitch"/"admin.html"
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
    return BASE_DIR/f"{name}.json"
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
async def landing_page(): return FileResponse(BASE_DIR / "index.html")

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
