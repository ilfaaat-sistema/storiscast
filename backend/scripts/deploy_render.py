#!/usr/bin/env python3
"""
Deploy Storiscast to Render via API.

Usage:
  1. Add RENDER_API_KEY to your .env
     (get it at: https://dashboard.render.com/u/settings#api-keys)
  2. Run from project root:
     cd backend && python scripts/deploy_render.py
"""
import os
import sys
import httpx
from pathlib import Path

# ── Load .env files ────────────────────────────────────────────────────────
def _load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

root = Path(__file__).parent.parent.parent
_load_dotenv(root / ".env")
_load_dotenv(root / "frontend" / ".env.local")

RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
if not RENDER_API_KEY:
    print("❌  RENDER_API_KEY не задан.")
    print("   Возьми его на: https://dashboard.render.com/u/settings#api-keys")
    sys.exit(1)

BASE    = "https://api.render.com/v1"
HEADERS = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
REPO    = "https://github.com/ilfaaat-sistema/storiscast"
BRANCH  = "main"
REGION  = "frankfurt"

# ── Secrets ────────────────────────────────────────────────────────────────
def _e(k, d=""):
    return os.environ.get(k, d)

SECRETS = {
    "DATABASE_URL":            _e("DATABASE_URL"),
    "SUPABASE_URL":            _e("SUPABASE_URL"),
    "SUPABASE_SERVICE_KEY":    _e("SUPABASE_SERVICE_KEY"),
    "SUPABASE_STORAGE_BUCKET": _e("SUPABASE_STORAGE_BUCKET", "media"),
    "FERNET_KEY":              _e("FERNET_KEY"),
    "SUPABASE_JWT_SECRET":     _e("SUPABASE_JWT_SECRET"),
    "VK_ACCESS_TOKEN":         _e("VK_ACCESS_TOKEN"),
    "TG_API_ID":               _e("TG_API_ID"),
    "TG_API_HASH":             _e("TG_API_HASH"),
    "TG_SESSION_STRING":       _e("TG_SESSION_STRING"),
    "IG_ACCESS_TOKEN":         _e("IG_ACCESS_TOKEN"),
    "IG_USER_ID":              _e("IG_USER_ID"),
    "IG_GRAPH_API_VERSION":    _e("IG_GRAPH_API_VERSION", "v21.0"),
    "INTERNAL_SECRET":         _e("INTERNAL_SECRET"),
    "VITE_SUPABASE_ANON_KEY":  _e("VITE_SUPABASE_ANON_KEY", _e("SUPABASE_ANON_KEY")),
}

missing = [k for k in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "FERNET_KEY", "SUPABASE_JWT_SECRET")
           if not SECRETS[k]]
if missing:
    print(f"❌  Отсутствуют обязательные переменные: {', '.join(missing)}")
    sys.exit(1)

# ── API helpers ────────────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    r = httpx.request(method, f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    if r.status_code >= 400:
        print(f"   ⚠  {r.status_code}: {r.text[:400]}")
        r.raise_for_status()
    data = r.json()
    return data

def ev(*keys, extra: dict | None = None) -> list[dict]:
    items = [{"key": k, "value": SECRETS.get(k, "")} for k in keys]
    if extra:
        items += [{"key": k, "value": v} for k, v in extra.items()]
    return items

def get_existing(name: str) -> dict | None:
    svcs = api("GET", f"/services?name={name}&ownerId={owner_id}&limit=20")
    for s in svcs:
        if s["service"]["name"] == name:
            return s["service"]
    return None

def set_env(svc_id: str, vars_list: list[dict]):
    api("PUT", f"/services/{svc_id}/env-vars", json=vars_list)

def trigger_deploy(svc_id: str):
    api("POST", f"/services/{svc_id}/deploys", json={"clearCache": "do_not_clear"})

# ── Owner ──────────────────────────────────────────────────────────────────
print("🔑  Проверяю ключ...")
owners = api("GET", "/owners?limit=1")
owner_id = owners[0]["owner"]["id"]
print(f"   {owners[0]['owner']['name']} ({owner_id})")

EXTRA_BASE = {"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"}

# ── 1. storiscast-api (web service) ───────────────────────────────────────
print("\n📦  storiscast-api...")
svc = get_existing("storiscast-api")
if svc:
    api_id = svc["id"]
    print(f"   Уже существует: {api_id}")
else:
    body = {
        "type": "web_service",
        "name": "storiscast-api",
        "ownerId": owner_id,
        "repo": REPO,
        "branch": BRANCH,
        "autoDeploy": "yes",
        "envVars": ev(
            "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
            "SUPABASE_STORAGE_BUCKET", "FERNET_KEY", "SUPABASE_JWT_SECRET",
            extra=EXTRA_BASE,
        ),
        "serviceDetails": {
            "runtime": "python",
            "plan": "free",
            "region": REGION,
            "numInstances": 1,
            "envSpecificDetails": {
                "buildCommand": "cd backend && pip install -r requirements.txt && alembic upgrade head",
                "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            },
        },
    }
    r = api("POST", "/services", json=body)
    api_id = r["service"]["id"]
    print(f"   Создан: {api_id}")

# Воркеры запускаются ВНУТРИ web-сервиса через /internal/trigger, значит читают env
# web-сервиса — поэтому соц-токены (VK/TG/IG) тоже должны быть здесь, а не только в кронах.
set_env(api_id, ev(
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "SUPABASE_STORAGE_BUCKET", "FERNET_KEY", "SUPABASE_JWT_SECRET", "INTERNAL_SECRET",
    "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
    "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
    extra=EXTRA_BASE,
))
api_url = f"https://storiscast-api.onrender.com"
print(f"   URL: {api_url}")

CRON_ENV = ev(
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "SUPABASE_STORAGE_BUCKET", "FERNET_KEY",
    "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
    "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
    extra=EXTRA_BASE,
)

def create_cron(name: str, schedule: str, start_cmd: str) -> str | None:
    svc = get_existing(name)
    if svc:
        sid = svc["id"]
        print(f"   Уже существует: {sid}")
        set_env(sid, CRON_ENV)
        return sid
    try:
        body = {
            "type": "cron_job",
            "name": name,
            "ownerId": owner_id,
            "repo": REPO,
            "branch": BRANCH,
            "envVars": CRON_ENV,
            "serviceDetails": {
                "runtime": "python",
                "region": REGION,
                "schedule": schedule,
                "envSpecificDetails": {
                    "buildCommand": "cd backend && pip install -r requirements.txt",
                    "startCommand": start_cmd,
                },
            },
        }
        r = api("POST", "/services", json=body)
        sid = r["service"]["id"]
        print(f"   Создан: {sid}")
        return sid
    except Exception as e:
        print(f"   ⚠️  Не удалось: {e}")
        print(f"      Добавь карту на dashboard.render.com/billing, затем создай вручную.")
        return None

# ── 2. publish-worker (cron) ───────────────────────────────────────────────
print("\n⏱️   publish-worker...")
pw_id = create_cron("publish-worker", "*/2 * * * *", "cd backend && python -m cron.publish_worker")

# ── 3. insights-poller (cron) ──────────────────────────────────────────────
print("\n📊  insights-poller...")
ip_id = create_cron("insights-poller", "0 * * * *", "cd backend && python -m cron.insights_poller")

# ── 4. storiscast-ui (static site) ────────────────────────────────────────
print("\n🌐  storiscast-ui...")
svc = get_existing("storiscast-ui")
if svc:
    ui_id = svc["id"]
    print(f"   Уже существует: {ui_id}")
else:
    ui_env = [
        {"key": "VITE_SUPABASE_URL",     "value": SECRETS["SUPABASE_URL"]},
        {"key": "VITE_SUPABASE_ANON_KEY","value": SECRETS["VITE_SUPABASE_ANON_KEY"]},
        {"key": "VITE_API_URL",          "value": api_url},
    ]
    body = {
        "type": "static_site",
        "name": "storiscast-ui",
        "ownerId": owner_id,
        "repo": REPO,
        "branch": BRANCH,
        "autoDeploy": "yes",
        "envVars": ui_env,
        "serviceDetails": {
            "buildCommand": "cd frontend && npm install && npm run build",
            "staticPublishPath": "frontend/dist",
        },
    }
    r = api("POST", "/services", json=body)
    ui_id = r["service"]["id"]
    print(f"   Создан: {ui_id}")

set_env(ui_id, [
    {"key": "VITE_SUPABASE_URL",     "value": SECRETS["SUPABASE_URL"]},
    {"key": "VITE_SUPABASE_ANON_KEY","value": SECRETS["VITE_SUPABASE_ANON_KEY"]},
    {"key": "VITE_API_URL",          "value": api_url},
])

# ── Trigger deploys ────────────────────────────────────────────────────────
print("\n🚀  Запускаю деплои...")
for name, sid in [("storiscast-api", api_id), ("storiscast-ui", ui_id)] :
    try:
        trigger_deploy(sid)
        print(f"   ✅  {name}")
    except Exception as e:
        print(f"   ⚠️  {name}: {e}")

print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Готово!

   API:    {api_url}
   UI:     https://storiscast-ui.onrender.com
   Worker: каждые 2 мин
   Poller: каждый час

   Логи: https://dashboard.render.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
