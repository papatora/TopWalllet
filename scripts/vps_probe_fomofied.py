import asyncio
import sys

sys.path.insert(0, "/opt/topwallet")


async def main() -> None:
    import sqlite3

    from src.utils.etherscan_client import make_explorer_client

    CA = "0xf3f7dc25cad40e4d88e6876895a7606089a71d16"
    c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
    rows = c.execute(
        "select wallet_address from wallet_token_interest where token_address=? limit 5",
        (CA,)).fetchall()
    print(f"trader FOMOFIED tercatat: {len(rows)}")
    if not rows:
        print("-> tidak ada trader tercatat: interest tidak pernah di-commit!")
        return
    cl = make_explorer_client()
    for (w,) in rows[:3]:
        items = await cl.address_token_transfers(w, 6, token_filter=CA)
        st = c.execute("select count(*), max(ts) from swap_events where wallet_address=?",
                       (w,)).fetchone()
        print(f"  {w[:14]}: transfer={len(items)} | swap_db={st[0]} max={st[1]}")
        if items:
            it = items[0]
            print("    contoh ts:", it.get("timestamp"),
                  "| block:", it.get("block_number"),
                  "| dari:", ((it.get("from") or {}).get("hash") or "")[:10])
    try:
        await cl.close()
    except Exception:
        pass


asyncio.run(main())
