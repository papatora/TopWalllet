"""Stage 1c — Optional external leaderboard sources (GMGN et al).

Reality check (verified 2026-09-05):
  * GMGN DOES list Robinhood Chain (gmgn.ai/trend?chain=robinhood) — but its
    API endpoints sit behind a Cloudflare "Just a moment..." challenge for
    plain HTTP clients, with or without residential proxies. TopWallet does
    NOT attempt to defeat bot protections (no CAPTCHA farming, no fingerprint
    spoofing): if the challenge appears, this source is skipped gracefully.
    Enable ENABLE_GMGN=true to try it anyway (may work from VPS IPs).
  * Other known Robinhood Chain surfaces worth wiring in later:
      - robinscan.io/leaderboard  (chain-native wallet leaderboard)
      - fomo.family/tokens/robinhood (mobile-first DEX frontend)
      - web3.okx.com (OKX Web3 token pages)
  * The primary pipeline (on-chain trader extraction) is strictly richer than
    any leaderboard: leaderboards rank a filtered subset, the pipeline sees
    every trader and computes true PnL from full histories.
"""
from __future__ import annotations

import asyncio
import logging
import random

import httpx

from config.settings import settings
from src.utils.logger import jlog

log = logging.getLogger(__name__)

GMGN_WALLET_RANK_URL = (
    "https://gmgn.ai/defi/quotation/v1/rank/{chain}/wallets/{period}"
    "?orderby=pnl&direction=desc"
)
# chains GMGN lists (robinhood confirmed via gmgn.ai/trend?chain=robinhood)
GMGN_CHAINS = ("robinhood", "sol", "eth", "base", "bsc", "tron")


def _is_cloudflare_challenge(resp: httpx.Response) -> bool:
    return resp.status_code in (403, 503) and "just a moment" in resp.text.lower()


async def fetch_leaderboard_wallets(chain: str = "sol", period: str = "7d") -> list[dict]:
    """Return [{'wallet': '0x..', 'pnl': float, 'win_rate': float}] or [] on failure.

    Empty result is an expected, logged outcome (Cloudflare challenge or
    unsupported chain) — the pipeline treats it as 'no extra wallets found'.
    """
    if not settings.enable_gmgn:
        return []
    if chain not in GMGN_CHAINS:
        jlog(log, logging.INFO, "gmgn does not support chain; skipping", chain=chain)
        return []

    proxies = settings.proxy_urls or [None]
    last_error = ""
    for attempt in range(3):
        proxy = random.choice(proxies) if len(proxies) > 1 else proxies[0]
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                proxy=proxy,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json,text/plain,*/*",
                },
                follow_redirects=True,
            ) as client:
                resp = await client.get(GMGN_WALLET_RANK_URL.format(chain=chain, period=period))
                if _is_cloudflare_challenge(resp):
                    jlog(log, logging.WARNING,
                         "gmgn blocked by Cloudflare challenge — skipping source "
                         "(TopWallet does not bypass bot protections)",
                         proxy=proxy is not None)
                    return []
                resp.raise_for_status()
                data = resp.json().get("data", {})
                wallets = [
                    {
                        "wallet": (w.get("wallet_address") or "").lower(),
                        "pnl": w.get("realized_profit"),
                        "win_rate": w.get("win_rate"),
                    }
                    for w in data.get("rank", [])
                ]
                jlog(log, logging.INFO, "gmgn leaderboard fetched",
                     chain=chain, wallets=len(wallets))
                return wallets
        except Exception as e:  # network/JSON errors — retry through another proxy
            last_error = str(e)
            await asyncio.sleep(2 ** attempt)
    jlog(log, logging.WARNING, "gmgn leaderboard unavailable", error=last_error[:160])
    return []
