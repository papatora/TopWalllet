"""One-shot VPS query helper for the dynamic workflow (world.run).

Usage:
  python scripts/vps_query.py scores      -> wallet_scores count
  python scripts/vps_query.py labels      -> wallet_labels count
  python scripts/vps_query.py counts      -> all key table counts (json)
  python scripts/vps_query.py phase       -> supervisor phase/exit (json)
  python scripts/vps_query.py stage       -> last pipeline stage line
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "phase"
    ssh = _vps.connect()
    q = {
        "scores": "select count(*) from wallet_scores",
        "labels": "select count(*) from wallet_labels",
        "pp": "select count(*) from price_points",
    }
    if what in q:
        _, out, err = ssh.exec_command(
            f"cd /opt/topwallet && .venv/bin/python -c \"import sqlite3; "
            f"c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
            f"print(c.execute('{q[what]}').fetchone()[0])\"", timeout=60)
        print(out.read().decode().strip())
    elif what == "counts":
        _, out, _ = ssh.exec_command(
            "cd /opt/topwallet && .venv/bin/python -c \"import sqlite3, json; "
            "c=sqlite3.connect('file:data/topwallet.db?mode=ro',uri=True); "
            "print(json.dumps({t: c.execute(f'select count(*) from {t}').fetchone()[0] "
            "for t in ('tokens','wallets','swap_events','price_points',"
            "'wallet_scores','wallet_labels')}))\"", timeout=90)
        print(out.read().decode().strip())
    elif what == "phase":
        _, out, _ = ssh.exec_command(
            "cd /opt/topwallet && .venv/bin/python -c \"import json; "
            "s=json.load(open('results/supervisor_status.json')); "
            "print(json.dumps({'phase': s.get('phase'), 'exit': s.get('last_exit'), "
            "'updated': s.get('updated_at')}))\"", timeout=60)
        print(out.read().decode().strip())
    elif what == "stage":
        _, out, _ = ssh.exec_command(
            "grep -a 'stage:' /opt/topwallet/logs/supervisor_pipeline.log | tail -1",
            timeout=60)
        print(out.read().decode().strip())
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
