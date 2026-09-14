"""One-off LOCAL backfill: rescale price_points of pools quoted in a non-18-dec token.

Before the decimals fix in src/enrich/price_fetcher.py, every pool quoted in
USDG (6 decimals) stored prices 10^(token_dec − quote_dec) = 1e12 too small.

Safety:
  * DRY-RUN by default — prints what would change. Pass --apply to write.
  * --apply first copies the DB to <db>.bak-<timestamp>.
  * Idempotent per POINT, not per pool: a point is rescaled only if the
    rescaled value is log-closer to the token's DexScreener spot price than the
    stored value (i.e. stored < spot / sqrt(factor)). Already-correct points —
    including points appended by the fixed fetcher — are left alone, so a
    second run is a no-op.
  * Pools whose token has no spot price are reported and skipped.
  * Local sqlite file only; never talks to the VPS.

Usage:
  .venv/Scripts/python.exe scripts/backfill_quote_decimals.py --db data/topwallet.db
  .venv/Scripts/python.exe scripts/backfill_quote_decimals.py --db data/topwallet.db --apply
"""
from __future__ import annotations

import argparse
import math
import shutil
import sqlite3
from datetime import datetime

NATIVE = "0x0000000000000000000000000000000000000000"
# verified on-chain via decimals() on Robinhood Chain (4663)
KNOWN_QUOTE_DECIMALS = {
    "0x5fc5360d0400a0fd4f2af552add042d716f1d168": 6,   # USDG
    "0x0bd7d308f8e1639fab988df18a8011f41eacad73": 18,  # WETH
    NATIVE: 18,
}


def parse_overrides(items: list[str]) -> dict[str, int]:
    out = {}
    for it in items:
        addr, _, dec = it.partition("=")
        out[addr.strip().lower()] = int(dec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path to a LOCAL topwallet.db")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--quote-decimals", action="append", default=[], metavar="ADDR=DEC",
                    help="extra/override quote token decimals, repeatable")
    args = ap.parse_args()

    quote_dec = KNOWN_QUOTE_DECIMALS | parse_overrides(args.quote_decimals)
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    pools = con.execute("""
        select p.address, lower(p.quote_token) quote, p.quote_symbol, t.symbol,
               coalesce(t.decimals, 18) tdec, t.price_usd spot
        from pools p left join tokens t on lower(t.address) = lower(p.token_address)
    """).fetchall()

    plan: list[tuple[str, float, list[int]]] = []   # (pool, factor, point ids)
    for p in pools:
        qdec = quote_dec.get(p["quote"])
        if qdec is None:
            # tokens table decimals as a fallback (quote tokens are rarely listed)
            row = con.execute("select decimals from tokens where lower(address)=?", (p["quote"],)).fetchone()
            qdec = row[0] if row and row[0] is not None else None
        if qdec is None:
            n = con.execute("select count(*) from price_points where pool_address=?", (p["address"],)).fetchone()[0]
            if n:
                print(f"?? {p['symbol']}/{p['quote_symbol']} {p['address'][:12]}: quote decimals unknown, "
                      f"{n} points untouched (pass --quote-decimals {p['quote']}=N)")
            continue
        exp = p["tdec"] - qdec
        if exp == 0:
            continue
        factor = 10.0 ** exp
        pts = con.execute("select id, price_usd from price_points where pool_address=?", (p["address"],)).fetchall()
        if not pts:
            continue
        if not p["spot"]:
            print(f"-- {p['symbol']}/{p['quote_symbol']} {p['address'][:12]}: no spot price, "
                  f"{len(pts)} points skipped")
            continue
        # rescale iff log-closer to spot after multiplying by factor
        cut = math.log10(p["spot"]) - exp / 2
        ids = [r["id"] for r in pts if r["price_usd"] > 0 and math.log10(r["price_usd"]) < cut]
        latest = con.execute("select price_usd from price_points where pool_address=? order by block_num desc limit 1",
                             (p["address"],)).fetchone()[0]
        print(f"{'>>' if ids else 'ok'} {p['symbol']}/{p['quote_symbol']} {p['address'][:12]} "
              f"x{factor:.0e}: {len(ids)}/{len(pts)} points to rescale; "
              f"latest {latest:.3g} -> {latest * factor if ids else latest:.3g} (spot {p['spot']:.3g})")
        if ids:
            plan.append((p["address"], factor, ids))

    total = sum(len(i) for _, _, i in plan)
    print(f"\n{total} points in {len(plan)} pools {'will be' if args.apply else 'would be'} rescaled")
    if not args.apply or not total:
        if not args.apply:
            print("dry-run: nothing written (use --apply)")
        return

    backup = f"{args.db}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    con.close()
    shutil.copy2(args.db, backup)
    print(f"backup: {backup}")
    con = sqlite3.connect(args.db)
    with con:
        for _pool, factor, ids in plan:
            con.executemany("update price_points set price_usd = price_usd * ? where id = ?",
                            [(factor, i) for i in ids])
    con.close()
    print("applied. Re-run analyze (wallet_scores) + feed backfill so USD metrics pick it up.")


if __name__ == "__main__":
    main()
