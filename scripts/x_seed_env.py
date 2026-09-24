"""Tanam sesi X utama (akun pertama yang hidup) ke /opt/topwallet/.env.

Ambil auth_token + ct0 dari /opt/xlogin/cookies.txt (hasil xlogin),
tulis X_USERNAME / X_AUTH_TOKEN / X_CT0 ke .env VPS — nilai TIDAK
di-print ke output. Jangan pernah commit file ini ke git.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
import _vps  # noqa: E402

ssh = _vps.connect()
_, out, _ = ssh.exec_command("cat /opt/xlogin/cookies.txt", timeout=30)
raw = out.read().decode("utf-8", "replace")

# blok per akun dipisah garis dashes; blok STATUS dan blok JSON terpisah
blocks = raw.split("----------------------------------------------------------------------")
primary = None
last_user = None
for b in blocks:
    m = re.search(r"AKUN:\s*(\S+)", b)
    if m:
        last_user = m.group(1)
    if "COOKIES_JSON_START" not in b:
        continue
    after = b.split("COOKIES_JSON_START", 1)[1]
    l, r = after.find("["), after.rfind("]")
    if l < 0 or r <= l:
        continue
    try:
        cookies = json.loads(after[l:r + 1])
    except Exception:
        continue
    names = {c.get("name"): c.get("value") for c in cookies if isinstance(c, dict)}
    if names.get("auth_token"):
        primary = {
            "username": last_user or "?",
            "auth_token": names["auth_token"],
            "ct0": names.get("ct0", ""),
        }
        break

if not primary:
    print("TIDAK KETEMU: blok cookie dengan auth_token+ct0")
    raise SystemExit(1)

env_line = (
    f"\nX_USERNAME={primary['username']}\n"
    f"X_AUTH_TOKEN={primary['auth_token']}\n"
    + (f"X_CT0={primary['ct0']}\n" if primary["ct0"] else "")
)
_, out, _ = ssh.exec_command(
    "grep -q '^X_AUTH_TOKEN=' /opt/topwallet/.env || printf '%s' '" +
    env_line.replace("'", "'\\''") + "' >> /opt/topwallet/.env; "
    "chmod 600 /opt/topwallet/.env; "
    "grep -c '^X_' /opt/topwallet/.env",
    timeout=30)
print(out.read().decode(errors="replace").strip())
ssh.close()
print(f"OK — sesi X utama ({primary['username']}) tertanam di [VPS] .env (nilai tak di-print)")
