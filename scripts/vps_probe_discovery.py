import asyncio
import sys

sys.path.insert(0, "/opt/topwallet")


async def main() -> None:
    from src.discover.holder_scraper import extract_wallet_hits
    from src.utils.etherscan_client import make_explorer_client

    CA = "0xf3f7dc25cad40e4d88e6876895a7606089a71d16"
    cl = make_explorer_client()
    print("client:", type(cl).__name__)
    transfers = await cl.token_transfers(CA, 24)
    print("token_transfers:", len(transfers))
    holders = await cl.token_holders(CA, 100)
    print("token_holders (derivasi):", len(holders))

    from config.settings import settings
    import sqlite3
    c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
    pools = [r[0] for r in c.execute("select address from pools where token_address=?", (CA,))]
    print("pool FOMOFIED di DB:", pools)
    exclude = {settings.pool_manager, settings.weth_address, settings.usdg_address,
               "0x" + "0" * 40, "0x" + "0" * 38 + "dead"}
    exclude |= {p.lower() for p in pools}
    hits = extract_wallet_hits(CA, holders, transfers, exclude)
    print("HITS:", len(hits))
    for h in hits[:5]:
        print("  ", h.address[:14], "| token:", h.token_address[:10], "| source:", h.source)
    try:
        await cl.close()
    except Exception:
        pass


asyncio.run(main())
