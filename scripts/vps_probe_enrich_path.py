import asyncio
import sys

sys.path.insert(0, "/opt/topwallet")
sys.path.insert(0, "/opt/topwallet/scripts")


async def main() -> None:
    from src.utils.etherscan_client import make_explorer_client
    import sqlite3

    c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
    # wallet dari kohor terakhir: punya interest di token yang pertama kali
    # dilihat paling baru, statusnya masih 'enriched'
    row = c.execute(
        "select i.wallet_address, i.token_address, t.symbol, t.first_seen "
        "from wallet_token_interest i "
        "join tokens t on t.address = i.token_address "
        "join wallets w on w.address = i.wallet_address "
        "where w.status = 'enriched' and t.address in ("
        "  select token_address from wallet_token_interest "
        "  group by token_address) "
        "order by t.first_seen desc limit 1").fetchone()
    if not row:
        print("tidak ada sampel")
        return
    wallet, token, sym, fs = row
    st = c.execute("select count(*), max(ts) from swap_events where wallet_address=?",
                   (wallet,)).fetchone()
    print(f"sampel: wallet {wallet[:14]} | token {token[:14]} ({sym}) first_seen {fs}")
    print(f"  swap saat ini: {st[0]} | max ts: {st[1]}")

    cl = make_explorer_client()
    print("client:", type(cl).__name__)
    items = await cl.address_token_transfers(wallet, 6, token_filter=token)
    print(f"address_token_transfers (token_filter) -> {len(items)} item")
    for it in items[:3]:
        print("  ", it.get("timestamp"), "| block", it.get("block_number"),
              "| dari", ((it.get("from") or {}).get("hash") or "")[:10],
              "ke", ((it.get("to") or {}).get("hash") or "")[:10])
    try:
        await cl.close()
    except Exception:
        pass


asyncio.run(main())
