"""Check DB journal mode + size on VPS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402

ssh = _vps.connect()
_, o, e = ssh.exec_command(
    "cd /opt/topwallet && .venv/bin/python -c \""
    "import sqlite3; c=sqlite3.connect('data/topwallet.db', timeout=30);"
    "print('journal_mode:', c.execute('pragma journal_mode').fetchone());"
    "import os; print('size_mb:', round(os.path.getsize('data/topwallet.db')/1e6, 1))\" "
    "2>&1 | tail -3", timeout=60)
print(o.read().decode(), e.read().decode())
ssh.close()
