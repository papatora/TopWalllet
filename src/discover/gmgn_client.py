"""GMGN OpenAPI client — official data source for TopWallet (replaces scraping).

Base: https://openapi.gmgn.ai · Auth: X-APIKEY header + timestamp + client_id
params (±5s clock window, 7s replay window — always generate fresh).

Endpoints (verified working 2026-09-08):
  /v1/market/rank            trending by volume/swaps/mc (1m,5m,1h,6h,24h)
  /v1/token/info             price, volume, MC, dev stats
  /v1/token/security         honeypot, bundler rate, insider rate, top10
  /v1/market/token_top_holders   top 100 holders + PnL + tags
  /v1/market/token_top_traders   top traders + realized profit
  /v1/market/token_kline     OHLCV (30s..1d)
  POST /v1/market/token_signal   real-time signals
  /v1/user/wallet_stats      win rate, realized profit
  POST /v1/user/wallet_profits   profit breakdown 1d/7d/30d/all
  /v1/user/wallet_activity   tx ledger
  /v1/user/created_tokens    all tokens by a creator

API key (public test): gmgn_solbscbaseethmonadtron — rotate via GMGN_API_KEY env.
Chains: sol, bsc, base, eth, robinhood, arc, stable.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

BASE = "https://openapi.gmgn.ai"
DEFAULT_KEY = "gmgn_solbscbaseethmonadtron"


class GmgnClient:
    def __init__(self, api_key: str | None = None, rps: float = 2.0):
        import os

        self.key = api_key or os.getenv("GMGN_API_KEY", DEFAULT_KEY)
        self._last = 0.0
        self._min_interval = 1.0 / max(rps, 0.1)
        self._client = httpx.Client(timeout=30)

    def get(self, path: str, params: dict | None = None) -> dict | list | None:
        now = time.time()
        wait = self._last + self._min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        p = {"timestamp": int(time.time()), "client_id": str(uuid.uuid4())}
        if params:
            p.update(params)
        r = self._client.get(BASE + path, params=p,
                             headers={"X-APIKEY": self.key, "Accept": "application/json"})
        self._last = time.time()
        if r.status_code != 200:
            return {"_http_status": r.status_code, "_error": r.text[:200]}
        data = r.json()
        # GMGN wraps: {code, data: {code, data: {...}}} — unwrap one level
        if isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, dict) and "data" in inner and "code" in inner:
                return inner["data"]
            return inner
        return data

    # ── market ──

    def trending(self, chain: str, interval: str = "5m", order_by: str = "volume",
                 limit: int = 50) -> list[dict]:
        d = self.get("/v1/market/rank", {"chain": chain, "interval": interval,
                                         "order_by": order_by, "limit": limit})
        return d.get("rank", []) if isinstance(d, dict) else []

    def token_security(self, chain: str, ca: str) -> dict | None:
        d = self.get("/v1/token/security", {"chain": chain, "address": ca})
        return d if isinstance(d, dict) else None

    def token_info(self, chain: str, ca: str) -> dict | None:
        d = self.get("/v1/token/info", {"chain": chain, "address": ca})
        return d if isinstance(d, dict) else None

    def token_top_holders(self, chain: str, ca: str, limit: int = 100) -> list[dict]:
        d = self.get("/v1/market/token_top_holders",
                     {"chain": chain, "address": ca, "limit": limit})
        if isinstance(d, dict):
            return d.get("holders", d.get("rank", d.get("list", [])))
        return []

    def token_top_traders(self, chain: str, ca: str, order_by: str = "profit",
                          limit: int = 100) -> list[dict]:
        d = self.get("/v1/market/token_top_traders",
                     {"chain": chain, "address": ca, "order_by": order_by, "limit": limit})
        if isinstance(d, dict):
            return d.get("traders", d.get("rank", d.get("list", [])))
        return []

    def token_kline(self, chain: str, ca: str, interval: str = "5m", limit: int = 100) -> list:
        # NOTE: API expects the candle size as `resolution` (interval accepted
        # but optional); payload rows arrive under `list`.
        d = self.get("/v1/market/token_kline",
                     {"chain": chain, "address": ca, "resolution": interval,
                      "limit": limit})
        return d.get("klines", d.get("list", [])) if isinstance(d, dict) else []

    # ── wallet ──

    def wallet_stats(self, chain: str, wallet: str, period: str = "30d") -> dict | None:
        d = self.get("/v1/user/wallet_stats",
                     {"chain": chain, "wallet_address": wallet, "period": period})
        return d if isinstance(d, dict) else None

    def wallet_profits(self, chain: str, wallet: str, period: str = "30d") -> dict | None:
        return self.get("/v1/user/wallet_profits",
                        {"chain": chain, "wallet_address": wallet, "period": period})

    def wallet_activity(self, chain: str, wallet: str, limit: int = 100) -> list[dict]:
        d = self.get("/v1/user/wallet_activity",
                     {"chain": chain, "wallet_address": wallet, "limit": limit})
        return d.get("activities", d.get("data", [])) if isinstance(d, dict) else []

    def created_tokens(self, chain: str, wallet: str) -> list[dict]:
        d = self.get("/v1/user/created_tokens", {"chain": chain, "wallet_address": wallet})
        return d.get("tokens", d.get("list", [])) if isinstance(d, dict) else []

    def close(self):
        self._client.close()


# Tag taxonomy for holders/traders filtering (GMGN spec):
TAGS = ("smart_degen", "renowned", "fresh_wallet", "sniper", "rat_trader", "bundler", "dev")
