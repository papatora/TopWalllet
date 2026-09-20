"""CF watcher — bg task yang memberi notifikasi (exit) saat panen Arkham
membutuhkan campur tangan:

  exit 0 + "PHASE=done"       — panen tuntas semua
  exit 1 + "PHASE=cf-blocked" — CF hard-block 5x tanpa progress → butuh
                                klik manusia di window Brave (solver 2captcha
                                sudah mencoba otomatis dan kalah)
  exit 2                      — timeout pantau (panen masih jalan normal)

Poll tiap 60s ke results/arkham_status.json (file lokal, murah).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATUS = REPO / "results" / "arkham_status.json"
MAX_HOURS = 6


def read_phase() -> tuple[str, dict]:
    try:
        st = json.loads(STATUS.read_text(encoding="utf-8"))
        return st.get("phase", "?"), st
    except (OSError, ValueError):
        return "?", {}


def main() -> int:
    t0 = time.time()
    while time.time() - t0 < MAX_HOURS * 3600:
        phase, st = read_phase()
        if phase == "done":
            print("PHASE=done", json.dumps(st))
            return 0
        if phase == "cf-blocked":
            print("PHASE=cf-blocked", json.dumps(st))
            return 1
        time.sleep(60)
    phase, st = read_phase()
    print(f"PHASE={phase} (timeout pantau {MAX_HOURS} jam)", json.dumps(st))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
