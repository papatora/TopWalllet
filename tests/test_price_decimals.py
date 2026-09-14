"""Regression: pools quoted in a non-18-decimal token (USDG = 6 decimals).

sqrtPriceX96² is a ratio of smallest units, so an 18-dec token priced in 6-dec
USDG came out 1e-12 too small (e.g. MEME stored at 3e-14 instead of ~0.046).
"""
from datetime import datetime, timezone
from math import sqrt

import pytest

from src.db.models import Pool, PricePoint, Token
from src.enrich.price_fetcher import Q96, PriceService, quote_per_token

TOKEN_LO = "0x1000000000000000000000000000000000000001"   # sorts before USDG → token0
TOKEN_HI = "0xf000000000000000000000000000000000000001"   # sorts after USDG → token1
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"


def sqrt_x96_for(price_usdg: float, token_is_token0: bool, token_dec=18, quote_dec=6) -> int:
    """Encode a human price the way the pool stores it (token1 wei per token0 wei)."""
    quote_wei_per_token_wei = price_usdg * 10 ** quote_dec / 10 ** token_dec
    raw = quote_wei_per_token_wei if token_is_token0 else 1 / quote_wei_per_token_wei
    return int(sqrt(raw) * Q96)


@pytest.mark.parametrize("token_is_token0", [True, False])
def test_quote_per_token_6_decimal_quote(token_is_token0):
    price = 0.0459
    sx = sqrt_x96_for(price, token_is_token0)
    got = quote_per_token(sx, token_is_token0, token_decimals=18, quote_decimals=6)
    assert got == pytest.approx(price, rel=1e-6)


def test_quote_per_token_same_decimals_unchanged():
    # 18/18 (WETH-quoted) pools must keep the old behaviour: no rescale
    sx = sqrt_x96_for(0.0002, True, token_dec=18, quote_dec=18)
    assert quote_per_token(sx, True, 18, 18) == pytest.approx(0.0002, rel=1e-6)


# ---------------- end-to-end through build_series_for_pool ----------------

class _Result:
    def scalars(self):
        return self

    def all(self):
        return []


class FakeSession:
    def __init__(self, tokens: dict[str, Token]):
        self.tokens = tokens
        self.added: list = []

    async def execute(self, _query):
        return _Result()          # no existing price points

    async def get(self, model, key):
        return self.tokens.get(key) if model is Token else None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


class FakeRpc:
    def __init__(self, logs, decimals_by_addr):
        self.logs = logs
        self.decimals_by_addr = decimals_by_addr
        self.calls: list = []

    async def get_logs_adaptive(self, *a, **kw):
        return self.logs

    async def call(self, method, params):
        self.calls.append((method, params))
        assert method == "eth_call" and params[0]["data"] == "0x313ce567"
        return hex(self.decimals_by_addr[params[0]["to"]])


def _swap_log(block: int, sqrt_x96: int) -> dict:
    words = [0, 0, sqrt_x96, 0, 0, 0]  # v4 Swap data: amount0, amount1, sqrtPriceX96, ...
    return {"blockNumber": hex(block),
            "data": "0x" + "".join(w.to_bytes(32, "big").hex() for w in words)}


@pytest.mark.asyncio
@pytest.mark.parametrize("token_addr", [TOKEN_LO, TOKEN_HI])
async def test_build_series_usdg_pool_is_usd_scaled(token_addr):
    spot = 0.0459
    is_t0 = token_addr < USDG
    prices = {100: 0.040, 200: 0.0459, 300: 0.050}
    logs = [_swap_log(b, sqrt_x96_for(p, is_t0)) for b, p in prices.items()]

    # USDG deliberately absent from tokens table → must come from decimals()
    session = FakeSession({token_addr: Token(address=token_addr, symbol="MEME",
                                             decimals=18, price_usd=spot)})
    rpc = FakeRpc(logs, {USDG: 6})
    svc = PriceService(rpc, session)
    ts = datetime(2026, 9, 1, tzinfo=timezone.utc)

    async def fake_ts(blocks):
        return {b: ts for b in blocks}
    svc._timestamps = fake_ts

    pool = Pool(address="0x" + "ab" * 32, token_address=token_addr, version=4,
                quote_token=USDG, quote_symbol="USDG")
    n = await svc.build_series_for_pool(pool, 0, 1000)

    points = {p.block_num: p.price_usd for p in session.added if isinstance(p, PricePoint)}
    assert n == 3
    for block, price in prices.items():
        assert points[block] == pytest.approx(price, rel=1e-6)
    assert len(rpc.calls) == 1  # decimals cached per quote token
