"""Arkham harvest ORCHESTRATOR — runs as a background task.

Loop until the queue is exhausted (or CF hard-blocks us):
  harvester batch (--max 150) -> merge -> next batch

Emits results/arkham_status.json after every batch so any watcher sees live
progress. Exit code 0 = queue done; 1 = CF hard-block (needs human click).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "results" / "arkham_queue.json"
ENT = REPO / "results" / "arkham_entities.json"
STATUS = REPO / "results" / "arkham_status.json"
PY = sys.executable


def write_status(phase: str, extra: dict | None = None) -> None:
    try:
        done = len(json.loads(ENT.read_text(encoding="utf-8"))) if ENT.exists() else 0
    except (OSError, ValueError):
        done = 0
    try:
        total = len(json.loads(QUEUE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        total = 0
    st = {"phase": phase, "checked": done, "queue": total,
          "updated_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        st.update(extra)
    STATUS.write_text(json.dumps(st, indent=1), encoding="utf-8")


def main() -> int:
    write_status("running", {"batch": 0})
    batch = 0
    while True:
        batch += 1
        try:
            todo = sum(1 for a in json.loads(QUEUE.read_text(encoding="utf-8"))
                       if a not in json.loads(ENT.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            todo = 0
        if todo == 0:
            write_status("done", {"batch": batch})
            print(f"QUEUE EMPTY after {batch} batch(es)")
            return 0

        write_status("harvesting", {"batch": batch, "todo": todo})
        print(f"=== batch {batch}: {todo} tersisa ===", flush=True)
        r = subprocess.run(
            [PY, str(REPO / "scripts" / "arkham_harvest.py"),
             "--max", "150", "--pause-min", "5", "--pause-max", "8"],
            cwd=str(REPO), capture_output=True, text=True, timeout=3600)
        tail = (r.stdout or "").strip().splitlines()[-3:]
        for ln in tail:
            print("  |", ln, flush=True)

        hard_cf = "CF 5x beruntun" in (r.stdout or "")
        m = subprocess.run([PY, str(REPO / "scripts" / "arkham_merge.py")],
                           cwd=str(REPO), capture_output=True, text=True)
        print("  merge:", (m.stdout or "").strip(), flush=True)
        write_status("merged", {"batch": batch, "todo": todo, "hard_cf": hard_cf})

        if hard_cf:
            write_status("cf-blocked", {"batch": batch})
            print("CF hard-block — butuh klik manusia di window Brave")
            return 1
        time.sleep(20)  # jeda antar-batch, kasih CF ruang


if __name__ == "__main__":
    raise SystemExit(main())
