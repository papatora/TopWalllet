"""Trending-based Smart Wallet Scanner (S-27 scaling directive).

Runs on the VPS. Every run:
  1. Pulls GMGN trending tokens for bsc + robinhood across intervals (1m/5m/1h/6h/24h)
  2. For each trending token: top 100 traders with GMGN's own tags
     (smart_degen/sniper/bundler/dev/fresh_wallet/rat_trader/renowned)
  3. Accumulates a de-duplicated wallet pool into results/wallet_pool.json
     with per-wallet: tags, tokens traded, win_rate, pnl (from wallet_stats
     for the top movers only — rate-limit aware)

Target: 100K candidate wallets → ultra deep-check cuts ~90% → diamond list.
"""
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.discover.gmgn_client import GmgnClient

POOL_FILE = "/opt/topwallet/results/wallet_pool.json"
CHAINS = ["bsc", "robinhood"]
INTERVALS = ["1m", "5m", "1h", "6h", "24h"]
STATS_BUDGET = 400  # wallet_stats calls per run (rate-limit aware)


def load_pool():
    if os.path.exists(POOL_FILE):
        return json.load(open(POOL_FILE))
    return {"wallets": {}, "updated_at": None, "runs": 0}


def save_pool(pool):
    pool["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(pool, open(POOL_FILE, "w"), indent=1)


def main():
    g = GmgnClient(rps=2.0)
    pool = load_pool()
    pool["runs"] = pool.get("runs", 0) + 1
    seen_tokens = set()
    stats_used = 0
    tokens_scanned = 0

    for chain in CHAINS:
        for interval in INTERVALS:
            tokens = g.trending(chain, interval, limit=30)
            for t in tokens:
                ca = (t.get("address") or "").lower()
                if not ca or ca in seen_tokens:
                    continue
                seen_tokens.add(ca)
                tokens_scanned += 1
                traders = g.token_top_traders(chain, ca, limit=100)
                if not isinstance(traders, list):
                    continue
                for tr in traders:
                    w = (tr.get("address") or tr.get("wallet") or "").lower()
                    if not w:
                        continue
                    entry = pool["wallets"].setdefault(w, {
                        "chains": set(), "tokens": [], "tags": set(),
                        "pnl_30d": None, "win_rate": None,
                    })
                    if isinstance(entry["chains"], list):
                        entry["chains"] = set(entry["chains"])
                    entry["chains"].add(chain)
                    if ca not in entry["tokens"]:
                        entry["tokens"].append(ca)
                    for tag in (tr.get("tags") or []):
                        entry["tags"].add(tag)
                    # promote top movers' stats within budget
                    if stats_used < STATS_BUDGET and entry.get("pnl_30d") is None:
                        try:
                            st = g.wallet_stats(chain, w, "30d")
                            pnl = st.get("realized_profit") if isinstance(st, dict) else None
                            pnl_stat = (st or {}).get("pnl_stat", {}) or {}
                            entry["pnl_30d"] = pnl
                            entry["win_rate"] = pnl_stat.get("winrate")
                            stats_used += 1
                        except Exception:
                            pass
                # normalize sets for json
                for w, entry in pool["wallets"].items():
                    if isinstance(entry.get("chains"), set):
                        entry["chains"] = list(entry["chains"])
                    if isinstance(entry.get("tags"), set):
                        entry["tags"] = sorted(entry["tags"])
                save_pool(pool)

            save_pool(pool)

    save_pool(pool)
    total = len(pool["wallets"])
    tagged = sum(1 for e in pool["wallets"].values() if e.get("tags"))
    print(f"scan done: tokens={tokens_scanned} total_wallets={total} tagged={tagged} stats_used={stats_used}")
    g.close()


if __name__ == "__main__":
    main()
