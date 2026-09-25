"""Cek status ronde (dipakai workflow verifikasi per-ronde). Output JSON.

Semua angka dari sumber nyata: DB VPS (via SSH), log sweep, state lokal.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def main() -> int:
    import _vps

    rep: dict = {}
    ssh = _vps.connect()

    def sh(cmd: str, t: int = 60) -> str:
        _, out, _ = ssh.exec_command(cmd, timeout=t)
        return out.read().decode(errors="replace").strip()

    q = ("cd /opt/topwallet && .venv/bin/python -c \""
         "import sqlite3; c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
         "q=lambda s: c.execute(s).fetchone()[0]; "
         "print(q('select max(ts) from swap_events')); "
         "print(q('select count(*) from swap_events')); "
         "print(q('select count(*) from wallets')); "
         "print(q('select count(*) from wallet_scores'))\"")
    lines = sh(q, 60).splitlines()
    if len(lines) == 4:
        rep.update({"swap_max_ts": lines[0], "swaps": int(lines[1]),
                    "wallets": int(lines[2]), "wallet_scores": int(lines[3])})
    rep["last_stage"] = sh("grep -a 'stage:' /opt/topwallet/logs/"
                           "supervisor_pipeline.log | tail -1")
    rep["cohort_log"] = sh("grep -a 'refresh cohort' /opt/topwallet/logs/"
                           "supervisor_pipeline.log | tail -1")
    rep["supervisor_alive"] = sh("ps aux | grep -c '[s]upervisor.py'") not in ("0", "")
    rep["sweep_alive"] = sh("ps aux | grep '[v]olume_sweep.py' | grep -v '/bin/sh' "
                            "| wc -l") not in ("0", "")
    # aktivitas track-ca & fired 2 jam terakhir
    rep["track_ca_recent"] = sh(
        "grep -aE 'track_ca_done|track_ca_error|track_ca_dropped' "
        "/opt/topwallet/results/volume_sweep_log.jsonl | tail -3")
    rep["fired_recent"] = sh(
        "grep -a '\"event\": \"fired\"' /opt/topwallet/results/volume_sweep_log.jsonl "
        "| tail -2")
    rep["queue_last"] = sh("grep -a 'queue_purged' /opt/topwallet/results/"
                           "volume_sweep_log.jsonl | tail -1")
    ssh.close()

    st_path = REPO / "results" / "night_state.json"
    try:
        rep["local_state"] = json.loads(st_path.read_text(encoding="utf-8"))
    except Exception:
        rep["local_state"] = {}

    rep["fresh"] = str(rep.get("swap_max_ts", "")) > "2026-09-17"
    rep["delta_done"] = bool(rep["local_state"].get("delta_done"))
    rep["delta_eligible"] = bool(rep["fresh"]) and not rep["delta_done"]
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
