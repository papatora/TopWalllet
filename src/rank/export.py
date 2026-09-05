"""Stage 4 — Export: ranked lists to JSON/CSV, per-wallet details, stats, history.

results/
  top_wallets_latest.json   — always the most recent ranked list (spec schema)
  top_wallets_latest.csv
  wallet_details/{addr}.json — per-wallet position breakdown (top N)
  history/{date}/            — immutable daily snapshots
  stats.json                 — machine-readable pipeline stats
PROGRESS.md                  — human log appended after every run
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings
from src.rank.ranker import RankedWallet
from src.utils.logger import jlog

log = logging.getLogger(__name__)


def eip55(address: str) -> str:
    """Checksum-case an address for display (Robinhood Chain uses EIP-55)."""
    from Crypto.Hash import keccak

    addr = address.lower().replace("0x", "")
    k = keccak.new(digest_bits=256)
    k.update(addr.encode())
    digest = k.hexdigest()
    out = "0x"
    for i, ch in enumerate(addr):
        out += ch.upper() if int(digest[i], 16) >= 8 else ch
    return out


def _wallet_json(entry: RankedWallet, symbols: dict[str, str]) -> dict:
    m = entry.metrics
    closed = sorted(
        [p for p in entry.positions if p.status == "closed" and p.return_multiple],
        key=lambda p: p.return_multiple or 0, reverse=True,
    )[:5]
    open_pos = sorted(
        [p for p in entry.positions if p.status == "open" and p.return_multiple],
        key=lambda p: p.return_multiple or 0, reverse=True,
    )[:2]
    top_trades = [
        {
            "token": symbols.get(p.token, p.token[:10]),
            "ca": eip55(p.token),
            "entry_price_usd": p.entry_price_usd,
            "exit_price_usd": p.exit_price_usd,
            "return_multiple": round(p.return_multiple, 2) if p.return_multiple else None,
            "position_size_usd": round(p.size_usd or 0, 2),
            "pnl_usd": round(p.pnl_usd or 0, 2) if p.pnl_usd is not None else None,
            "entry_date": p.entry_ts.date().isoformat(),
            "exit_date": p.exit_ts.date().isoformat() if p.exit_ts else None,
        }
        for p in closed + open_pos
    ]
    return {
        "rank": entry.rank,
        "wallet_address": eip55(entry.wallet_address),
        "composite_score": entry.composite_score,
        "metrics": {
            "total_positions": m.total_positions,
            "winning_positions": m.winning_positions,
            "win_rate": m.win_rate,
            "median_return_multiple": m.median_return_multiple,
            "max_return_multiple": m.max_return_multiple,
            "total_realized_pnl_usd": m.total_realized_pnl_usd,
            "total_unrealized_pnl_usd": m.total_unrealized_pnl_usd,
            "avg_hold_duration_hours": m.avg_hold_duration_hours,
            "consistency_score": m.consistency_score,
            "dip_buying_accuracy": m.dip_buying_accuracy,
            "top_selling_accuracy": m.top_selling_accuracy,
            "distinct_tokens": m.distinct_tokens,
            "big_wins_10x_plus": m.big_wins,
            "recent_win_rate": m.recent_win_rate,
            "active_months": m.active_months,
            "last_active": m.last_active.isoformat() if m.last_active else None,
        },
        "top_trades": top_trades,
        "trading_style": entry.trading_style,
        "risk_flags": entry.risk_flags,
        "cluster_id": entry.cluster_id,
    }


def _wallet_csv_row(entry: RankedWallet) -> dict:
    m = entry.metrics
    return {
        "rank": entry.rank,
        "wallet_address": eip55(entry.wallet_address),
        "composite_score": entry.composite_score,
        "win_rate": m.win_rate,
        "median_return_multiple": m.median_return_multiple,
        "max_return_multiple": m.max_return_multiple,
        "total_positions": m.total_positions,
        "distinct_tokens": m.distinct_tokens,
        "big_wins_10x_plus": m.big_wins,
        "total_realized_pnl_usd": m.total_realized_pnl_usd,
        "total_unrealized_pnl_usd": m.total_unrealized_pnl_usd,
        "dip_buying_accuracy": m.dip_buying_accuracy,
        "top_selling_accuracy": m.top_selling_accuracy,
        "avg_hold_duration_hours": m.avg_hold_duration_hours,
        "active_months": m.active_months,
        "last_active": m.last_active.isoformat() if m.last_active else "",
        "trading_style": entry.trading_style,
        "risk_flags": "|".join(entry.risk_flags),
        "cluster_id": entry.cluster_id or "",
    }


def export_results(
    ranked: list[RankedWallet],
    symbols: dict[str, str],
    stage_counts: dict,
    run_started_at: datetime,
) -> Path:
    results = settings.results_dir
    (results / "wallet_details").mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hist = results / "history" / today
    hist.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chain": settings.chain,
        "chain_id": settings.chain_id,
        "total_ranked": len(ranked),
        "wallets": [_wallet_json(e, symbols) for e in ranked],
    }
    (results / "top_wallets_latest.json").write_text(json.dumps(payload, indent=2))

    csv_path = results / "top_wallets_latest.csv"
    rows = [_wallet_csv_row(e) for e in ranked]
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("")

    # per-wallet details for the top 50
    for entry in ranked[:50]:
        detail = _wallet_json(entry, symbols)
        detail["all_positions"] = [
            {
                "token": symbols.get(p.token, p.token[:10]),
                "ca": eip55(p.token),
                "status": p.status,
                "entry_ts": p.entry_ts.isoformat() if p.entry_ts else None,
                "exit_ts": p.exit_ts.isoformat() if p.exit_ts else None,
                "entry_price_usd": p.entry_price_usd,
                "exit_price_usd": p.exit_price_usd,
                "size_usd": round(p.size_usd or 0, 2),
                "pnl_usd": round(p.pnl_usd or 0, 2) if p.pnl_usd is not None else None,
                "return_multiple": round(p.return_multiple, 4) if p.return_multiple else None,
                "hold_hours": round(p.hold_hours, 2) if p.hold_hours is not None else None,
                "entry_pctile": p.entry_pctile,
                "exit_pctile": p.exit_pctile,
            }
            for p in entry.positions
        ]
        safe = entry.wallet_address[:20]
        (results / "wallet_details" / f"{safe}.json").write_text(json.dumps(detail, indent=2))

    for target in (hist,):
        (target / "top_wallets.json").write_text(json.dumps(payload, indent=2))
        (target / "top_wallets.csv").write_text(csv_path.read_text())

    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "chain": settings.chain,
        "chain_id": settings.chain_id,
        "stage_counts": stage_counts,
        "top_wallets_count": len(ranked),
        "run_duration_seconds": round((datetime.now(timezone.utc) - run_started_at).total_seconds(), 1),
        "config": {
            "lookback_days": settings.lookback_days,
            "min_positions": settings.min_positions,
            "min_distinct_tokens": settings.min_distinct_tokens,
            "max_tokens": settings.max_tokens,
            "dip_window_days": settings.dip_window_days,
        },
    }
    (results / "stats.json").write_text(json.dumps(stats, indent=2))

    _append_progress(ranked, stage_counts, today)
    jlog(log, logging.INFO, "export complete", ranked=len(ranked), out=str(results))
    return results


def _append_progress(ranked: list[RankedWallet], stage_counts: dict, today: str) -> None:
    prog = Path(__file__).resolve().parents[2] / "PROGRESS.md"
    lines = [f"\n### [{today}] — Automated pipeline run", "- What ran: full pipeline (discover → enrich → analyze → rank → export)"]
    lines.append(f"- Stats: {json.dumps(stage_counts)}")
    if ranked:
        top = ranked[0]
        lines.append(
            f"- Top wallet: `{top.wallet_address[:10]}…` score {top.composite_score} "
            f"({top.trading_style}, {top.metrics.distinct_tokens} tokens, "
            f"median {top.metrics.median_return_multiple}x)"
        )
    else:
        lines.append("- No wallets passed the consistency filters this run (normal for small samples).")
    lines.append("- Next: scheduled re-run per PIPELINE_CRON; details in results/stats.json")
    with open(prog, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
