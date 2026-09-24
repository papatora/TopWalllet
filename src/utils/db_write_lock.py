"""Kunci tulis lintas-proses (POSIX flock) untuk SQLite.

SQLite WAL hanya mengizinkan SATU writer; pipeline stage, sweep track-ca,
dan skrip cron lain yang menulis lama saling memblokir sampai busy_timeout
habis → 'database is locked' mematikan cycle (crash-loop 2026-09-24,
cycle 152-166). busy_timeout tidak menolong saat writer lain memegang
lock bermenit-menit, jadi satuan tulis berat diserialisasi lewat kunci
file ini secara deterministik:

- pipeline  : kunci per STAGE, lepas + jeda antar stage → beri giliran
              writer latar (sweep) di sela stage.
- track_by_ca: kunci per PEMANGGILAN run_track_by_ca (sweep & CLI).

Pembaca (explorer, dump, query) tidak terpengaruh — WAL. flock otomatis
lepas bila proses mati, jadi tidak ada kunci basi. Di Windows (dev/
unit-test) kunci menjadi no-op — pola sama dengan LOCK_FILE di
volume_sweep.
"""
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

LOCK_PATH = Path("data") / "db_write.lock"


@contextlib.asynccontextmanager
async def db_write_lock():
    try:
        import fcntl  # POSIX
    except ImportError:  # Windows dev — tanpa kunci
        yield
        return
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "w")

    def _acquire() -> None:
        # blocking: menunggu giliran tanpa poll; kernel melepas lock
        # otomatis bila pemegangnya mati.
        fcntl.flock(fh, fcntl.LOCK_EX)

    await asyncio.get_running_loop().run_in_executor(None, _acquire)
    try:
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()
