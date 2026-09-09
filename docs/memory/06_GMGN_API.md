# 06 — GMGN OPENAPI REFERENCE (verified working)

## AUTH
```
Base: https://openapi.gmgn.ai
Headers: X-APIKEY: gmgn_solbscbaseethmonadtron
Params: timestamp (unix sec, ±5s) + client_id (UUID, 7s replay)
Rate: public test key — gunakan rps 1.5-2.0, budget per run
Rotate keys kalau ada 2 key (user sebut ada 2)
```

## CLIENT
```
Sudah ada: src/discover/gmgn_client.py (GmgnClient class)
Import: from src.discover.gmgn_client import GmgnClient
Usage: g = GmgnClient(rps=2.0); g.trending("robinhood", "1h", limit=50)
```

## ENDPOINTS (semua verified 200 OK)
```
GET  /v1/market/rank                  trending tokens
     params: chain, interval (1m/5m/1h/6h/24h), order_by (volume/swaps/mc), limit
GET  /v1/token/info                   price, volume, MC, dev stats
     params: chain, address
GET  /v1/token/security               honeypot, bundler %, insider %, top10
     params: chain, address
GET  /v1/market/token_top_holders     top 100 holders + PnL + tags
     params: chain, address, limit
GET  /v1/market/token_top_traders     top traders + realized profit
     params: chain, address, order_by (profit), limit
GET  /v1/market/token_kline           OHLCV candles
     params: chain, address, interval (30s/1m/5m/15m/1h/4h/1d), limit
POST /v1/market/token_signal          real-time signals
GET  /v1/user/wallet_stats            win rate, PnL, tokens traded
     params: chain, wallet_address, period (1d/7d/30d)
POST /v1/user/wallet_profits          profit breakdown
GET  /v1/user/wallet_activity         tx ledger
GET  /v1/user/created_tokens          all tokens by creator

Response format: {code: 0, data: {code: 0, data: {...actual data}}}
GmgnClient sudah unwrap otomatis.
```

## TAGS (untuk filtering holders/traders)
```
smart_degen    — wallet pintar yang diakui GMGN
renowned       — wallet terkenal (CT/KOL)
fresh_wallet   — wallet baru (<30 hari)
sniper         — beli di blok pertama
rat_trader     — pola dumping/scam
bundler        — bagian dari bundling attack
dev            — deployer token
```

## CHAINS SUPPORTED
```
sol, bsc, base, eth, robinhood, arc, stable
```

## PAYG (untuk rate limit lebih tinggi)
```
Public test key cukup untuk scanning basic.
Kalau perlu lebih, user harus beli GMGN API plan (bukan gratis).
```
