# 09 — VPS OPERATIONS RUNBOOK

## SSH ACCESS
```
Host: 78.31.250.202 · User: root · Password: di file creds user
SSH dari Windows pakai paramiko (sudah terinstall di venv)
⚠️ Jangan reconnect terlalu cepat → 10054 reset. Tunggu 30+ detik.
```

## SERVICES (systemd)
```
topwallet-supervisor — pipeline loop (enrich,prices,analyze)
topwallet-api        — FastAPI (SAAT INI DISABLED — buka saat data matang)
cron:
  */30 * * * * trending_scanner.py  (GMGN trending → wallet pool)
  0 * * * *    watchdog.py          (LLM health check)
```

## COMMON COMMANDS
```bash
# Check status
systemctl is-active topwallet-supervisor
cat /opt/topwallet/results/supervisor_status.json

# Check pipeline log
tail -20 /opt/topwallet/logs/supervisor_pipeline.log | grep -v httpx

# Check wallet/event counts
cd /opt/topwallet && .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/topwallet.db'); print(c.execute('select count(*) from wallets').fetchone())"

# Manual pipeline cycle (JANGAN saat cycle jalan!)
cd /opt/topwallet && .venv/bin/python -m src.cli pipeline

# Deploy code update
cd /opt/topwallet && git fetch origin main && git reset --hard origin/main && systemctl restart topwallet-supervisor
```

## TROUBLESHOOTING
```
"database is locked" → jangan 2 pipeline bersamaan, tunggu cycle selesai
Blockscout 500 → retry otomatis, kalau massal tunggu 5-10 menit
RPC 429 → circuit breaker aktif, tunggu atau ganti endpoint
Endpoint log probe blocked → probe harus dapat >0 logs, kalau 0 semua = jangan block
getLogs "range skipped" → normal, adaptive shrinking jalan
```

## ENV VARS (.env di VPS)
```
TOPWALLET_RUN_ENV=vps
DATABASE_URL=sqlite+aiosqlite:////opt/topwallet/data/topwallet.db
EVM_RPC_ENDPOINTS=https://rpc.mainnet.chain.robinhood.com
BLOCKSCOUT_API_URL=https://robinhoodchain.blockscout.com
GITHUB_TOKEN=<token>
GITHUB_REPO=papatora/TopWalllet
AUTO_PUSH_RESULTS=true
ZAI_API_KEY=<key>
ZAI_BASE_URL=https://api.z.ai/api/coding/paas/v4
ZAI_MODEL=glm-5.3-flash
MAX_TOKENS=300
ENRICH_CONCURRENCY=6
GMGN_API_KEY=gmgn_solbscbaseethmonadtron
```
