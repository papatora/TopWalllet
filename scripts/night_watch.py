"""Night watch checker — deterministik, report-only tanpa --act.

Mengumpulkan status [VPS] + [PC] dan mencetak JSON untuk diinterpretasi
agent (cron watcher). Dengan --act: menjalankan langkah mekanis yang aman
(delta ekstraksi bila syarat terpenuhi; restart supervisor bila mati).

ANTI-HALU: semua angka berasal dari query/berkas nyata, bukan asumsi.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import _vps  # noqa: E402

STATE = REPO / "results" / "night_state.json"
FRESH_AFTER = "2026-09-17"   # swap_max_ts harus di atas ini = refresh bekerja
ACT = "--act" in sys.argv


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def vps_status() -> dict:
    st: dict = {}
    try:
        ssh = _vps.connect()
        q = ("cd /opt/topwallet && .venv/bin/python -c \""
             "import sqlite3; c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
             "q=lambda s: c.execute(s).fetchone()[0]; "
             "print(q('select count(*) from wallets')); "
             "print(q('select count(*) from swap_events')); "
             "print(q('select max(ts) from swap_events')); "
             "print(q('select count(*) from wallet_scores'))\"")
        _, out, _ = ssh.exec_command(q, timeout=60)
        lines = out.read().decode(errors="replace").strip().splitlines()
        if len(lines) == 4:
            st.update({"wallets": int(lines[0]), "swaps": int(lines[1]),
                       "swap_max_ts": lines[2], "wallet_scores": int(lines[3])})
        _, out, _ = ssh.exec_command(
            "grep -aE 'refresh cohort' /opt/topwallet/logs/supervisor_pipeline.log | tail -1; "
            "grep -a 'stage:' /opt/topwallet/logs/supervisor_pipeline.log | tail -1; "
            "ps aux | grep -c '[s]upervisor.py'; ps aux | grep -c '[v]olume_sweep.py'",
            timeout=60)
        lines = [l for l in out.read().decode(errors="replace").strip().splitlines() if l.strip()]
        st["cohort_log"] = next((l for l in lines if "refresh cohort" in l), "")
        st["last_stage"] = next((l for l in lines if "stage:" in l), "")
        st["supervisor_alive"] = any("supervisor.py" in l for l in lines[2:])
        st["sweep_alive"] = any(l.strip().endswith(("/1", "/2")) and "volume_sweep" in l for l in lines)
        ssh.close()
    except Exception as e:
        st["vps_error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return st


def local_status() -> dict:
    import sqlite3
    st: dict = {"night_state": load_state()}
    try:
        c = sqlite3.connect(f"file:{REPO / 'data' / 'topwallet.db'}?mode=ro", uri=True)
        st["local_swap_max_ts"] = str(c.execute("select max(ts) from swap_events").fetchone()[0])
        c.close()
    except Exception as e:
        st["local_db_error"] = str(e)[:120]
    return st


def main() -> int:
    rep = {"checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
           "vps": vps_status(), "local": local_status(),
           "fresh_threshold": FRESH_AFTER}
    v = rep["vps"]
    rep["supervisor_alive"] = v.get("supervisor_alive", False)
    rep["swap_fresh"] = str(v.get("swap_max_ts", "")) > FRESH_AFTER
    rep["cohort_seen"] = bool(v.get("cohort_log"))
    rep["delta_eligible"] = bool(rep["swap_fresh"]) and not rep["local"]["night_state"].get("delta_done")

    if ACT:
        if not rep["supervisor_alive"]:
            try:
                ssh = _vps.connect()
                ssh.exec_command("systemctl restart topwallet-supervisor", timeout=30)
                ssh.close()
                rep["acted"] = rep.get("acted", []) + ["restart supervisor"]
            except Exception as e:
                rep["acted"] = rep.get("acted", []) + [f"restart gagal: {e}"]
        if rep["delta_eligible"]:
            rc = subprocess.run([sys.executable, str(REPO / "scripts" / "night_delta.py")],
                                cwd=str(REPO)).returncode
            rep["acted"] = rep.get("acted", []) + [f"night_delta exit={rc}"]
            rep["delta_exit"] = rc
            rep["local"]["night_state"] = load_state()

    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    main()
