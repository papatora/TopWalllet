"""Stage 5 — Real-time monitoring of Top Wallets.

Polls the newest token transfers of each top wallet (Blockscout, cheap 1-page
queries) every MONITOR_INTERVAL_SECONDS. When a top wallet BUYS a token that
is not yet tracked in the DB, an alert goes out (Telegram/Discord/logging).

Run:  python -m src.cli monitor     (ENABLE_MONITOR gates the compose service)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from config.settings import settings
from src.db.database import get_session_factory, init_db
from src.db.models import Token
from src.discover.holder_scraper import BlockscoutClient
from src.track.alert_sender import send_alert
from src.utils.logger import jlog, setup_logging

log = logging.getLogger(__name__)
STATE_FILE = Path("data/monitor_state.json")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


async def _top_wallets(session) -> list[str]:
    results_file = settings.results_dir / "top_wallets_latest.json"
    if results_file.exists():
        try:
            data = json.loads(results_file.read_text())
            return [w["wallet_address"].lower() for w in data.get("wallets", [])]
        except (json.JSONDecodeError, KeyError):
            pass
    # fallback: best scores from the DB
    from src.db.models import WalletScore

    rows = (await session.execute(
        select(WalletScore.wallet_address)
        .order_by(WalletScore.composite_score.desc())
        .limit(settings.top_wallets_for_monitor)
    )).all()
    return [r[0] for r in rows]


async def run_monitor() -> None:
    setup_logging()
    await init_db()
    blockscout = BlockscoutClient()
    session_factory = get_session_factory()
    state = _load_state()
    jlog(log, logging.INFO, "monitor started", interval=settings.monitor_interval_seconds,
         state_wallets=len(state))

    while True:
        try:
            async with session_factory() as session:
                known_tokens = {
                    r[0] for r in (await session.execute(select(Token.address))).all()
                }
                wallets = await _top_wallets(session)

            new_buys: list[tuple[str, str, str]] = []
            for wallet in wallets:
                items = await blockscout.address_token_transfers(wallet, 1)
                seen_block = state.get(wallet, {}).get("block", 0)
                max_block = seen_block
                for item in items:
                    block = int(item.get("block_number") or 0)
                    max_block = max(max_block, block)
                    token = ((item.get("token") or {}).get("address") or "").lower()
                    symbol = ((item.get("token") or {}).get("symbol") or token[:8])
                    dst = ((item.get("to") or {}).get("hash") or "").lower()
                    src = ((item.get("from") or {}).get("hash") or "").lower()
                    if dst == wallet and src == settings.pool_manager and token not in known_tokens:
                        if block > seen_block:
                            new_buys.append((wallet, symbol, token))
                state[wallet] = {"block": max_block, "checked": datetime.now(timezone.utc).isoformat()}
            _save_state(state)

            for wallet, symbol, token in new_buys:
                text = (f"🎯 <b>Top Wallet entry</b>\n"
                        f"wallet: <code>{wallet}</code>\n"
                        f"bought: {symbol} (<code>{token}</code>) on {settings.chain}")
                await send_alert(text)
                jlog(log, logging.INFO, "new top-wallet entry", wallet=wallet, token=token)
        except Exception as e:
            jlog(log, logging.ERROR, "monitor iteration failed", error=str(e)[:200])

        await asyncio.sleep(settings.monitor_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_monitor())
