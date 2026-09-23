"""One-shot: dump + split on the VPS, then download parts with MD5 verify.

v2 RESILIENT (S-42): setiap langkah membuka koneksi SSH FRESH — satu
koneksi yg dipegang 10-40 menit pernah di-reset jaringan (10054) dan
mematikan seluruh proses di tengah download. Resumable: part yg sudah
terverifikasi MD5 tercatat di data/fetch_manifest.json dan dilewati.

Used by the dynamic workflow via world.run.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402

LOCAL = Path(__file__).resolve().parents[1] / "data"
MANIFEST = LOCAL / "fetch_manifest.json"
VPS_DATA = "/opt/topwallet/data"


def md5_local(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=1), encoding="utf-8")


def sh(cmd: str, t: int = 600) -> str:
    """Koneksi fresh + hard timeout: kembalikan output parsial saat habis,
    JANGAN tunggu EOF selamanya (perintah launch yang mem-background proses
    pernah menahan channel 10 menit -> PipeTimeout)."""
    import _vps
    ssh = _vps.connect()
    buf = b""
    try:
        chan = ssh.get_transport().open_session(timeout=min(t, 30))
        chan.settimeout(min(t, 30))
        chan.exec_command(cmd)
        end = time.time() + t
        while time.time() < end:
            if chan.recv_ready():
                buf += chan.recv(65536)
            elif chan.exit_status_ready():
                break
            time.sleep(0.2)
        try:
            while chan.recv_ready():
                buf += chan.recv(65536)
        except Exception:
            pass
    finally:
        try:
            ssh.close()
        except Exception:
            pass
    return buf.decode("utf-8", "replace").strip()


def main() -> int:
    manifest = load_manifest()

    pp, ws = sh("cd /opt/topwallet && .venv/bin/python -c \"import sqlite3; "
                "c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
                "print(c.execute('select count(*) from price_points').fetchone()[0], "
                "c.execute('select count(*) from wallet_scores').fetchone()[0])\"",
                90).split() or ("0", "0")
    print(f"[0/4] VPS price_points={pp} wallet_scores={ws}", flush=True)
    if pp == "0":
        print("PERINGATAN: price_points VPS masih 0 — dump ini tidak akan "
              "mengaktifkan sparkline/Price chart/kalibrasi.", flush=True)

    print("[1/4] extract_wallets (fresh labels)...", flush=True)
    print(sh("cd /opt/topwallet && TOPWALLET_RUN_ENV=vps .venv/bin/python "
             "scripts/extract_wallets.py 2>&1 | tail -1", 900), flush=True)

    print("[2/4] dump atomik (detached) + poll...", flush=True)
    sh("cd /opt/topwallet && rm -f data/local_snapshot.sql.part* "
       "data/local_snapshot.sql.gz && setsid nohup .venv/bin/python "
       "scripts/dump_snapshot.py > logs/dump.log 2>&1 < /dev/null "
       "& > /dev/null 2>&1", 20)
    for _ in range(60):  # maks 15 menit
        time.sleep(15)
        log = sh("cat /opt/topwallet/logs/dump.log 2>/dev/null", 30)
        if "lines=" in log:
            print("  dump:", log, flush=True)
            break
    else:
        print("dump tidak selesai dalam 15 menit — cek logs/dump.log")
        return 1

    print("[3/4] split...", flush=True)
    nparts = sh("cd /opt/topwallet/data && rm -f local_snapshot.sql.part* && "
                "split -b 6m local_snapshot.sql.gz local_snapshot.sql.part && "
                "ls local_snapshot.sql.part* | wc -l", 120)
    print("  parts:", nparts, flush=True)

    print("[4/4] download + MD5 (koneksi fresh per part)...", flush=True)
    parts = sorted(n for n in
                   sh("ls /opt/topwallet/data | grep -a 'local_snapshot.sql.part'",
                      60).splitlines() if n.strip())
    for f in parts:
        if manifest.get(f) == "verified":
            print(" ", f, "skip (sudah verified)")
            continue
        dst = LOCAL / f
        ok = False
        for attempt in range(5):
            try:
                ssh = _vps.connect()
                sftp = ssh.open_sftp()
                sftp.get(f"{VPS_DATA}/{f}", str(dst))
                _, out, _ = ssh.exec_command(
                    f"md5sum {VPS_DATA}/{f} | cut -d' ' -f1", timeout=120)
                remote = out.read().decode().strip()
                sftp.close()
                ssh.close()
                if md5_local(dst) == remote:
                    print(" ", f, "OK", flush=True)
                    manifest[f] = "verified"
                    save_manifest(manifest)
                    ok = True
                    break
                print(" ", f, f"retry {attempt + 1}: md5 mismatch", flush=True)
            except Exception as e:
                print(" ", f, f"retry {attempt + 1}: {str(e)[:60]}", flush=True)
                time.sleep(10)
        if not ok:
            print("GAGAL:", f, "— jalankan ulang skrip ini (resumable)")
            return 1

    print("ALL PARTS MD5-VERIFIED — jalankan scripts/rebuild_local_db.py "
          "lalu scripts/start_explorer.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
