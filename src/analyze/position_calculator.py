"""Stage 3a — Position construction from classified swap events.

FIFO lot accounting per (wallet, token): buys accumulate a weighted-average
cost basis; sells realize the proportional cost and produce a closed position
with a return multiple. Whatever remains at the end is an open position
valued at the token's latest known price (unrealized).

Callers group a wallet's events by token and call build_positions() once per
token. Timing percentiles are filled via a price-window lookup: entry_pctile
near 0.0 means the buy landed at the bottom of the local price window (a dip
buy); exit_pctile near 1.0 means the sell landed at a local top.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

EPS_QTY = 1e-9


@dataclass
class CalcPosition:
    wallet: str
    token: str
    status: str                      # open | closed
    entry_ts: datetime
    exit_ts: datetime | None
    entry_block: int
    exit_block: int | None
    entry_price_usd: float | None
    exit_price_usd: float | None
    size_usd: float | None           # cost basis realized (closed) or held (open)
    pnl_usd: float | None
    return_multiple: float | None
    hold_hours: float | None
    entry_pctile: float | None = None
    exit_pctile: float | None = None


@dataclass
class PricedEvent:
    """A classified swap of ONE token with USD price already attached."""
    token: str
    side: str
    token_amount: float
    price_usd: float
    ts: datetime
    block_num: int


class PriceWindowLookup:
    """Adapter interface implemented by PriceService (kept tiny for tests)."""

    def window_prices(self, token: str, block: int, window_blocks: int) -> list[float]: ...
    def percentile(self, value: float, window: list[float]) -> float | None: ...


def build_positions(
    wallet: str,
    token: str,
    events: list[PricedEvent],
    current_price_usd: float | None = None,
    price_lookup: PriceWindowLookup | None = None,
    dip_window_blocks: int = 5_000_000,
) -> list[CalcPosition]:
    """Build all positions for a single (wallet, token) pair."""
    events = sorted(
        [e for e in events if e.price_usd and e.price_usd > 0 and e.token_amount > 0],
        key=lambda e: (e.block_num, e.side == "SELL"),
    )
    positions: list[CalcPosition] = []

    qty = 0.0
    cost = 0.0
    opened_ts: datetime | None = None
    opened_block: int | None = None

    def _close(exit_ev: PricedEvent) -> None:
        nonlocal qty, cost
        sell_qty = min(exit_ev.token_amount, qty)
        frac = sell_qty / qty
        cost_sold = cost * frac
        proceeds = sell_qty * exit_ev.price_usd
        positions.append(CalcPosition(
            wallet=wallet, token=token, status="closed",
            entry_ts=opened_ts, exit_ts=exit_ev.ts,
            entry_block=opened_block or exit_ev.block_num, exit_block=exit_ev.block_num,
            entry_price_usd=(cost / qty) if qty > EPS_QTY else None,
            exit_price_usd=exit_ev.price_usd,
            size_usd=cost_sold, pnl_usd=proceeds - cost_sold,
            return_multiple=(proceeds / cost_sold) if cost_sold > 0 else None,
            hold_hours=_hours_between(opened_ts, exit_ev.ts),
        ))
        qty -= sell_qty
        cost -= cost_sold

    for ev in events:
        if ev.side == "BUY":
            if qty <= EPS_QTY:
                opened_ts, opened_block = ev.ts, ev.block_num
            qty += ev.token_amount
            cost += ev.token_amount * ev.price_usd
        else:  # SELL
            if qty <= EPS_QTY or opened_ts is None:
                continue  # selling tokens acquired before the lookback window
            _close(ev)
            if qty <= EPS_QTY:
                qty, cost = 0.0, 0.0

    if qty > EPS_QTY and opened_ts is not None and cost > 0:
        last_ts = max(e.ts for e in events)
        positions.append(CalcPosition(
            wallet=wallet, token=token, status="open",
            entry_ts=opened_ts, exit_ts=None,
            entry_block=opened_block, exit_block=None,
            entry_price_usd=(cost / qty), exit_price_usd=current_price_usd,
            size_usd=cost, pnl_usd=None,
            return_multiple=(qty * current_price_usd / cost) if current_price_usd else None,
            hold_hours=_hours_between(opened_ts, last_ts),
        ))

    if price_lookup is not None:
        attach_timing(positions, price_lookup, dip_window_blocks)
    return positions


def attach_timing(positions: list[CalcPosition], lookup: PriceWindowLookup, window_blocks: int) -> None:
    for pos in positions:
        if pos.entry_price_usd:
            window = lookup.window_prices(pos.token, pos.entry_block, window_blocks)
            pos.entry_pctile = lookup.percentile(pos.entry_price_usd, window)
        if pos.status == "closed" and pos.exit_price_usd:
            window = lookup.window_prices(pos.token, pos.exit_block or 0, window_blocks)
            pos.exit_pctile = lookup.percentile(pos.exit_price_usd, window)


def _hours_between(a: datetime, b: datetime) -> float:
    a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
    b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
    return max((b - a).total_seconds() / 3600.0, 0.0)
