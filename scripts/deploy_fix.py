"""VPS deploy fix pass: clone repo properly, rebuild venv, restart service."""
import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("78.31.250.202", port=22, username="root", password="lala123456", timeout=25)

def run(ssh, cmd, timeout=900, quiet=False):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        tail = (out + err).strip().splitlines()
        print(f"  [{code}] {cmd[:60]}  ->  " + (" | ".join(tail[-2:])[:150] if tail else "(empty)"))
    return code, out, err

print("1. install venv/pip packages…")
run(ssh, "apt-get update -qq && apt-get install -y -qq python3-venv python3-pip", timeout=600)

print("2. fetch repo into existing /opt/topwallet (keeps .env, logs, data)…")
run(ssh, "cd /opt/topwallet && rm -rf .git .venv && git init -q && git remote add origin https://github.com/papatora/TopWalllet.git && git fetch -q origin main && git reset --hard origin/main && ls | head -12", timeout=300)

print("3. rebuild venv + deps + tests…")
run(ssh, "cd /opt/topwallet && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python -m pytest -q 2>&1 | tail -1", timeout=900)

print("4. restart systemd service…")
run(ssh, "systemctl restart topwallet-supervisor && sleep 25 && systemctl is-active topwallet-supervisor")

print("5. verify heartbeat + first log lines…")
run(ssh, "head -10 /opt/topwallet/results/supervisor_status.json 2>/dev/null; echo ---; tail -3 /opt/topwallet/logs/supervisor.log 2>/dev/null; echo ---; tail -2 /opt/topwallet/logs/supervisor_pipeline.log 2>/dev/null | grep -v httpx | head -2")
run(ssh, "( crontab -l 2>/dev/null | grep watchdog.py ) && test -f /etc/systemd/system/topwallet-supervisor.service && echo SYSTEMD_OK")
ssh.close()
print("FIX PASS DONE")
