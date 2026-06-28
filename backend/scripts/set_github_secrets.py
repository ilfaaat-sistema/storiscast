#!/usr/bin/env python3
"""
Set GitHub repository secrets from .env for GitHub Actions workflows.

Usage:
  1. Add GITHUB_TOKEN to .env
     (get it at: https://github.com/settings/tokens → New token → repo scope)
  2. Run: cd backend && python scripts/set_github_secrets.py
"""
import os
import sys
import base64
import httpx
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.padding import OAEP
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_der_public_key
import json

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

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    print("❌  GITHUB_TOKEN не задан.")
    print("   Возьми на: https://github.com/settings/tokens")
    print("   Нужны права: repo (или только secrets:write если fine-grained)")
    sys.exit(1)

OWNER = "ilfaaat-sistema"
REPO  = "storiscast"
BASE  = f"https://api.github.com/repos/{OWNER}/{REPO}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Воркфлоу publish-worker.yml / insights-poller.yml только дёргают HTTP-эндпоинт
# /internal/trigger/* с заголовком x-internal-secret. Единственный нужный им секрет —
# INTERNAL_SECRET. Остальные секреты (БД, соц-токены) живут в env Render web-сервиса,
# а не в GitHub, чтобы не размазывать их по лишним местам.
SECRETS = {
    "INTERNAL_SECRET":         os.environ.get("INTERNAL_SECRET", ""),
}

# Get repo public key for secret encryption
r = httpx.get(f"{BASE}/actions/secrets/public-key", headers=HEADERS)
r.raise_for_status()
key_data = r.json()
key_id   = key_data["key_id"]
pub_key  = base64.b64decode(key_data["key"])

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
# GitHub uses libsodium sealed box — use PyNaCl if available, else fallback
try:
    from nacl.public import PublicKey, SealedBox
    def encrypt_secret(value: str) -> str:
        box = SealedBox(PublicKey(pub_key))
        return base64.b64encode(box.encrypt(value.encode())).decode()
except ImportError:
    print("⚠️  PyNaCl не установлен, ставлю...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyNaCl", "-q"])
    from nacl.public import PublicKey, SealedBox
    def encrypt_secret(value: str) -> str:
        box = SealedBox(PublicKey(pub_key))
        return base64.b64encode(box.encrypt(value.encode())).decode()

print(f"🔑  Устанавливаю {len(SECRETS)} секретов в {OWNER}/{REPO}...")
ok = 0
for name, value in SECRETS.items():
    if not value:
        print(f"   ⚪  {name} — пропущен (пустой)")
        continue
    encrypted = encrypt_secret(value)
    r = httpx.put(
        f"{BASE}/actions/secrets/{name}",
        headers={**HEADERS, "Content-Type": "application/json"},
        content=json.dumps({"encrypted_value": encrypted, "key_id": key_id}),
    )
    if r.status_code in (201, 204):
        print(f"   ✅  {name}")
        ok += 1
    else:
        print(f"   ❌  {name}: {r.status_code} {r.text[:100]}")

print(f"\n✅  Готово: {ok}/{len(SECRETS)} секретов установлено.")
print(f"   Воркфлоу запустятся автоматически:")
print(f"   https://github.com/{OWNER}/{REPO}/actions")
