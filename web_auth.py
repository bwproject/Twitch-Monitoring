from __future__ import annotations
import hashlib, hmac, json, os, secrets
from pathlib import Path
from typing import Any
BASE_DIR=Path(__file__).resolve().parent
DATA_DIR=Path(os.getenv("BOT_DATA_DIR",str(BASE_DIR/"data"))).resolve()
AUTH_DIR=DATA_DIR/"admin"
USERS_FILE=AUTH_DIR/"users.json"
SESSION_SECRET_FILE=AUTH_DIR/"session_secret"
def _hash_password(password: str, salt: str|None=None)->str:
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),310_000)
    return f"pbkdf2_sha256\${salt}\${digest.hex()}"
def verify_password(password: str, encoded: str)->bool:
    try:
        algorithm,salt,expected=encoded.split("$",2)
        if algorithm!="pbkdf2_sha256": return False
        actual=_hash_password(password,salt).split("$",2)[2]
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False
def _env_user(username,password,role,streamer=""):
    if not username or not password: return None
    return {"username":username,"password_hash":_hash_password(password),"role":role,
            "streamers":[x.strip().lower() for x in streamer.split(",") if x.strip()],"enabled":True}
def init_admin_storage():
    AUTH_DIR.mkdir(parents=True,exist_ok=True)
    if not SESSION_SECRET_FILE.exists():
        SESSION_SECRET_FILE.write_text(secrets.token_urlsafe(48),encoding="utf-8")
        try: SESSION_SECRET_FILE.chmod(0o600)
        except OSError: pass
    if USERS_FILE.exists(): return
    users=[]
    admin_name=os.getenv("WEB_ADMIN_USERNAME","admin").strip()
    admin_password=os.getenv("WEB_ADMIN_PASSWORD","")
    if not admin_password:
        admin_password=secrets.token_urlsafe(14)
        print(f"[WEB ADMIN] Сгенерирован пароль для {admin_name}: {admin_password}")
        print("[WEB ADMIN] Сохраните пароль сейчас; он не будет показан повторно.")
    users.append(_env_user(admin_name,admin_password,"admin"))
    for n in (1,2):
        username=os.getenv(f"WEB_USER{n}_USERNAME","").strip()
        password=os.getenv(f"WEB_USER{n}_PASSWORD","")
        streamers=os.getenv(f"WEB_USER{n}_STREAMERS","")
        if username and password: users.append(_env_user(username,password,"user",streamers))
    USERS_FILE.write_text(json.dumps({"users":users},ensure_ascii=False,indent=2),encoding="utf-8")
    try: USERS_FILE.chmod(0o600)
    except OSError: pass
def get_session_secret():
    init_admin_storage()
    return SESSION_SECRET_FILE.read_text(encoding="utf-8").strip()
def load_users():
    init_admin_storage()
    try:
        data=json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return data.get("users",[]) if isinstance(data,dict) else []
    except (OSError,ValueError): return []
def save_users(users):
    AUTH_DIR.mkdir(parents=True,exist_ok=True)
    temp=USERS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps({"users":users},ensure_ascii=False,indent=2),encoding="utf-8")
    try: temp.chmod(0o600)
    except OSError: pass
    temp.replace(USERS_FILE)
def authenticate(username,password):
    for user in load_users():
        if user.get("enabled",True) and hmac.compare_digest(str(user.get("username","")),username):
            if verify_password(password,user.get("password_hash","")):
                return {"username":user["username"],"role":user.get("role","user"),"streamers":user.get("streamers",[])}
    return None
