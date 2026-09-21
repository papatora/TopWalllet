"""Rebuild local explorer DB from the selective dump.

Steps: gabung part (SATU stream gzip) -> bangun DB BARU di temp -> validasi
counts minimum -> baru replace DB lama (backup rolling .prev.db). DB lama
TIDAK PERNAH disentuh sebelum DB baru lolos validasi — kegagalan download
atau dump kosong tidak merusak apa pun.
Run from repo root AFTER all parts downloaded:
  python scripts/rebuild_local_db.py
"""
import gzip
import sqlite3
import zlib
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PARTS = sorted(DATA.glob("local_snapshot.sql.part*"))
DB = DATA / "topwallet.db"
NEW = DATA / "topwallet.new.db"
PREV = DATA / "topwallet.prev.db"
BACKUP = DATA / "topwallet.pre-s35.db"  # backup historis pertama, dijaga

if not PARTS:
    sys.exit("tidak ada part local_snapshot.sql.part* di data/")
print(f"parts: {len(PARTS)}")

# 1. gabung part (fragmen SATU stream gzip) -> decompress SEKALI
blob = b"".join(p.read_bytes() for p in PARTS)
sql_path = DATA / "local_snapshot.sql"
try:
    sql_path.write_bytes(gzip.decompress(blob))
except (OSError, EOFError, zlib.error) as e:
    sys.exit(f"gzip rusak — part download parsial/campur dump lama? "
             f"hapus part lokal lalu re-download. ({e})")
blob = None
print(f"sql: {sql_path.stat().st_size/1e6:.0f} MB")

# 2. schema via SQLAlchemy — dump dari dump_snapshot.py SUDAH data-only
#    (schema statements dibuang di sisi VPS, statement-level). create_all
#    di sini menjamin semua tabel model ada (termasuk yang di-skip dump).
sys.path.insert(0, str(REPO))
from sqlalchemy import create_engine  # noqa: E402
from src.db.models import Base  # noqa: E402

NEW.unlink(missing_ok=True)
NEW.with_name(NEW.name + "-wal").unlink(missing_ok=True)
NEW.with_name(NEW.name + "-shm").unlink(missing_ok=True)
eng = create_engine(f"sqlite:///{NEW}")
Base.metadata.create_all(eng)
eng.dispose()

# 3. apply dump (cepat: journal off)
con = sqlite3.connect(NEW)
con.execute("PRAGMA journal_mode=MEMORY")
con.execute("PRAGMA synchronous=OFF")
t0 = time.time()
con.executescript(sql_path.read_text(encoding="utf-8"))
con.commit()
print(f"dump applied in {time.time()-t0:.0f}s")

# 4. validasi SEBELUM menyentuh DB lama — dump kosong/parsial tidak boleh
#    dianggap sukses (counts minimum per 2026-09; naikkan manual bila
#    universe membesar)
MIN_ROWS = {"wallets": 50_000, "swap_events": 100_000, "tokens": 500}
ok = True
for t in ("tokens", "pools", "wallets", "wallet_labels", "swap_events"):
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(t, n)
    if t in MIN_ROWS and n < MIN_ROWS[t]:
        print(f"!! {t}={n} di bawah minimum {MIN_ROWS[t]}")
        ok = False
# premis explorer (bukan syarat gagal, tapi WAJIB dilaporkan): price_points=0
# berarti sparkline, Price chart & kalibrasi USDG tetap nonaktif dan SEMUA
# USD est. di explorer dihitung dari harga snapshot statis (audit-A P1).
for t in ("price_points", "wallet_scores"):
    n = con.execute(f"select count(*) from {t}").fetchone()[0]
    print(t, n)
    if n == 0:
        print(f"!! PERINGATAN: {t}=0 di dump — cek [VPS] dulu: "
              "python scripts/vps_query.py counts (stage prices/analyze mungkin "
              "belum selesai; rebuild ini TIDAK mengaktifkan fitur tsb)")
con.close()

if not ok:
    sql_path.unlink(missing_ok=True)
    NEW.unlink(missing_ok=True)
    sys.exit("REBUILD GAGAL validasi — DB lama utuh, NEW dihapus, "
             "parts dipertahankan untuk investigasi")

# 5. lolos validasi -> replace: lama jadi .prev.db (rolling), pertahankan
#    backup historis pertama kalau ada
if DB.exists():
    if not BACKUP.exists():
        import shutil

        shutil.copy2(DB, BACKUP)
    DB.replace(PREV)
NEW.replace(DB)

# 6. bersihkan part
for p in PARTS:
    p.unlink()
sql_path.unlink(missing_ok=True)
print("REBUILD OK")
