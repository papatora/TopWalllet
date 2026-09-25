import asyncio
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/opt/topwallet")


async def main() -> None:
    from sqlalchemy import select, text

    from src.db.database import get_session_factory, init_db
    from src.db.models import Wallet
    from src.pipeline import Pipeline, _commit_locked

    await init_db()
    p = Pipeline()
    sf = get_session_factory()
    async with sf() as session:
        session.sync_session.autoflush = False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = (await session.execute(text(
            "select w.address from wallets w "
            "join wallet_token_interest i on i.wallet_address = w.address "
            "join tokens t on t.address = i.token_address "
            "where w.status = 'enriched' "
            "and (w.enriched_at is null or w.enriched_at < :c) "
            "group by w.address "
            "order by max(t.first_seen) desc limit :lim"),
            {"c": cutoff, "lim": 400})).all()
        addrs = [r[0] for r in rows]
        print("kohor ter-target:", len(addrs), flush=True)
        if addrs:
            print("contoh 3 teratas:", addrs[:3], flush=True)
        wallets = []
        for i in range(0, len(addrs), 500):
            wallets += (await session.execute(
                select(Wallet).where(Wallet.address.in_(addrs[i:i + 500]))
            )).scalars().all()
        order = {a: k for k, a in enumerate(addrs)}
        wallets.sort(key=lambda w: order.get(w.address, 1 << 30))
        res = await p.enrich_wallets(session, wallets)
        await _commit_locked(session)
        print("hasil enrich:", res, flush=True)
    await p.blockscout.close()
    await p.rpc.close()
    c = None
    import sqlite3
    c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
    print("swap_max_ts sekarang:",
          c.execute("select max(ts) from swap_events").fetchone()[0], flush=True)
    print("swaps sekarang:",
          c.execute("select count(*) from swap_events").fetchone()[0], flush=True)


asyncio.run(main())
