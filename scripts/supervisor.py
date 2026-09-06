"""Overnight supervisor — keeps the TopWallet pipeline running unattended.

Responsibilities:
  1. Run pipeline stages (enrich→prices→analyze) with resume; skip stages
     that have nothing to do (no pending wallets / no fresh swaps).
  2. After each analyze: read results/stats.json; require top_wallets_count>0
     AND a fresh results/top_wallets_latest.json before declaring a cycle OK.
  3. Write a heartbeat to results/supervisor_status.json (extract progress in
     the morning from this file + logs/).
  4. Every CHECK_INTERVAL seconds, send a compact status to the ZAI
     GLM-5.3-flash endpoint (coding-plan base URL, key in .env ZAI_API_KEY)
     asking a one-glance health judgment; append to results/night_watch.log.
     The AI is a cheap watchdog, NOT the operator.
  5. Crash-safe: any exception → log, backoff, continue. Ctrl+C → clean exit.

Run:  python scripts/supervisor.py        (leave running overnight)
Stop: Ctrl+C (checkpoints make the pipeline resume-safe)
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
PY = str(REPO / ".venv" / "Scripts" / "python.exe") if os.name == "nt" else "python"

PIPELINE_CMD = [PY, "-m", "src.cli", "pipeline", "--stages", "enrich,prices,analyze"]
CHECK_INTERVAL = int(os.getenv("SUPERVISOR_CHECK_INTERVAL", "3600"))  # 1 hour
LOOP_SLEEP = 120          # between crash-retries
BACKOFF_MAX = 1800        # max crash backoff

ZAI_BASE = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4").rstrip("/")
ZAI_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_MODEL = os.getenv("ZAI_MODEL", "glm-5.3-flash")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(update: dict) -> None:
    status = {}
    if STATUS_FILE.exists():
        try:
            status = json.loads(STATUS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            status = {}
    status.update(update)
    status["updated_at"] = now_iso()
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2))


def tail(path: Path, n: int = 3) -> str:
    try:
        lines = path.read_text(errors="replace").strip().splitlines()
        return " | ".join(lines[-n:])[-400:]
    except OSError:
        return ""


def zai_watchdog(status: dict) -> str:
    """Ask GLM for a one-glance health judgment. Cheap: short prompt, 200 tokens."""
    if not ZAI_KEY:
        return "zai skipped (no ZAI_API_KEY)"
    import httpx

    brief = {
        "updated_at": status.get("updated_at"),
        "cycle": status.get("cycle"),
        "phase": status.get("phase"),
        "last_exit": status.get("last_exit"),
        "top_wallets": status.get("top_wallets"),
        "stats": status.get("stats"),
        "log_tail": status.get("log_tail"),
    }
    prompt = (
        "You are an unattended-jobs watchdog. Here is the TopWallet supervisor "
        f"status JSON: {json.dumps(brief)}. UTC now = {now_iso()}. "
        "Answer in ONE short line: 'OK: <why>' if work is progressing (recent "
        "updated_at, plausible phase), or 'PROBLEM: <why>' if stalled/failed "
        "(updated_at older than 30 min, repeated failures, empty results). "
        "No extra words."
    )
    try:
        resp = httpx.post(
            f"{ZAI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {ZAI_KEY}"},
            json={"model": ZAI_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 120},
            timeout=45,
        )
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        line = f"[{now_iso()}] {text}"
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return text
    except Exception as e:
        line = f"[{now_iso()}] watchdog error: {str(e)[:150]}"
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return line


def read_stats() -> dict:
    try:
        return json.loads((RESULTS / "stats.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def run_pipeline_cycle(cycle: int) -> None:
    write_status({"cycle": cycle, "phase": "pipeline", "last_exit": None,
                  "log_tail": tail(REPO / "logs" / "supervisor_pipeline.log", 2)})
    log_fh = open(REPO / "logs" / "supervisor_pipeline.log", "a", encoding="utf-8")
    proc = subprocess.Popen(PIPELINE_CMD, cwd=REPO, stdout=log_fh, stderr=subprocess.STDOUT)
    write_status({"pipeline_pid": proc.pid})
    while proc.poll() is None:
        time.sleep(30)
        write_status({"log_tail": tail(REPO / "logs" / "supervisor_pipeline.log", 2)})
    log_fh.close()

    stats = read_stats()
    ranked = stats.get("top_wallets_count", 0)
    write_status({
        "phase": "pipeline_done",
        "last_exit": proc.returncode,
        "top_wallets": ranked,
        "stats": stats.get("stage_counts"),
    })


def main() -> int:
    print(f"[supervisor] starting; status → {STATUS_FILE}", flush=True)
    write_status({"phase": "boot", "cycle": 0, "pid": os.getpid(),
                  "top_wallets": None, "last_exit": None})
    cycle = 0
    backoff = 60
    last_check = 0.0
    while True:
        cycle += 1
        try:
            run_pipeline_cycle(cycle)
            backoff = 60
        except Exception as e:
            write_status({"phase": "error", "error": str(e)[:300]})
            print(f"[supervisor] cycle {cycle} error: {e}", flush=True)

        status = json.loads(STATUS_FILE.read_text())
        if time.time() - last_check >= CHECK_INTERVAL:
            verdict = zai_watchdog(status)
            last_check = time.time()
            print(f"[supervisor] watchdog: {verdict}", flush=True)

        if status.get("phase") == "pipeline_done" and (status.get("top_wallets") or 0) > 0:
            print(f"[supervisor] cycle {cycle} OK: {status.get('top_wallets')} verified "
                  f"wallets. Sleeping {CHECK_INTERVAL}s.", flush=True)
            time.sleep(CHECK_INTERVAL)
        else:
            print(f"[supervisor] cycle {cycle} incomplete "
                  f"(exit={status.get('last_exit')}). Retrying in {backoff}s.", flush=True)
            time.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[supervisor] stopped by user", flush=True)
        write_status({"phase": "stopped_by_user"})
