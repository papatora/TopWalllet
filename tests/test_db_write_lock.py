"""Pin S-43: db_write_lock sebagai async context manager.

Di Windows (CI/dev) kunci = no-op; di POSIX acquire jalan lewat executor
dengan flock blocking. Tes ini memastikan wiring import + yield/finally
tidak pernah regresi (pipeline & track_by_ca bergantung padanya).
"""
from __future__ import annotations

import asyncio

from src.utils.db_write_lock import db_write_lock


def test_lock_yields_and_releases() -> None:
    async def go() -> str:
        out = ""
        async with db_write_lock():
            out = "inside"
        # setelah keluar context, pemanggilan berikutnya tidak boleh hang
        async with db_write_lock():
            out += "+reentry"
        return out

    assert asyncio.run(go()) == "inside+reentry"
