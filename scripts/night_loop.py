"""Night loop — watcher deterministik (jalan sebagai background task).

Setiap 5 menit:
  1. jalankan night_watch.py --act (cek VPS; delta otomatis bila syarat ok)
  2. cek aturan eskalasi deterministik -> bila butuh pertimbangan AI:
     tulis results/night_escalation.json lalu exit (notifikasi membangunkan
     sesi utama utk diagnosis/fix; setelah fix, sesi menjalankan loop lagi)
  3. bila SEMUA tuntas (delta_done + audit_done + git bersih + docs flag):
     tulis laporan akhir + `shutdown /s /t 600` (grace 10 menit)

Maks runtime 10 jam (MAX_HOURS) — setelah itu exit 9 tanpa shutdown.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "results" / "night_state.json"
ESCAL = REPO / "results" / "night_escalation.json"
AUDIT_DONE = REPO / "results" / "audit_done.json"
LOGVPS = Path("/opt/topwallet/logs/supervisor_pipeline.log")  # via SSH, bukan lokal

POLL_S = 300
MAX_HOURS = 10
FRESH_AFTER = "2026-09-17"
START = time.time()


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def escalate(code: int, reason: str, detail: str) -> int:
    save(ESCAL, {"code": code, "reason": reason, "detail": detail[:2000],
                 "at": datetime.now(timezone.utc).isoformat()})
    print(f"[night-loop] ESCALATE {code}: {reason}", flush=True)
    return code


def git_clean() -> bool:
    r = subprocess.run(["git", "status", "--porcelain"], cwd=str(REPO),
                       capture_output=True, text=True)
    # abaikan file yang memang berjalan (log, state)
    noisy = ("night_watch", "volume_sweep_log", "supervisor_status",
             "night_escalation", "night_state")
    lines = [l for l in r.stdout.splitlines()
             if not any(n in l for n in noisy)]
    return not lines


def all_done() -> tuple[bool, str]:
    st = load(STATE, {})
    audit = load(AUDIT_DONE, {})
    if not st.get("delta_done"):
        return False, "delta belum tuntas"
    if not audit.get("completed"):
        return False, "audit debat belum tuntas"
    if not git_clean():
        return False, "git masih kotor"
    return True, "semua tuntas"


def vps_quick() -> dict:
    sys.path.insert(0, str(REPO / "scripts"))
    import _vps
    ssh = _vps.connect()
    _, out, _ = ssh.exec_command(
        "cd /opt/topwallet && .venv/bin/python -c \""
        "import sqlite3; c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
        "print(c.execute('select max(ts) from swap_events').fetchone()[0])\" ; "
        "ps aux | grep -c '[s]upervisor.py'; "
        "grep -ac 'refresh cohort' /opt/topwallet/logs/supervisor_pipeline.log; "
        "grep -ac 'Traceback' /opt/topwallet/logs/supervisor_pipeline.log",
        timeout=60)
    lines = [l.strip() for l in out.read().decode(errors="replace").splitlines() if l.strip()]
    ssh.close()
    return {"swap_max_ts": lines[0] if lines else "", "sup": lines[1] if len(lines) > 1 else "0",
            "cohort_seen": int(lines[2]) if len(lines) > 2 else 0,
            "tracebacks": int(lines[3]) if len(lines) > 3 else 0}


def main() -> int:
    print("[night-loop] START — poll tiap 5 menit, maks 10 jam", flush=True)
    baseline = load(STATE, {})
    tb_baseline = baseline.get("traceback_baseline")
    restarts = 0
    first = True
    while True:
        if (time.time() - START) > MAX_HOURS * 3600:
            print("[night-loop] batas 10 jam tercapai — exit tanpa shutdown", flush=True)
            return 9
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            v = vps_quick()
        except Exception as e:
            print(f"[{ts}] VPS tidak terjangkau ({type(e).__name__}) — coba lagi polling berikutnya", flush=True)
            time.sleep(POLL_S)
            continue

        if first and tb_baseline is None:
            # poll pertama: hitungan traceback SAAT INI = baseline (log memuat
            # crash lama pra-fix — jangan dianggap anomali baru)
            tb_baseline = v["tracebacks"]
            st = load(STATE, {})
            st["traceback_baseline"] = tb_baseline
            save(STATE, st)
        first = False

        # --- aturan deterministik ---
        if int(v["sup"]) == 0:
            restarts += 1
            print(f"[{ts}] supervisor mati — restart (ke-{restarts})", flush=True)
            sys.path.insert(0, str(REPO / "scripts"))
            import _vps
            ssh = _vps.connect()
            ssh.exec_command("systemctl restart topwallet-supervisor", timeout=30)
            ssh.close()
            time.sleep(60)
            v2 = vps_quick()
            if int(v2["sup"]) == 0:
                return escalate(3, "supervisor mati walau sudah di-restart 2x",
                                json.dumps(v2))
        else:
            restarts = 0

        if v["tracebacks"] > tb_baseline:
            st = load(STATE, {})
            st["traceback_baseline"] = v["tracebacks"]
            save(STATE, st)
            return escalate(4, "Traceback baru di log pipeline VPS",
                            f"baseline={tb_baseline} sekarang={v['tracebacks']}")

        if not v["swap_max_ts"] or str(v["swap_max_ts"]) <= FRESH_AFTER:
            elapsed_h = (time.time() - START) / 3600
            if v["cohort_seen"] == 0 and elapsed_h > 3:
                return escalate(5, "3 jam berjalan, kohor refresh TIDAK terlihat di log",
                                json.dumps(v))
        else:
            print(f"[{ts}] swap FRESH: {v['swap_max_ts']}", flush=True)

        # --- delta otomatis bila eligible (night_watch --act menangani) ---
        st = load(STATE, {})
        if not st.get("delta_done") and str(v["swap_max_ts"]) > FRESH_AFTER:
            print(f"[{ts}] syarat delta terpenuhi — jalankan night_delta", flush=True)
            rc = subprocess.run([sys.executable, str(REPO / "scripts" / "night_delta.py")],
                                cwd=str(REPO)).returncode
            print(f"[{ts}] night_delta exit={rc}", flush=True)
            if rc != 0:
                return escalate(6, "night_delta gagal", f"exit={rc}")

        # --- selesai semua? ---
        done, why = all_done()
        if done:
            print("[night-loop] SEMUA TUNTAS — shutdown dalam 10 menit "
                  "(batalkan: shutdown /a)", flush=True)
            subprocess.run(["shutdown", "/s", "/t", "600"], cwd=str(REPO))
            return 0
        print(f"[{ts}] status: belum tuntas ({why}) — swap_max_ts={v['swap_max_ts']}", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    raise SystemExit(main())
