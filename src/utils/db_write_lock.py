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
        # S-45f: polling LOCK_NB + jitter — blocking flock TIDAK FIFO:
        # pemenang commit terus-menerus (sweep) bisa mem-menangkan balapan
        # selamanya melawan waiter blocking (pipeline/track-ca kelaparan,
        # py-spy 2026-09-25 16:47). Polling membuat semua pelaku setara;
        # waiter menang dalam hitungan detik karena lock dipegang hitungan
        # milidetik per commit.
        import os
        import time
        jitter = 0.15 + (os.getpid() % 11) * 0.03
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                time.sleep(jitter)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _acquire)
    try:
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()
