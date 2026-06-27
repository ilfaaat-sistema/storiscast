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
import time
import httpx
from pathlib import Path

# Load .env from project root and frontend/.env.local
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
    print("   Добавь строку RENDER_API_KEY=rnd_... в .env и запусти снова.")
    sys.exit(1)

BASE = "https://api.render.com/v1"
HEADERS = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
GITHUB_REPO = "https://github.com/ilfaaat-sistema/storiscast"
BRANCH = "main"
REGION = "frankfurt"

# ── Read secrets from env ──────────────────────────────────────────────────
def _e(key, default=""):
    v = os.environ.get(key, default)
    return v

SECRETS = {
    "DATABASE_URL":          _e("DATABASE_URL"),
    "SUPABASE_URL":          _e("SUPABASE_URL"),
    "SUPABASE_SERVICE_KEY":  _e("SUPABASE_SERVICE_KEY"),
    "SUPABASE_STORAGE_BUCKET": _e("SUPABASE_STORAGE_BUCKET", "media"),
    "FERNET_KEY":            _e("FERNET_KEY"),
    "SUPABASE_JWT_SECRET":   _e("SUPABASE_JWT_SECRET"),
    "VK_ACCESS_TOKEN":       _e("VK_ACCESS_TOKEN"),
    "TG_API_ID":             _e("TG_API_ID"),
    "TG_API_HASH":           _e("TG_API_HASH"),
    "TG_SESSION_STRING":     _e("TG_SESSION_STRING"),
    "IG_ACCESS_TOKEN":       _e("IG_ACCESS_TOKEN"),
    "IG_USER_ID":            _e("IG_USER_ID"),
    "IG_GRAPH_API_VERSION":  _e("IG_GRAPH_API_VERSION", "v21.0"),
}

missing = [k for k in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "FERNET_KEY", "SUPABASE_JWT_SECRET")
           if not SECRETS[k]]
if missing:
    print(f"❌  Отсутствуют обязательные переменные в .env: {', '.join(missing)}")
    sys.exit(1)


def api(method: str, path: str, **kwargs):
    r = httpx.request(method, f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    if r.status_code >= 400:
        print(f"   API error {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
    return r.json()


def env_vars(*keys, extra: dict | None = None) -> list[dict]:
    items = [{"key": k, "value": SECRETS.get(k, "")} for k in keys]
    if extra:
        items += [{"key": k, "value": v} for k, v in extra.items()]
    return items


# ── Get owner ID ───────────────────────────────────────────────────────────
print("🔑  Проверяю ключ и получаю owner ID...")
owners = api("GET", "/owners?limit=1")
if not owners:
    print("❌  Не удалось получить owner. Проверь RENDER_API_KEY.")
    sys.exit(1)
owner_id = owners[0]["owner"]["id"]
print(f"   Owner: {owners[0]['owner']['name']} ({owner_id})")


# ── Helper: create or find existing service ────────────────────────────────
def get_existing(name: str) -> dict | None:
    services = api("GET", f"/services?name={name}&ownerId={owner_id}&limit=10")
    for s in services:
        if s["service"]["name"] == name:
            return s["service"]
    return None


def set_env(service_id: str, vars_list: list[dict]):
    """PUT env vars for a service (replaces all)."""
    api("PUT", f"/services/{service_id}/env-vars", json=vars_list)


def trigger_deploy(service_id: str):
    api("POST", f"/services/{service_id}/deploys", json={"clearCache": "do_not_clear"})


# ── 1. storiscast-api (Web Service) ───────────────────────────────────────
print("\n📦  storiscast-api (web service)...")
svc = get_existing("storiscast-api")
if svc:
    api_id = svc["id"]
    print(f"   Уже существует: {api_id}")
else:
    payload = {
        "type": "web_service",
        "name": "storiscast-api",
        "ownerId": owner_id,
        "repo": GITHUB_REPO,
        "branch": BRANCH,
        "region": REGION,
        "plan": "free",
        "runtime": "python",
        "buildCommand": "cd backend && pip install -r requirements.txt && alembic upgrade head",
        "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
        "envVars": env_vars(
            "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
            "SUPABASE_STORAGE_BUCKET", "FERNET_KEY", "SUPABASE_JWT_SECRET",
            extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
        ),
    }
    result = api("POST", "/services", json=payload)
    api_id = result["service"]["id"]
    print(f"   Создан: {api_id}")

set_env(api_id, env_vars(
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "SUPABASE_STORAGE_BUCKET", "FERNET_KEY", "SUPABASE_JWT_SECRET",
    extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
))

# Get the public URL
svc_info = api("GET", f"/services/{api_id}")
api_url = f"https://{svc_info['serviceDetails']['url']}" if svc_info.get("serviceDetails", {}).get("url") else ""
print(f"   URL: {api_url or '(будет после деплоя)'}")


# ── 2. publish-worker (Cron) ───────────────────────────────────────────────
print("\n⏱️   publish-worker (cron)...")
svc = get_existing("publish-worker")
if svc:
    pw_id = svc["id"]
    print(f"   Уже существует: {pw_id}")
else:
    payload = {
        "type": "cron_job",
        "name": "publish-worker",
        "ownerId": owner_id,
        "repo": GITHUB_REPO,
        "branch": BRANCH,
        "region": REGION,
        "plan": "free",
        "runtime": "python",
        "buildCommand": "cd backend && pip install -r requirements.txt",
        "startCommand": "cd backend && python -m cron.publish_worker",
        "schedule": "*/2 * * * *",
        "envVars": env_vars(
            "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
            "SUPABASE_STORAGE_BUCKET", "FERNET_KEY",
            "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
            "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
            extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
        ),
    }
    result = api("POST", "/services", json=payload)
    pw_id = result["service"]["id"]
    print(f"   Создан: {pw_id}")

set_env(pw_id, env_vars(
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "SUPABASE_STORAGE_BUCKET", "FERNET_KEY",
    "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
    "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
    extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
))


# ── 3. insights-poller (Cron) ──────────────────────────────────────────────
print("\n📊  insights-poller (cron)...")
svc = get_existing("insights-poller")
if svc:
    ip_id = svc["id"]
    print(f"   Уже существует: {ip_id}")
else:
    payload = {
        "type": "cron_job",
        "name": "insights-poller",
        "ownerId": owner_id,
        "repo": GITHUB_REPO,
        "branch": BRANCH,
        "region": REGION,
        "plan": "free",
        "runtime": "python",
        "buildCommand": "cd backend && pip install -r requirements.txt",
        "startCommand": "cd backend && python -m cron.insights_poller",
        "schedule": "0 * * * *",
        "envVars": env_vars(
            "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
            "SUPABASE_STORAGE_BUCKET", "FERNET_KEY",
            "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
            "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
            extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
        ),
    }
    result = api("POST", "/services", json=payload)
    ip_id = result["service"]["id"]
    print(f"   Создан: {ip_id}")

set_env(ip_id, env_vars(
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "SUPABASE_STORAGE_BUCKET", "FERNET_KEY",
    "VK_ACCESS_TOKEN", "TG_API_ID", "TG_API_HASH", "TG_SESSION_STRING",
    "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_GRAPH_API_VERSION",
    extra={"DEFAULT_TENANT_ID": "00000000-0000-0000-0000-000000000001"},
))


# ── 4. storiscast-ui (Static Site) ────────────────────────────────────────
print("\n🌐  storiscast-ui (static site)...")
vite_api_url = api_url or input("   Введи URL API (напр. https://storiscast-api.onrender.com): ").strip()

svc = get_existing("storiscast-ui")
if svc:
    ui_id = svc["id"]
    print(f"   Уже существует: {ui_id}")
else:
    payload = {
        "type": "static_site",
        "name": "storiscast-ui",
        "ownerId": owner_id,
        "repo": GITHUB_REPO,
        "branch": BRANCH,
        "region": REGION,
        "buildCommand": "cd frontend && npm install && npm run build",
        "staticPublishPath": "frontend/dist",
        "envVars": [
            {"key": "VITE_SUPABASE_URL",    "value": SECRETS["SUPABASE_URL"]},
            {"key": "VITE_SUPABASE_ANON_KEY", "value": _e("SUPABASE_ANON_KEY", _e("VITE_SUPABASE_ANON_KEY"))},
            {"key": "VITE_API_URL",          "value": vite_api_url},
        ],
    }
    result = api("POST", "/services", json=payload)
    ui_id = result["service"]["id"]
    print(f"   Создан: {ui_id}")

# Update env vars with final API url
set_env(ui_id, [
    {"key": "VITE_SUPABASE_URL",      "value": SECRETS["SUPABASE_URL"]},
    {"key": "VITE_SUPABASE_ANON_KEY", "value": _e("SUPABASE_ANON_KEY", _e("VITE_SUPABASE_ANON_KEY"))},
    {"key": "VITE_API_URL",           "value": vite_api_url},
])


# ── Trigger deploys ────────────────────────────────────────────────────────
print("\n🚀  Запускаю деплои...")
for name, sid in [("storiscast-api", api_id), ("storiscast-ui", ui_id)]:
    try:
        trigger_deploy(sid)
        print(f"   ✅  {name} — деплой запущен")
    except Exception as e:
        print(f"   ⚠️  {name} — {e}")

print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅  Готово! Сервисы на Render:

   API:     {api_url or 'https://storiscast-api.onrender.com'}
   UI:      https://storiscast-ui.onrender.com (через ~3 мин)
   Worker:  каждые 2 мин
   Poller:  каждый час

   Следи за логами: https://dashboard.render.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
