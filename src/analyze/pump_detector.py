"""PUMP-FIRST wallet discovery — the strategy that finds real hunters.

Old way (wallet-first): scan holders/holders → 12K wallets → top PnL $480. Wrong.
New way (pump-first): find tokens that PUMPED (price velocity + volume spike),
then extract who bought BEFORE or at the START of the pump. Wallets that catch
MULTIPLE pumps across DIFFERENT tokens = genuine early buyers = GOLD.
Wallets that appear at pump start in one bundled tx = bundler/dev fleet.
Wallets funded by the same funder at pump time = insider cluster.

Detectable per pump, per wallet:
  ACCUMULATOR   — bought in the flat zone before the pump started
  EARLY_HUNTER  — bought in the first 10% of the pump rise
  LATE_CHASER   — bought in the last 25% (exit liquidity)
  BUNDLER       — part of a same-tx/group buy at pump ignition
  SNIPER        — bought within blocks of pool creation AND held into the pump
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Pump:
    start_block: int
    start_price: float
    peak_block: int
    peak_price: float
    gain_pct: float
    duration_blocks: int


@dataclass
class PumpParticipant:
    wallet: str
    category: str            # ACCUMULATOR | EARLY_HUNTER | LATE_CHASER
    first_buy_block: int
    bought_usd: float = 0.0
    sells_usd: float = 0.0
    realized_usd: float = 0.0


def detect_pumps(
    blocks: list[int],
    prices: list[float],
    min_gain_pct: float = 50.0,
    min_window_blocks: int = 200,
    max_window_blocks: int = 300_000,
) -> list[Pump]:
    """Detect pump episodes in a price series: a rise of >= min_gain_pct from
    a local base to a local peak within [min_window, max_window] blocks.
    Non-overlapping, newest last. `blocks` must be sorted ascending."""
    if len(blocks) != len(prices) or len(prices) < 3:
        return []
    pumps: list[Pump] = []
    i = 0
    n = len(prices)
    while i < n - 1:
        base_price = prices[i]
        base_block = blocks[i]
        # find the max price reachable within the window from i
        best_j = None
        best_p = base_price
        j = i + 1
        while j < n and blocks[j] - base_block <= max_window_blocks:
            if prices[j] > best_p:
                best_p, best_j = prices[j], j
            j += 1
        if best_j is not None:
            gain = (best_p - base_price) / base_price * 100 if base_price > 0 else 0
            dur = blocks[best_j] - base_block
            if gain >= min_gain_pct and dur >= min_window_blocks:
                pumps.append(Pump(base_block, base_price, blocks[best_j], best_p, gain, dur))
                i = best_j + 1  # next pump search starts after this peak
                continue
        i += 1
    return pumps


def classify_pump_participants(
    pump: Pump,
    buys: list[dict],          # [{wallet, block, usd}]
    sells: list[dict],         # [{wallet, block, usd}]
    early_pct: float = 0.10,
    late_pct: float = 0.75,
) -> list[PumpParticipant]:
    """Classify wallets by WHERE they entered relative to the pump."""
    span = max(pump.peak_block - pump.start_block, 1)
    early_until = pump.start_block + int(span * early_pct)
    late_from = pump.start_block + int(span * late_pct)

    agg: dict[str, dict] = {}
    for b in buys:
        if b["block"] > pump.peak_block:
            continue
        a = agg.setdefault(b["wallet"], {"first": b["block"], "usd": 0.0, "sells": 0.0})
        a["usd"] += b.get("usd", 0.0)
        a["first"] = min(a["first"], b["block"])
    for s in sells:
        if s["block"] > pump.peak_block:
            continue
        a = agg.setdefault(s["wallet"], {"first": s["block"], "usd": 0.0, "sells": 0.0})
        a["sells"] += s.get("usd", 0.0)

    out = []
    for wallet, a in agg.items():
        if a["usd"] <= 0:
            continue  # seller-only: they bought pre-pump (off-window)
        if a["first"] < pump.start_block:
            cat = "ACCUMULATOR"
        elif a["first"] <= early_until:
            cat = "EARLY_HUNTER"
        elif a["first"] >= late_from:
            cat = "LATE_CHASER"
        else:
            cat = "MID_RIDER"
        out.append(PumpParticipant(wallet, cat, a["first"], a["usd"], a["sells"],
                                   a["sells"] - a["usd"]))
    return out


def multi_pump_hunters(participants_by_pump: dict[str, list[PumpParticipant]],
                       min_pumps: int = 2) -> list[dict]:
    """Wallets that early-caught >= min_pumps DIFFERENT token pumps = GOLD.
    Returns sorted by pumps caught desc."""
    stats: dict[str, dict] = {}
    for token, parts in participants_by_pump.items():
        for p in parts:
            if p.category not in ("ACCUMULATOR", "EARLY_HUNTER"):
                continue
            s = stats.setdefault(p.wallet, {"pumps": 0, "tokens": [], "usd": 0.0})
            s["pumps"] += 1
            s["tokens"].append(token)
            s["usd"] += p.bought_usd
    hunters = [
        {"wallet": w, "pumps_caught": s["pumps"], "tokens": s["tokens"], "bought_usd": s["usd"]}
        for w, s in stats.items() if s["pumps"] >= min_pumps
    ]
    return sorted(hunters, key=lambda h: (-h["pumps_caught"], -h["bought_usd"]))
