"""S-34 finisher — run from repo root: .venv/Scripts/python.exe scripts/finish_s34.py

1. local backfill of USDG price_points (backup made first)
2. VPS: pull latest main, update GITHUB_TOKEN in /opt/topwallet/.env, restart
3. VPS: wait, then show supervisor status + any price-build errors

Needs VPS_HOST + VPS_PASSWORD (or VPS_SSH_KEY) in the local .env.
"""
import re
import subprocess
import sys
import time
from pathlib import Path

from _vps import connect

ROOT = Path(__file__).resolve().parents[1]
PAT_FILE = Path(r"C:\Users\ROG\Downloads\Telegram Desktop\github pat.txt")


def run(ssh, cmd, timeout=300):
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    text = (out.read() + err.read()).decode(errors="replace").strip()
    print(f"$ {cmd[:90]}\n{text}\n")
    return text


print("== 1. local backfill")
subprocess.run([sys.executable, str(ROOT / "scripts/backfill_quote_decimals.py"),
                "--db", str(ROOT / "data/topwallet.db"), "--apply"], check=False)

print("== 2. VPS deploy")
m = re.search(r"(github_pat_\w+|ghp_\w+)", PAT_FILE.read_text(encoding="utf-8"))
if not m:
    sys.exit(f"no PAT found in {PAT_FILE}")
ssh = connect()
run(ssh, "cd /opt/topwallet && git fetch -q origin && git reset --hard origin/main && git log --oneline -1")

sftp = ssh.open_sftp()
env_path = "/opt/topwallet/.env"
with sftp.open(env_path, "r") as f:
    lines = f.read().decode().splitlines()
lines = [l for l in lines if not l.startswith("GITHUB_TOKEN=")] + [f"GITHUB_TOKEN={m.group(1)}"]
with sftp.open(env_path, "w") as f:
    f.write("\n".join(lines) + "\n")
run(ssh, f"chmod 600 {env_path} && echo GITHUB_TOKEN updated")

run(ssh, "systemctl restart topwallet-supervisor && sleep 5 && systemctl is-active topwallet-supervisor")
print("waiting 90s for the first cycle…")
time.sleep(90)

print("== 3. health")
run(ssh, "head -12 /opt/topwallet/results/supervisor_status.json 2>/dev/null")
run(ssh, "grep -hE \"NameError|series build failed\" /opt/topwallet/logs/*.log 2>/dev/null | tail -8 || true")
run(ssh, "cd /opt/topwallet && .venv/bin/python -c \"import sqlite3;c=sqlite3.connect('data/topwallet.db');"
         "print('price_points:',c.execute('select count(*) from price_points').fetchone()[0])\"")
ssh.close()
print("DONE")
