"""Rantai delta ekstraksi [VPS]->[PC] untuk malam — resumable + marker.

Langkah (semua idempoten, aman diulang):
  1. fetch_dump.py    — dump+split di VPS, download part + MD5 (resumable)
  2. rebuild_local_db.py — bangun DB baru -> validasi -> replace (old aman)
  3. validasi hasil: wallets >= 90k, swaps >= 442k, swap_max_ts > 2026-09-17
  4. update results/night_state.json (delta_done, swap_max_ts, ts)
  5. commit + push hasil (wallet_labels.json dsb.)

Pemakaian:  python scripts/night_delta.py
Exit 0 = sukses; selain itu = gagal (lihat output).
"""
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "results" / "night_state.json"
DB = REPO / "data" / "topwallet.db"


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def run_step(cmd: list[str], timeout_s: int) -> int:
    print(f"[delta] $ {' '.join(cmd)}", flush=True)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(REPO), timeout=timeout_s)
    print(f"[delta] exit={p.returncode} ({time.time()-t0:.0f}s)", flush=True)
    return p.returncode


def main() -> int:
    st = load_state()
    st["delta_started_at"] = datetime.now(timezone.utc).isoformat()
    st["delta_status"] = "running"
    save_state(st)

    if run_step([sys.executable, "scripts/fetch_dump.py"], 60 * 60) != 0:
        st["delta_status"] = "failed_fetch"
        save_state(st)
        return 1
    if run_step([sys.executable, "scripts/rebuild_local_db.py"], 30 * 60) != 0:
        st["delta_status"] = "failed_rebuild"
        save_state(st)
        return 1

    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    wallets = c.execute("select count(*) from wallets").fetchone()[0]
    swaps = c.execute("select count(*) from swap_events").fetchone()[0]
    max_ts = str(c.execute("select max(ts) from swap_events").fetchone()[0])
    scores = c.execute("select count(*) from wallet_scores").fetchone()[0]
    c.close()

    ok = wallets >= 90_000 and swaps >= 442_000 and max_ts > "2026-09-17"
    st.update({
        "delta_status": "done" if ok else "failed_validation",
        "delta_done": bool(ok),
        "wallets": wallets, "swaps": swaps,
        "swap_max_ts": max_ts, "wallet_scores": scores,
        "delta_finished_at": datetime.now(timezone.utc).isoformat(),
    })
    save_state(st)
    print(f"[delta] wallets={wallets} swaps={swaps} max_ts={max_ts} "
          f"scores={scores} -> {'OK' if ok else 'VALIDASI GAGAL'}", flush=True)

    if ok:
        tok = ""
        for line in (REPO / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("GITHUB_TOKEN="):
                tok = line.split("=", 1)[1].strip()
                break
        subprocess.run(["git", "add", "-f", "results/night_state.json",
                        "results/wallet_labels.json"], cwd=str(REPO))
        subprocess.run(["git", "commit", "-q",
                        "-m", f"chore(night): delta ekstraksi — swap_max_ts {max_ts}"],
                       cwd=str(REPO))
        subprocess.run(["git", "push", "-q",
                        f"https://x-access-token:{tok}@github.com/papatora/TopWalllet.git",
                        "main:main"], cwd=str(REPO))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
