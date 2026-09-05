"""Stage 3b — Wallet-level metrics and the composite smart-money score.

The thesis: consistency beats one-off luck. A wallet that hits 10x–1000x on
MULTIPLE tokens over months, buying local dips and selling local tops, is the
signal. The composite score (0–100) is a weighted blend — weights live in
config/scoring_weights.json and can be tuned without touching code.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.analyze.position_calculator import CalcPosition


@dataclass
class WalletMetrics:
    total_positions: int
    closed_positions: int
    open_positions: int
    winning_positions: int
    win_rate: float
    median_return_multiple: float
    max_return_multiple: float
    total_realized_pnl_usd: float
    total_unrealized_pnl_usd: float
    avg_hold_duration_hours: float
    consistency_score: float
    dip_buying_accuracy: float
    top_selling_accuracy: float
    distinct_tokens: int
    big_wins: int                      # closed positions with multiple >= big_win_multiple
    recent_win_rate: float             # recency-weighted win rate
    active_months: int
    last_active: datetime | None
    median_position_size_usd: float


def compute_metrics(
    positions: list[CalcPosition],
    weights_cfg: dict,
    now: datetime | None = None,
) -> WalletMetrics | None:
    cfg = weights_cfg.get("thresholds", {})
    norm = weights_cfg.get("normalization", {})
    styles = weights_cfg.get("styles", {})
    min_positions = cfg.get("min_positions", 5)
    min_tokens = cfg.get("min_distinct_tokens", 3)
    min_size_usd = cfg.get("min_position_size_usd", 1.0)

    meaningful = [p for p in positions if (p.size_usd or 0) >= min_size_usd]
    if len(meaningful) < min_positions:
        return None
    distinct = {p.token for p in meaningful}
    if len(distinct) < min_tokens:
        return None

    now = now or datetime.now(timezone.utc)
    closed = [p for p in meaningful if p.status == "closed" and p.return_multiple]
    open_pos = [p for p in meaningful if p.status == "open"]
    with_mult = closed

    wins = [p for p in with_mult if (p.return_multiple or 0) > 1.0]
    win_rate = len(wins) / len(with_mult) if with_mult else 0.0

    mults = sorted((p.return_multiple or 1.0) for p in with_mult)
    median_mult = statistics.median(mults) if mults else 0.0
    max_mult = max(mults) if mults else 0.0
    big_win_threshold = styles.get("big_win_multiple", 10.0)
    big_wins = sum(1 for m in mults if m >= big_win_threshold)

    realized = sum(p.pnl_usd or 0.0 for p in closed)
    unrealized = sum(
        (p.size_usd or 0) * (p.return_multiple or 1.0) - (p.size_usd or 0)
        for p in open_pos if p.return_multiple
    )

    holds = [p.hold_hours for p in closed if p.hold_hours is not None]
    avg_hold = statistics.mean(holds) if holds else 0.0

    # timing accuracy over positions where a window percentile exists
    dip_thr = weights_cfg.get("styles", {}).get("dip_accuracy_threshold", 0.6)
    top_thr = weights_cfg.get("styles", {}).get("top_accuracy_threshold", 0.6)
    dip_pctile_target = cfg.get("dip_percentile", 0.2)
    top_pctile_target = cfg.get("top_percentile", 0.8)
    entry_pctiles = [p.entry_pctile for p in meaningful if p.entry_pctile is not None]
    exit_pctiles = [p.exit_pctile for p in closed if p.exit_pctile is not None]
    dip_accuracy = (
        sum(1 for q in entry_pctiles if q <= dip_pctile_target) / len(entry_pctiles)
        if entry_pctiles else 0.0
    )
    top_accuracy = (
        sum(1 for q in exit_pctiles if q >= top_pctile_target) / len(exit_pctiles)
        if exit_pctiles else 0.0
    )

    # consistency: reliability (win rate) scaled by token breadth
    token_cap = norm.get("distinct_tokens_cap", 15)
    breadth = min(len(distinct) / max(token_cap, 1), 1.0)
    consistency = win_rate * (0.4 + 0.6 * breadth)

    # recency-weighted win rate (exponential decay by position age)
    half_life = float(norm.get("recency_half_life_days", 45))
    wsum = wwin = 0.0
    for p in with_mult:
        ended = p.exit_ts or p.entry_ts
        age_days = max((now - _aware(ended)).total_seconds() / 86400.0, 0.0)
        w = 0.5 ** (age_days / half_life)
        wsum += w
        if (p.return_multiple or 0) > 1.0:
            wwin += w
    recent_win_rate = (wwin / wsum) if wsum > 0 else 0.0

    months = {(p.entry_ts or now).strftime("%Y-%m") for p in meaningful}
    last_active = max((_aware(p.exit_ts or p.entry_ts) for p in meaningful), default=None)
    sizes = sorted(p.size_usd or 0.0 for p in meaningful)

    return WalletMetrics(
        total_positions=len(meaningful),
        closed_positions=len(closed),
        open_positions=len(open_pos),
        winning_positions=len(wins),
        win_rate=round(win_rate, 4),
        median_return_multiple=round(median_mult, 4),
        max_return_multiple=round(max_mult, 4),
        total_realized_pnl_usd=round(realized, 2),
        total_unrealized_pnl_usd=round(unrealized, 2),
        avg_hold_duration_hours=round(avg_hold, 2),
        consistency_score=round(consistency, 4),
        dip_buying_accuracy=round(dip_accuracy, 4),
        top_selling_accuracy=round(top_accuracy, 4),
        distinct_tokens=len(distinct),
        big_wins=big_wins,
        recent_win_rate=round(recent_win_rate, 4),
        active_months=len(months),
        last_active=last_active,
        median_position_size_usd=round(statistics.median(sizes), 2) if sizes else 0.0,
    )


def composite_score(metrics: WalletMetrics, weights_cfg: dict) -> float:
    w = weights_cfg.get("weights", {})
    norm = weights_cfg.get("normalization", {})

    def lognorm(value: float, cap: float) -> float:
        if value <= 1:
            return 0.0
        return min(math.log10(value) / math.log10(cap), 1.0) if cap > 1 else 0.0

    components = {
        "win_rate": metrics.win_rate,
        "median_return": lognorm(metrics.median_return_multiple, norm.get("median_return_log_cap", 20)),
        "moonshots": lognorm(metrics.max_return_multiple, norm.get("max_return_log_cap", 500)),
        "dip_buying": metrics.dip_buying_accuracy,
        "top_selling": metrics.top_selling_accuracy,
        "consistency": metrics.consistency_score,
        "recency": metrics.recent_win_rate,
    }
    total_w = sum(float(w.get(k, 0)) for k in components)
    if total_w <= 0:
        return 0.0
    score = sum(float(w.get(k, 0)) * v for k, v in components.items()) / total_w
    return round(score * 100.0, 2)


def trading_style(metrics: WalletMetrics, weights_cfg: dict) -> str:
    styles = weights_cfg.get("styles", {})
    tags: list[str] = []
    if metrics.dip_buying_accuracy >= styles.get("dip_accuracy_threshold", 0.6):
        tags.append("dip_buyer")
    if metrics.top_selling_accuracy >= styles.get("top_accuracy_threshold", 0.6):
        tags.append("top_seller")
    if metrics.open_positions > 0:
        big_open = metrics.total_unrealized_pnl_usd > 0 and metrics.big_wins >= 1
        if big_open or metrics.avg_hold_duration_hours >= styles.get("diamond_min_hold_hours", 168):
            tags.append("diamond_hands")
    if metrics.avg_hold_duration_hours > 0 and metrics.avg_hold_duration_hours <= styles.get(
        "scalper_max_hold_hours", 6
    ):
        tags.append("scalper")
    if metrics.big_wins >= weights_cfg.get("thresholds", {}).get("big_wins_for_moonshot_style", 3):
        tags.append("multi_moonshot")
    if metrics.median_position_size_usd >= 5000:
        tags.append("whale_size")
    return "_".join(tags[:3]) if tags else "generalist"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
