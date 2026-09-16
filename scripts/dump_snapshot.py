"""Selective DB dump for local-explorer sync — runs on the VPS.

Emits the full sqlite schema+data EXCEPT tables the explorer never reads
(block_timestamps, feed_events, wallet_token_interest) into
data/local_snapshot.sql.gz. Detached run:

  cd /opt/topwallet && setsid nohup .venv/bin/python scripts/dump_snapshot.py \\
      > logs/dump.log 2>&1 < /dev/null &

Split + download (lokal):
  split -b 6m data/local_snapshot.sql.gz data/local_snapshot.sql.part
  # SFTP get part* -> repo data/ -> python scripts/rebuild_local_db.py
"""
import gzip
import sqlite3
import time

SK = ("block_timestamps", "feed_events", "wallet_token_interest")
t0 = time.time()
src = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
src.execute("PRAGMA busy_timeout=30000")
n = 0
with gzip.open("/opt/topwallet/data/local_snapshot.sql.gz", "wb",
               compresslevel=6) as f:
    for line in src.iterdump():
        # iterdump statements can span physical lines (SQLAlchemy DDL is
        # multi-line) — filter at STATEMENT level, never per physical line.
        u = line.lstrip().upper()
        if u.startswith(("CREATE ", "DELETE FROM SQLITE_SEQUENCE",
                         "INSERT INTO SQLITE_SEQUENCE")):
            continue
        if any(k in line for k in SK):
            continue
        f.write((line + "\n").encode())
        n += 1
src.close()
print(f"lines={n} secs={time.time() - t0:.0f}")
