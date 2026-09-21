"""One-shot: dump + split on the VPS, then download parts with MD5 verify.

Used by the dynamic workflow via world.run. Steps:
  1. VPS: extract_wallets.py (fresh labels) + dump_snapshot.py (atomic)
  2. VPS: split -b 6m
  3. local: SFTP get all parts, verify MD5 per part (NEVER trust sizes)
"""
import hashlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402

LOCAL = Path(__file__).resolve().parents[1] / "data"


def md5_local(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ssh = _vps.connect()

    def run(cmd: str, t: int = 600) -> str:
        _, out, err = ssh.exec_command(cmd, timeout=t)
        return (out.read().decode() + err.read().decode()).strip()

    # preflight: dump hanya berguna utk premis price asli kalau VPS punya points
    _, out, _ = ssh.exec_command(
        "cd /opt/topwallet && .venv/bin/python -c \"import sqlite3; "
        "c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
        "print(c.execute('select count(*) from price_points').fetchone()[0], "
        "c.execute('select count(*) from wallet_scores').fetchone()[0])\"", timeout=60)
    pp, ws = (out.read().decode().split() + ["0", "0"])[:2]
    print(f"[0/4] VPS price_points={pp} wallet_scores={ws}", flush=True)
    if pp == "0":
        print("PERINGATAN: price_points di VPS masih 0 — dump ini TIDAK akan "
              "mengaktifkan sparkline/Price chart/kalibrasi (semua USD est. tetap "
              "dari harga snapshot). Tunggu stage prices selesai atau jalankan "
              "scripts/vps_wait_scores.py dulu.", flush=True)

    print("[1/4] extract_wallets (fresh labels)...", flush=True)
    print(run("cd /opt/topwallet && TOPWALLET_RUN_ENV=vps "
              ".venv/bin/python scripts/extract_wallets.py 2>&1 | tail -1", 600))
    print("[2/4] dump atomik + split...", flush=True)
    run("cd /opt/topwallet && rm -f data/local_snapshot.sql.part* "
        "data/local_snapshot.sql.gz && setsid nohup .venv/bin/python "
        "scripts/dump_snapshot.py > logs/dump.log 2>&1 < /dev/null & echo launched")
    for _ in range(40):
        time.sleep(10)
        log = run("cat /opt/topwallet/logs/dump.log 2>/dev/null")
        if "lines=" in log:
            print("dump:", log.strip(), flush=True)
            break
    else:
        print("dump TIDAK selesai — cek logs/dump.log")
        return 1
    n = run("cd /opt/topwallet/data && rm -f local_snapshot.sql.part* && "
            "split -b 6m local_snapshot.sql.gz local_snapshot.sql.part && "
            "ls local_snapshot.sql.part* | wc -l")
    print("parts:", n, flush=True)

    print("[3/4] download + MD5 verify...", flush=True)
    sftp = ssh.open_sftp()

    def md5_remote(p: str) -> str:
        _, out, _ = ssh.exec_command(f"md5sum {p} | cut -d' ' -f1", timeout=120)
        return out.read().decode().strip()

    parts = sorted(f for f in sftp.listdir("/opt/topwallet/data")
                   if f.startswith("local_snapshot.sql.part"))
    for f in parts:
        dst = LOCAL / f
        for attempt in range(3):
            sftp.get(f"/opt/topwallet/data/{f}", str(dst))
            if md5_local(dst) == md5_remote(f"/opt/topwallet/data/{f}"):
                print(" ", f, "OK", flush=True)
                break
            print(" ", f, "retry", attempt + 1, flush=True)
        else:
            print("MD5 GAGAL terus:", f)
            return 1
    sftp.close()

    print("[4/4] VPS cleanup parts", flush=True)
    run("cd /opt/topwallet/data && rm -f local_snapshot.sql.part*")
    ssh.close()
    print("ALL PARTS MD5-VERIFIED — siap rebuild_local_db.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
