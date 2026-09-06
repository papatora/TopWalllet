"""One-shot VPS deployment for TopWallet (reads secrets from local files only)."""
import sys, time, json, re
import paramiko

HOST, PORT, USER, PASS = "78.31.250.202", 22, "root", "lala123456"

# local .env values to replicate on the VPS
env = {}
for line in open(".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

REMOTE_ENV = f"""TOPWALLET_RUN_ENV=vps
CHAIN=robinhood
CHAIN_ID=4663
DATABASE_URL=sqlite+aiosqlite:////opt/topwallet/data/topwallet.db
EVM_RPC_ENDPOINTS={env.get('EVM_RPC_ENDPOINTS','https://rpc.mainnet.chain.robinhood.com')}
BLOCKSCOUT_API_URL=https://robinhoodchain.blockscout.com
BLOCKSCOUT_RPS=8
GITHUB_REPO=papatora/TopWalllet
GITHUB_TOKEN={env.get('GITHUB_TOKEN','')}
GITHUB_BRANCH=main
AUTO_PUSH_RESULTS=true
ZAI_BASE_URL={env.get('ZAI_BASE_URL','https://api.z.ai/api/coding/paas/v4')}
ZAI_MODEL=glm-5.3-flash
ZAI_API_KEY={env.get('ZAI_API_KEY','')}
GETLOGS_START_WINDOW=2000000
SAFE_LOG_LAG_BLOCKS=50000
PRICE_LOOKBACK_DAYS=45
PRICE_MAX_CLUSTERS_PER_POOL=60
PRICE_MAX_CALLS_PER_POOL=120
ENRICH_CONCURRENCY=4
ENRICH_MAX_PAGES_PER_WALLET=6
MAX_TOKENS=100
"""

def run(ssh, cmd, timeout=600, quiet=False):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        tail = (out + err).strip().splitlines()
        print(f"  [{code}] {cmd[:70]}  ->  " + (" | ".join(tail[-2:])[:160] if tail else "(empty)"))
    return code, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("connecting…")
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=25)
print("connected.")

run(ssh, "uname -m && grep PRETTY /etc/os-release && python3 --version && nproc && df -h / | tail -1")
run(ssh, "git --version || (apt-get update -qq && apt-get install -y -qq git python3-venv python3-pip)", timeout=600)
run(ssh, "mkdir -p /opt/topwallet/logs /opt/topwallet/data /opt/topwallet/results")
code, _, _ = run(ssh, "test -d /opt/topwallet/.git && echo yes || echo no", quiet=True)
if code == 0:
    run(ssh, "cd /opt/topwallet && git config --global --add safe.directory /opt/topwallet && git fetch origin && git reset --hard origin/main")
else:
    run(ssh, "git clone https://github.com/papatora/TopWalllet.git /opt/topwallet", timeout=300)

# write .env via SFTP (not shell history)
sftp = ssh.open_sftp()
with sftp.open("/opt/topwallet/.env", "w") as f:
    f.write(REMOTE_ENV)
print("  .env written (secrets via SFTP)")
run(ssh, "chmod 600 /opt/topwallet/.env")

print("venv + deps (2-5 min)…")
run(ssh, "cd /opt/topwallet && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python -m pytest -q", timeout=900)

print("systemd + cron…")
unit = """[Unit]
Description=TopWallet overnight supervisor
After=network-online.target

[Service]
WorkingDirectory=/opt/topwallet
Environment=TOPWALLET_RUN_ENV=vps
ExecStart=/opt/topwallet/.venv/bin/python scripts/supervisor.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
"""
with sftp.open("/etc/systemd/system/topwallet-supervisor.service", "w") as f:
    f.write(unit)
run(ssh, "systemctl daemon-reload && systemctl enable --now topwallet-supervisor")
run(ssh, "( crontab -l 2>/dev/null | grep -v watchdog.py ; echo '0 * * * * cd /opt/topwallet && TOPWALLET_RUN_ENV=vps .venv/bin/python scripts/watchdog.py >> logs/watchdog_cron.log 2>&1' ) | crontab - && crontab -l | tail -1")

print("waiting 30s for first heartbeat…")
time.sleep(30)
run(ssh, "systemctl is-active topwallet-supervisor && cat /opt/topwallet/results/supervisor_status.json | head -8")
run(ssh, "tail -4 /opt/topwallet/logs/supervisor.log; tail -2 /opt/topwallet/logs/supervisor_pipeline.log | grep -v httpx | head -2")
ssh.close()
print("DEPLOY DONE — VPS is autonomous.")
