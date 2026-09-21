"""Wait until [VPS] wallet_scores > 0 (analyze finished with the autoflush fix).

Usage: python scripts/vps_wait_scores.py [deadline_minutes]
Polls every 5 min with a FRESH SSH connection per poll (10054-safe).
Exit 0 = scores filled. Exit 1 = deadline reached, still 0.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def query() -> tuple[int, str]:
    import _vps

    ssh = _vps.connect()
    _, out, _ = ssh.exec_command(
        "cd /opt/topwallet && .venv/bin/python -c \"import sqlite3; "
        "c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
        "print(c.execute('select count(*) from wallet_scores').fetchone()[0])\"",
        timeout=60,
    )
    n = int(out.read().decode().strip() or 0)
    _, out2, _ = ssh.exec_command(
        "grep -a 'stage:' /opt/topwallet/logs/supervisor_pipeline.log | tail -1",
        timeout=60,
    )
    st = out2.read().decode().strip()[-60:]
    ssh.close()
    return n, st


def main() -> int:
    deadline_min = float(sys.argv[1]) if len(sys.argv) > 1 else 120
    deadline = time.time() + deadline_min * 60
    while time.time() < deadline:
        try:
            n, st = query()
            print(f"[{time.strftime('%H:%M')}] wallet_scores={n} | {st}", flush=True)
            if n > 0:
                print("ANALYZE SELESAI — scores terisi")
                return 0
        except Exception as e:
            print(f"[{time.strftime('%H:%M')}] conn err: {str(e)[:60]}", flush=True)
        time.sleep(300)
    print("DEADLINE — wallet_scores masih 0")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
