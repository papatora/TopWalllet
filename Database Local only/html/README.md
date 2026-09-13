# TopWallet Explorer (local)

Arkham-style wallet intelligence site for **Robinhood Chain (4663) only**, served on
localhost from the local snapshot. The VPS stays the scraper; this folder never talks to it.

## Run

```bash
python server.py            # http://127.0.0.1:8787
```

Or double-click `start.cmd`. The refresh icon in the nav rebuilds the dataset from
`data/topwallet.db` + `results/*.json` without restarting.

## Pages

| Route | What it is |
|---|---|
| `#/` | Overview: stats, daily buy/sell flow, classification mix, largest swaps |
| `#/leaderboard` | Arkham DEX-style podium + ranked traders (net flow / volume / swaps, 1D–All); Snipers tab |
| `#/explorer` | Arkham Labels-style: facets by activity, primary type, label; label cards |
| `#/visualizer` | Force-directed bubble map. Drag nodes to pin, pan, zoom, brush the timeline. Scopes: network, `?token=`, `?entity=`, `?wallet=` |
| `#/tokens`, `#/token/0x…` | Token screener and token page (price chart, traders, flagged wallets) |
| `#/address/0x…` | Wallet profile: cumulative flow chart, tokens, swaps, classification evidence, related wallets |

### Visualizer layers

Arkham and Bubblemaps presets, plus per-layer switches: DEX pools, CEX, bridges,
contracts, funders, bundle tx, trade edges, label-only wallets, icons, labels, flow dots.
Hiding a funder or bundle hub collapses it into direct wallet↔wallet bonds, so clusters
still hold together in raw mode. Each row in the Address list has an eye toggle.

CEX / bridge / contract icons come from `data/known_entities.json`. Add only verified
Robinhood Chain addresses, then press refresh.

## Data honesty

- `swap_events.usd_value` is empty in the snapshot, so USD is **estimated** from the
  nearest pool price point. Swaps above the pool's liquidity count as bad prices and
  stay unpriced. The UI marks these figures **est.**
- **Verified** PnL comes only from `wallet_scores` / `top_wallets_latest.json`.
- BSC research files (`wallet_data.json`, `diamond_*`, `cross_token_traders`) are not used.

## Layout

```
server.py              local HTTP server + /api/dataset, /api/rebuild (127.0.0.1 only)
dataset.py             builds the dataset from the local DB and results/
index.html             app shell
design/DESIGN.md       design system (source of truth)
design/styleguide.html visual test for every component
data/known_entities.json
assets/css/            tokens → base → components → views
assets/icons/sprite.svg
assets/js/lib/         store, fmt, ui, charts, force, graph, graph-data, evidence
assets/js/views/       dashboard, leaderboard, explorer, visualizer, tokens, token, address
```
