"""Rebuild local explorer DB from the selective dump.

Steps: backup old DB -> create schema (SQLAlchemy) -> apply dump -> validate.
Run from repo root AFTER all parts downloaded:
  python scripts/rebuild_local_db.py
"""
import gzip
import shutil
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PARTS = sorted(DATA.glob("local_snapshot.sql.part*"))
DB = DATA / "topwallet.db"
BACKUP = DATA / "topwallet.pre-s35.db"

if not PARTS:
    sys.exit("tidak ada part local_snapshot.sql.part* di data/")
print(f"parts: {len(PARTS)}")

# 1. gabung part (fragmen SATU stream gzip) -> decompress SEKALI
blob = b"".join(p.read_bytes() for p in PARTS)
sql_path = DATA / "local_snapshot.sql"
sql_path.write_bytes(gzip.decompress(blob))
blob = None
print(f"sql: {sql_path.stat().st_size/1e6:.0f} MB")

# 2. backup DB lama (kalau ada)
if DB.exists() and not BACKUP.exists():
    shutil.copy2(DB, BACKUP)
    print(f"backup DB lama -> {BACKUP.name}")
DB.unlink(missing_ok=True)

# 3. schema via SQLAlchemy — dump dari dump_snapshot.py SUDAH data-only
#    (schema statements dibuang di sisi VPS, statement-level). create_all
#    di sini menjamin semua tabel model ada (termasuk yang di-skip dump).
sys.path.insert(0, str(REPO))
from sqlalchemy import create_engine  # noqa: E402
from src.db.models import Base  # noqa: E402

eng = create_engine(f"sqlite:///{DB}")
Base.metadata.create_all(eng)
eng.dispose()

# 4. apply dump (cepat: journal off)
con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=MEMORY")
con.execute("PRAGMA synchronous=OFF")
t0 = time.time()
con.executescript(sql_path.read_text(encoding="utf-8"))
con.commit()
print(f"dump applied in {time.time()-t0:.0f}s")

# 5. validasi SEBELUM parts dihapus — dump kosong/parsial tidak boleh
#    diam-diam dianggap sukses (counts minimum per 2026-09; naikkan manual
#    bila universe membesar)
MIN_ROWS = {"wallets": 50_000, "swap_events": 100_000, "tokens": 500}
ok = True
for t in ("tokens", "pools", "wallets", "wallet_labels", "swap_events"):
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(t, n)
    if t in MIN_ROWS and n < MIN_ROWS[t]:
        print(f"!! {t}={n} di bawah minimum {MIN_ROWS[t]} — parts DIPERTAHANKAN")
        ok = False
con.close()
if not ok:
    sys.exit("REBUILD GAGAL validasi — DB baru dibiarkan, parts disimpan")

# 6. bersihkan part
for p in PARTS:
    p.unlink()
sql_path.unlink(missing_ok=True)
print("REBUILD OK")
