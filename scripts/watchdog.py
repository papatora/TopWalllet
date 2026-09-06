"""Hourly LLM watchdog — runs on the VPS via cron, INDEPENDENT of the
supervisor (so it can revive the supervisor itself if it died).

Flow every hour (cron injects this request):
  1. Collect hard facts (no LLM): supervisor alive? pipeline alive? heartbeat
     (results/supervisor_status.json) fresher than 30 min? results sane?
  2. Inject a compact status into ZAI GLM-5.3-flash (coding-plan endpoint) and
     ask for a verdict as STRICT JSON: {"action": ..., "reason": "..."}
     Allowed actions: NONE | START_SUPERVISOR | RESTART_SUPERVISOR |
     RESTART_PIPELINE.
  3. Execute the whitelisted action (VPS only) — auto-restart whatever died.
  4. Append everything to results/night_watch.log. If all is fine (even slow),
     the AI just answers NONE/OK.

Cron line (VPS):
  0 * * * * cd /opt/topwallet && TOPWALLET_RUN_ENV=vps .venv/bin/python scripts/watchdog.py >> logs/watchdog_cron.log 2>&1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

RESULTS = REPO / "results"
STATUS_FILE = RESULTS / "supervisor_status.json"
WATCH_LOG = RESULTS / "night_watch.log"
PY = str(REPO / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else str(REPO / ".venv" / "bin" / "python")

ZAI_BASE = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4").rstrip("/")
ZAI_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_MODEL = os.getenv("ZAI_MODEL", "glm-5.3-flash")
RUN_ENV = os.getenv("TOPWALLET_RUN_ENV", "")
ALLOW_ACTIONS = RUN_ENV == "vps"  # actions only on the VPS; elsewhere: report-only

ALLOWED = {"NONE", "START_SUPERVISOR", "RESTART_SUPERVISOR", "RESTART_PIPELINE"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(line: str) -> None:
    with open(WATCH_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {line}\n")
    print(line, flush=True)


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def pgrep_alive(pattern: str) -> bool:
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        return out.returncode == 0
    except FileNotFoundError:
        # Windows dev box: use tasklist as a rough check
        try:
            out = subprocess.run(["tasklist"], capture_output=True, text=True)
            return pattern.split()[-1][:12] in out.stdout
        except Exception:
            return False


def collect_facts() -> dict:
    facts: dict = {"utc": now_iso(), "run_env": RUN_ENV or "unset"}
    status: dict = {}
    try:
        status = json.loads(STATUS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    facts["status_file"] = bool(status)
    if status:
        facts["supervisor_updated_at"] = status.get("updated_at")
        try:
            age_s = time.time() - datetime.fromisoformat(
                str(status.get("updated_at", "")).replace("Z", "+00:00")
            ).timestamp()
            facts["heartbeat_age_min"] = round(age_s / 60, 1)
            facts["heartbeat_fresh"] = age_s < 1800
        except ValueError:
            facts["heartbeat_fresh"] = False
        sup_pid = status.get("pid")
        pipe_pid = status.get("pipeline_pid")
        facts["supervisor_pid"] = sup_pid
        facts["supervisor_alive"] = pid_alive(sup_pid) or pgrep_alive("scripts/supervisor.py")
        facts["pipeline_alive"] = pid_alive(pipe_pid) if pipe_pid else pgrep_alive("src.cli pipeline")
        facts["phase"] = status.get("phase")
        facts["cycle"] = status.get("cycle")
        facts["top_wallets"] = status.get("top_wallets")
    else:
        facts["supervisor_alive"] = pgrep_alive("scripts/supervisor.py")
        facts["pipeline_alive"] = pgrep_alive("src.cli pipeline")
        facts["heartbeat_fresh"] = False
    return facts


def ask_llm(facts: dict) -> tuple[str, str]:
    brief = json.dumps({k: facts.get(k) for k in (
        "utc", "supervisor_alive", "pipeline_alive", "heartbeat_fresh",
        "heartbeat_age_min", "phase", "cycle", "top_wallets")})
    prompt = (
        "You are the overnight watchdog of an unattended data pipeline. "
        f"Status facts: {brief}. "
        "Decide ONE action. Rules: supervisor or pipeline dead OR heartbeat "
        "stale (>30min) → restart what is dead (START_SUPERVISOR if supervisor "
        "dead, RESTART_SUPERVISOR if supervisor alive but pipeline dead/stuck, "
        "RESTART_PIPELINE if only pipeline stuck). Everything alive and fresh "
        "→ NONE (working slowly is fine, do not restart for slowness). "
        'Reply ONLY strict JSON: {"action": "NONE|START_SUPERVISOR|'
        'RESTART_SUPERVISOR|RESTART_PIPELINE", "reason": "<=12 words"}'
    )
    import httpx

    try:
        resp = httpx.post(
            f"{ZAI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {ZAI_KEY}"},
            json={"model": ZAI_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 200},
            timeout=60,
        )
        text = resp.json()["choices"][0]["message"]["content"].strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return "NONE", f"unparseable LLM reply: {text[:80]}"
        verdict = json.loads(text[start:end + 1])
        action = str(verdict.get("action", "NONE")).upper()
        if action not in ALLOWED:
            action = "NONE"
        return action, str(verdict.get("reason", ""))[:120]
    except Exception as e:
        return "NONE", f"llm error: {str(e)[:120]}"


def execute(action: str) -> str:
    if not ALLOW_ACTIONS:
        return "skipped (not on VPS — report-only mode)"
    try:
        if action == "RESTART_SUPERVISOR":
            subprocess.run(["pkill", "-f", "scripts/supervisor.py"], capture_output=True)
            time.sleep(2)
        if action in ("START_SUPERVISOR", "RESTART_SUPERVISOR"):
            subprocess.Popen(
                [PY, "scripts/supervisor.py"],
                cwd=REPO,
                stdout=open(REPO / "logs" / "supervisor.log", "ab"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            return "supervisor started"
        if action == "RESTART_PIPELINE":
            subprocess.run(["pkill", "-f", "src.cli pipeline"], capture_output=True)
            return "pipeline killed (supervisor loop will relaunch it)"
    except Exception as e:
        return f"execute error: {str(e)[:120]}"
    return "none"


def main() -> int:
    facts = collect_facts()
    if not ZAI_KEY:
        log(f"watchdog skipped (no ZAI_API_KEY) facts={json.dumps(facts)}")
        return 0
    action, reason = ask_llm(facts)
    result = "report-only (local)" if not ALLOW_ACTIONS else execute(action)
    log(f"facts={json.dumps(facts)} | llm_action={action} ({reason}) | result={result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
