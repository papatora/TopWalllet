"""VOLUME SWEEP WALLET HARVESTER — port of the user's Telegram volume bot
(VolumeNotification/bot.js) tagging state machine, but instead of sending
notifications we HARVEST THE WALLETS behind qualifying tokens.

Runs on the VPS via cron (*/5). Per run:
  1. GMGN /v1/market/rank interval=5m chain=robinhood (rps-budgeted)
  2. Tag gate per token (EXACT port of bot.js evaluateTag):
       first   — volume >= TAG_FLOOR for the first time
       double  — volume >= DOUBLE x the volume it was last tagged at
       trough  — volume dipped <= TAG_TROUGH at some point since the last
                 tag and is now back >= TAG_FLOOR (dead token revive)
       sustain — volume stayed >= TAG_FLOOR continuously for SUSTAIN minutes
     On fire the anchor resets uniformly: tags[key]=vol, troughs[key]=vol,
     hot[key]=now (same as bot.js lines around evaluateTag caller).
  3. Rug-risk flag: at FIRST tag, volume/liquidity >= RUG_RATIO means thin-LP
     pump (the classic 5-22 minute rug). Token still gets harvested — its
     snipers/dev/bundlers are exactly the serial ruggers we want — but it is
     flagged rug_risk so downstream scoring does not treat it as blue-chip.
  4. Harvest per qualifying token (priority order):
       a. first buyers  <=10 blocks  (sniper-early)  [Etherscan tokentx asc]
       b. first buyers  <=300 blocks (dev-early) + same-tx bundle members
       c. GMGN top traders (pnl-ranked)
       d. late entrants into rug_risk tokens -> RUG_VICTIM candidates
  5. Persist: wallets table (status=pending -> pipeline enrich picks them up)
     + wallet_token_interest(source='vol_sweep:<reason>') + results/
     wallet_pool.json merge + results/volume_sweep_log.jsonl.

State file data/volume_sweep_state.json keeps bot.js-compatible keys
(tags/tagTrough/tagHotSince) so the mental model transfers 1:1.

Heuristics documented in docs/DIRECTIVE_VOLUME_SWEEP.md; thresholds via env:
  VOLUME_SWEEP_FLOOR=100000  VOLUME_SWEEP_DOUBLE=2.0  VOLUME_SWEEP_TROUGH=350000
  VOLUME_SWEEP_SUSTAIN_MINUTES=45  VOLUME_SWEEP_RUG_RATIO=15
  VOLUME_SWEEP_TOP_TRADERS=50  VOLUME_SWEEP_MAX_WALLETS=150
  VOLUME_SWEEP_CHAIN=robinhood  VOLUME_SWEEP_ASC_PAGES=3
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # POSIX only; Windows (unit-test env) runs the no-lock path
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from config.settings import settings  # noqa: E402
from src.discover.gmgn_client import GmgnClient  # noqa: E402

FLOOR = float(os.getenv("VOLUME_SWEEP_FLOOR", "100000"))
DOUBLE = float(os.getenv("VOLUME_SWEEP_DOUBLE", "2.0"))
TROUGH = float(os.getenv("VOLUME_SWEEP_TROUGH", "350000"))
SUSTAIN_MS = float(os.getenv("VOLUME_SWEEP_SUSTAIN_MINUTES", "45")) * 60_000
RUG_RATIO = float(os.getenv("VOLUME_SWEEP_RUG_RATIO", "15"))
TOP_TRADERS = int(os.getenv("VOLUME_SWEEP_TOP_TRADERS", "50"))
MAX_WALLETS = int(os.getenv("VOLUME_SWEEP_MAX_WALLETS", "150"))
CHAIN = os.getenv("VOLUME_SWEEP_CHAIN", "robinhood")
ASC_PAGES = int(os.getenv("VOLUME_SWEEP_ASC_PAGES", "3"))
SNIPER_BLOCKS = 10
EARLY_BLOCKS = 300
BUNDLE_MIN_WALLETS = 4

STATE_FILE = Path(REPO_ROOT) / "data" / "volume_sweep_state.json"
POOL_FILE = Path(settings.results_dir) / "wallet_pool.json"
LOG_FILE = Path(settings.results_dir) / "volume_sweep_log.jsonl"
LOCK_FILE = Path(REPO_ROOT) / "data" / ".volume_sweep.lock"

ZERO_ADDR = "0x" + "0" * 40
BURN_ADDR = "0x" + "0" * 38 + "dead"


def pick(obj: dict, keys: tuple[str, ...]):
    """bot.js pick(): first present, non-empty value among candidate keys."""
    for k in keys:
        v = obj.get(k)
        if v is not None and v != "":
            return v
    return None


def token_key(chain: str, ca: str) -> str:
    return f"{chain}:{(ca or '').lower()}"


def dedupe_by_symbol_keep_highest_volume(items: list[dict]) -> list[dict]:
    """Port of bot.js dedupeBySymbolKeepHighestVolume: fake/copycat tokens
    share a ticker — only the highest-volume contract per symbol survives."""
    best: dict[str, dict] = {}
    for it in items:
        sym = str(pick(it, ("symbol", "token_symbol", "name")) or "").upper()
        vol = float(pick(it, ("volume", "vol", "volume_5m", "vol_5m")) or 0)
        cur = best.get(sym)
        if cur is None or vol > cur["_vol"]:
            best[sym] = {**it, "_vol": vol}
    out = []
    for v in best.values():
        v.pop("_vol", None)
        out.append(v)
    return out


class TagState:
    """Volume-tag gate — faithful port of bot.js evaluateTag side effects:
    trough/hotSince are updated on EVERY call (even when not eligible)."""

    def __init__(self, tags: dict | None = None, troughs: dict | None = None,
                 hot: dict | None = None):
        self.tags: dict[str, float] = tags or {}
        self.troughs: dict[str, float] = troughs or {}
        self.hot: dict[str, float] = hot or {}

    def evaluate(self, key: str, volume: float, now_ms: float) -> str | None:
        last = self.tags.get(key)
        if last is None:
            return "first" if volume >= FLOOR else None

        self.troughs[key] = min(self.troughs.get(key, last), volume)

        if volume < FLOOR:
            self.hot.pop(key, None)
            return None
        self.hot.setdefault(key, now_ms)

        if volume >= last * DOUBLE:
            return "double"
        # trough = volume GENUINELY dropped below the anchor since the last
        # tag, then came back >= floor. bot.js can skip the `trough < last`
        # guard because its floor (500K) > trough reset (350K); with our
        # floor 100K < trough 350K the guard is what stops a freshly-tagged
        # 100-350K token from re-firing 'trough' on every poll.
        trough = self.troughs.get(key, volume)
        if trough <= TROUGH and trough < last:
            return "trough"
        hot_since = self.hot.get(key)
        if hot_since is not None and now_ms - hot_since >= SUSTAIN_MS:
            return "sustain"
        return None

    def commit(self, key: str, volume: float, now_ms: float) -> None:
        """Fresh anchor for ALL three re-tag conditions (bot.js semantics)."""
        self.tags[key] = volume
        self.troughs[key] = volume
        self.hot[key] = now_ms


def classify_transfers(items: list[dict]) -> dict:
    """On-chain first-buyer / bundle / late-buyer evidence from ascending
    token transfers (Blockscout-shaped items). Pool/router addresses are
    heuristically excluded: a recipient absorbing >50% of early transfers
    (>=20) is liquidity infrastructure, not a buyer."""
    rows = []
    for it in items:
        blk = int(it.get("block_number") or 0)
        to = ((it.get("to") or {}).get("hash") or "").lower()
        frm = ((it.get("from") or {}).get("hash") or "").lower()
        tx = (it.get("transaction_hash") or "").lower()
        if blk:
            rows.append((blk, to, frm, tx))
    if not rows:
        return {"b0": 0, "b1": 0, "sniper": [], "early": [], "bundles": [],
                "late": [], "excluded": []}
    rows.sort(key=lambda r: r[0])  # order-agnostic (fallback = newest-first)
    b0 = min(r[0] for r in rows)
    b1 = max(r[0] for r in rows)

    to_count: dict[str, int] = {}
    for _, to, _, _ in rows:
        if to:
            to_count[to] = to_count.get(to, 0) + 1
    excluded = {a for a, c in to_count.items() if c >= 20 and c > 0.5 * len(rows)}

    first_blk: dict[str, int] = {}
    for blk, to, _, _ in rows:  # ascending input -> first occurrence wins
        if to and to not in first_blk:
            first_blk[to] = blk

    buyers = {a: b for a, b in first_blk.items()
              if a not in (ZERO_ADDR, BURN_ADDR) and a not in excluded}
    sniper = sorted(a for a, b in buyers.items() if b <= b0 + SNIPER_BLOCKS)
    early = sorted(a for a, b in buyers.items()
                   if b0 + SNIPER_BLOCKS < b <= b0 + EARLY_BLOCKS)

    by_tx: dict[str, set[str]] = {}
    for blk, to, _, tx in rows:
        if blk <= b0 + EARLY_BLOCKS and to in buyers:
            by_tx.setdefault(tx, set()).add(to)
    bundles = sorted(tx for tx, ws in by_tx.items() if len(ws) >= BUNDLE_MIN_WALLETS)

    late_cut = b0 + 0.7 * (b1 - b0)
    late = sorted(a for a, b in buyers.items() if b >= late_cut)
    return {"b0": b0, "b1": b1, "sniper": sniper, "early": early,
            "bundles": bundles, "late": late, "excluded": sorted(excluded)}


def load_state() -> dict:
    try:
        if STATE_FILE.exists():
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return {
                "tags": raw.get("tags") or {},
                "tagTrough": raw.get("tagTrough") or {},
                "tagHotSince": raw.get("tagHotSince") or {},
                "rug": raw.get("rug") or {},
                "lastSeen": raw.get("lastSeen") or {},
                "runs": raw.get("runs") or 0,
            }
    except (ValueError, OSError) as e:
        print(f"[state] failed to load {STATE_FILE}, starting fresh: {e}")
    return {"tags": {}, "tagTrough": {}, "tagHotSince": {}, "rug": {},
            "lastSeen": {}, "runs": 0}


def save_state(st: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st), encoding="utf-8")
    tmp.replace(STATE_FILE)


def merge_pool(entries: dict[str, dict]) -> None:
    """Merge harvested wallets into results/wallet_pool.json (trending
    scanner's pool) so one file lists every candidate. Atomic replace."""
    pool = {"wallets": {}, "updated_at": None, "runs": 0}
    try:
        if POOL_FILE.exists():
            pool.update(json.loads(POOL_FILE.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        pass
    wallets = pool.get("wallets") or {}
    for addr, e in entries.items():
        cur = wallets.get(addr) or {"chains": [], "tokens": [], "tags": [],
                                    "pnl_30d": None, "win_rate": None}
        for field in ("chains", "tokens"):
            for v in e.get(field, []):
                if v not in cur[field]:
                    cur[field].append(v)
        tags = set(cur.get("tags") or []) | set(e.get("tags") or [])
        cur["tags"] = sorted(tags)
        if e.get("pnl_30d") is not None and cur.get("pnl_30d") is None:
            cur["pnl_30d"] = e["pnl_30d"]
        wallets[addr] = cur
    pool["wallets"] = wallets
    pool["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POOL_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(pool, indent=1), encoding="utf-8")
    tmp.replace(POOL_FILE)


def append_log(record: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


async def persist_wallets(rows: list[dict]) -> int:
    """Insert Wallet(status=pending) + WalletTokenInterest for new wallets.
    Existing wallets get the interest edge only (no re-enrich)."""
    if not rows:
        return 0
    from sqlalchemy import select

    from src.db.database import get_session_factory
    from src.db.models import Wallet, WalletTokenInterest

    inserted = 0
    factory = get_session_factory()
    async with factory() as session:
        for r in rows:
            addr = r["address"]
            if await session.get(Wallet, addr) is None:
                session.add(Wallet(address=addr))
                inserted += 1
            exists = await session.execute(
                select(WalletTokenInterest.id).where(
                    WalletTokenInterest.wallet_address == addr,
                    WalletTokenInterest.token_address == r["token_address"],
                    WalletTokenInterest.source == r["source"],
                ))
            if exists.first() is None:
                session.add(WalletTokenInterest(
                    wallet_address=addr,
                    token_address=r["token_address"],
                    source=r["source"],
                ))
        await session.commit()
    return inserted


async def harvest(ca: str, reason: str, rug_risk: bool,
                  g: GmgnClient, explorer) -> dict:
    """Collect candidate wallets for one qualifying token. Priority:
    snipers > early/bundle > GMGN top traders; late entrants appended when
    rug_risk (they are the rug's exit liquidity — mapping material)."""
    evidence: dict = {"gmgn_traders": 0, "transfers": 0}

    # earliest transfers first (sort=asc) — ASC_PAGES*200 rows reach the
    # token's birth blocks even for tokens with deep history. Blockscout
    # fallback tidak kenal kwarg sort (degraded: dapat baris terbaru).
    try:
        asc = await explorer.address_token_transfers(ca, max_pages=ASC_PAGES,
                                                     sort="asc")
    except TypeError:
        asc = await explorer.address_token_transfers(ca, max_pages=ASC_PAGES)
    cls = classify_transfers(asc)
    evidence["transfers"] = len(asc)

    traders = g.token_top_traders(CHAIN, ca, limit=TOP_TRADERS)
    traders = traders if isinstance(traders, list) else []
    evidence["gmgn_traders"] = len(traders)

    rows: list[dict] = []
    seen: set[str] = set()

    def add(addr: str, tag: str) -> None:
        addr = (addr or "").lower()
        if not addr or addr in (ZERO_ADDR, BURN_ADDR) or addr in seen:
            return
        if len(rows) >= MAX_WALLETS:
            return
        seen.add(addr)
        rows.append({"address": addr, "token_address": ca,
                     "source": f"vol_sweep:{reason}"[:24],
                     "tag": tag, "rug_risk": rug_risk})

    for a in cls["sniper"]:
        add(a, "sniper_early")
    for a in cls["early"]:
        add(a, "dev_early")
    for tx in cls["bundles"]:
        for it in asc:
            if (it.get("transaction_hash") or "").lower() == tx:
                add((it.get("to") or {}).get("hash"), "bundle")
    for tr in traders:
        add(tr.get("address") or tr.get("wallet"), "top_trader")
    if rug_risk:
        for a in cls["late"]:
            add(a, "rug_victim")
    return {"rows": rows, "evidence": evidence, "classify": cls}


async def run_cycle() -> dict:
    from src.utils.etherscan_client import make_explorer_client

    st = load_state()
    st["runs"] = int(st.get("runs") or 0) + 1
    tags = TagState(st["tags"], st["tagTrough"], st["tagHotSince"])
    g = GmgnClient(rps=1.5)
    explorer = make_explorer_client(rps=2.0)
    now_ms = time.time() * 1000
    fired: list[dict] = []
    pool_entries: dict[str, dict] = {}

    try:
        items = g.trending(CHAIN, "5m", order_by="volume", limit=50)
        for it in dedupe_by_symbol_keep_highest_volume(items):
            ca = str(pick(it, ("address", "contract", "ca")) or "").lower()
            if not ca or len(ca) != 42:
                continue
            key = token_key(CHAIN, ca)
            vol = float(pick(it, ("volume", "vol", "volume_5m", "vol_5m")) or 0)
            liq = float(pick(it, ("liquidity", "liq", "liquidity_usd")) or 0)
            st["lastSeen"][key] = datetime.now(timezone.utc).isoformat()

            reason = tags.evaluate(key, vol, now_ms)
            if reason is None:
                continue

            rug = bool(st["rug"].get(key))
            if reason == "first":
                rug = liq > 0 and (vol / liq) >= RUG_RATIO
                st["rug"][key] = rug
            tags.commit(key, vol, now_ms)  # bot.js: commit BEFORE slow sends

            h = await harvest(ca, reason, rug, g, explorer)
            inserted = await persist_wallets(h["rows"])

            sym = str(pick(it, ("symbol", "token_symbol", "name")) or "?")
            rec = {"ts": datetime.now(timezone.utc).isoformat(),
                   "chain": CHAIN, "token": ca, "symbol": sym,
                   "volume_5m": vol, "liquidity": liq, "reason": reason,
                   "rug_risk": rug, "wallets_found": len(h["rows"]),
                   "wallets_new": inserted,
                   "sniper": len(h["classify"]["sniper"]),
                   "bundles": len(h["classify"]["bundles"]),
                   "b0": h["classify"]["b0"], "b1": h["classify"]["b1"]}
            fired.append(rec)
            append_log(rec)

            for r in h["rows"]:
                e = pool_entries.setdefault(r["address"], {
                    "chains": [], "tokens": [], "tags": [],
                    "pnl_30d": None, "win_rate": None})
                if CHAIN not in e["chains"]:
                    e["chains"].append(CHAIN)
                if ca not in e["tokens"]:
                    e["tokens"].append(ca)
                e["tags"].append(r["tag"])
    finally:
        # prune tokens unseen for 7 days so the state file cannot grow forever
        cutoff = time.time() - 7 * 86400
        fresh_ls = {}
        for k, iso in st["lastSeen"].items():
            try:
                if datetime.fromisoformat(iso).timestamp() >= cutoff:
                    fresh_ls[k] = iso
            except ValueError:
                fresh_ls[k] = iso
        keep = set(fresh_ls) | {k for k in tags.tags
                                if k not in st["lastSeen"]}
        st["lastSeen"] = fresh_ls
        st["tags"] = {k: v for k, v in tags.tags.items() if k in keep}
        st["tagTrough"] = {k: v for k, v in tags.troughs.items() if k in keep}
        st["tagHotSince"] = {k: v for k, v in tags.hot.items() if k in keep}
        st["rug"] = {k: v for k, v in st["rug"].items() if k in keep}
        save_state(st)
        merge_pool(pool_entries)
        g.close()

    return {"tokens_polled": len(items), "fired": fired,
            "pool_new": len(pool_entries)}


async def main() -> int:
    if os.getenv("TOPWALLET_RUN_ENV") != "vps" and not os.getenv("FORCE_LOCAL"):
        print("volume_sweep: butuh TOPWALLET_RUN_ENV=vps (scraping = VPS only, "
              "lihat SECURITY_POLICY ATURAN 1/2)")
        return 2
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock = LOCK_FILE.open("w")
    if fcntl is not None:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("volume_sweep: run sebelumnya masih jalan — skip")
            return 0
    try:
        result = await run_cycle()
    finally:
        lock.close()
    print(json.dumps({"fired": len(result["fired"]),
                      "pool_new": result["pool_new"],
                      "tokens_polled": result["tokens_polled"]}))
    for r in result["fired"]:
        print(f"  {r['symbol']} vol={r['volume_5m']:.0f} {r['reason']}"
              f"{' RUG-RISK' if r['rug_risk'] else ''} "
              f"wallets={r['wallets_found']} new={r['wallets_new']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
