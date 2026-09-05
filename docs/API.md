# API

FastAPI service (compose: `api` service, port 8000; local: `python -m src.cli api`).

## GET /health
```json
{"status": "ok", "chain": "robinhood", "chain_id": 4663}
```

## GET /api/v1/top-wallets?limit=100
The latest ranked list (same payload as `results/top_wallets_latest.json`):
```json
{
  "generated_at": "2026-09-05T12:00:00+00:00",
  "total_ranked": 137,
  "wallets": [
    {
      "rank": 1,
      "wallet_address": "0xAbC…",
      "composite_score": 97.3,
      "metrics": {
        "total_positions": 47, "win_rate": 0.872,
        "median_return_multiple": 12.4, "max_return_multiple": 1043.2,
        "total_realized_pnl_usd": 2450000.0,
        "dip_buying_accuracy": 0.85, "top_selling_accuracy": 0.78,
        "consistency_score": 0.91, "distinct_tokens": 23
      },
      "top_trades": [
        {"token": "TOKEN", "ca": "0x…", "entry_price_usd": 0.0002,
         "exit_price_usd": 0.15, "return_multiple": 750.0,
         "position_size_usd": 2000.0, "pnl_usd": 1498000.0,
         "entry_date": "2026-07-01", "exit_date": "2026-07-19"}
      ],
      "trading_style": "dip_buyer_diamond_hands",
      "risk_flags": [],
      "cluster_id": null
    }
  ]
}
```

## GET /api/v1/stats
Machine-readable pipeline stats (same file as `results/stats.json`).

## GET /api/v1/track-by-ca?ca=0x…&top=50
Scores every wallet that ever traded the token and ranks them by their
**global** track record. Serves cached results when present; otherwise
computes live (may take minutes on first call).

## Errors
- `400` — malformed CA
- `404` — no results yet / unknown token
