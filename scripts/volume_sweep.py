"""VOLUME SWEEP WALLET HARVESTER — port of the user's Telegram volume bot
(VolumeNotification/bot.js) tagging state machine. Instead of notifications,
qualifying tokens are queued into run_track_by_ca() — the engine that
resolves the token's pool, upserts Token+Pool, discovers EVERY wallet that
touched the token on-chain, then prices + enriches + scores them with the
same pipeline engine (results/by_ca/<ca>.json).

Runs on the VPS via cron (*/5). Per run:
  1. GMGN /v1/market/rank interval=5m chain=robinhood (rps-budgeted)
  2. Tag gate per token (EXACT port of bot.js evaluateTag):
       first   — volume >= TAG_FLOOR for the first time
       double  — volume >= DOUBLE x the volume it was last tagged at
       trough  — volume genuinely collapsed (<= TROUGH and <= DROP x anchor)
                 since the last tag and is back >= TAG_FLOOR (dead-token
                 revive; the extra DROP guard replaces the bot's floor(500K)
                 > trough(350K) invariant, which our 100K/350K config breaks)
       sustain — volume stayed >= TAG_FLOOR continuously for SUSTAIN minutes
     On fire the anchor resets uniformly: tags[key]=vol, troughs[key]=vol,
     hot[key]=now (same as bot.js caller).
  3. Rug-risk flag: at FIRST tag, volume/liquidity >= RUG_RATIO means thin-LP
     pump (the classic 5-22 minute rug). Still queued — its snipers/dev/
     bundlers/late-buyers are exactly the serial-rugger mapping material —
     but flagged rug_risk in reports so scoring never treats it as blue-chip.
  4. Queue processing (budget TRACK_BUDGET per cycle, FIFO): run_track_by_ca
     discovers + enriches + scores the wallets. Success pops the queue;
     dead/unresolvable tokens retry then drop.
  5. Report: results/wallet_pool.json merge (GMGN top traders + sweep tags)
     + results/volume_sweep_log.jsonl per fired/processed token.

State file data/volume_sweep_state.json keeps bot.js-compatible keys
(tags/tagTrough/tagHotSince) plus rug/caQueue/lastSeen/runs.

Thresholds via env (never hardcode):
  VOLUME_SWEEP_FLOOR=100000        VOLUME_SWEEP_DOUBLE=2.0
  VOLUME_SWEEP_TROUGH=350000       VOLUME_SWEEP_TROUGH_DROP=0.7
  VOLUME_SWEEP_SUSTAIN_MINUTES=45  VOLUME_SWEEP_RUG_RATIO=15
  VOLUME_SWEEP_TOP_TRADERS=50      VOLUME_SWEEP_TRACK_BUDGET=1
  VOLUME_SWEEP_CHAIN=robinhood
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
TROUGH_DROP = float(os.getenv("VOLUME_SWEEP_TROUGH_DROP", "0.7"))
SUSTAIN_MS = float(os.getenv("VOLUME_SWEEP_SUSTAIN_MINUTES", "45")) * 60_000
RUG_RATIO = float(os.getenv("VOLUME_SWEEP_RUG_RATIO", "15"))
TOP_TRADERS = int(os.getenv("VOLUME_SWEEP_TOP_TRADERS", "50"))
TRACK_BUDGET = int(os.getenv("VOLUME_SWEEP_TRACK_BUDGET", "1"))
CHAIN = os.getenv("VOLUME_SWEEP_CHAIN", "robinhood")
QUEUE_MAX = 100
QUEUE_DROP_TRIES = 3

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
        # trough = GENUINE collapse below the anchor since the last tag.
        # bot.js needs no drop guard because its floor (500K) > trough reset
        # (350K); with our floor 100K < trough 350K, a plain `<= TROUGH`
        # test fires on every new low of a bleeding rug (anchor ratchets
        # down each commit). Require the trough to sit well below the anchor.
        trough = self.troughs.get(key, volume)
        if trough <= TROUGH and trough <= last * TROUGH_DROP:
            return "trough"
        hot_since = self.hot.get(key)
        if hot_since is not None and now_ms - hot_since >= SUSTAIN_MS:
            return "sustain"
        return None

    def commit(self, key: str, volume: float, now_ms: float) -> None:
        """Fresh anchor for ALL re-tag conditions (bot.js semantics)."""
        self.tags[key] = volume
        self.troughs[key] = volume
        self.hot[key] = now_ms


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
                "caQueue": raw.get("caQueue") or [],
                "runs": raw.get("runs") or 0,
            }
    except (ValueError, OSError) as e:
        print(f"[state] failed to load {STATE_FILE}, starting fresh: {e}")
    return {"tags": {}, "tagTrough": {}, "tagHotSince": {}, "rug": {},
            "lastSeen": {}, "caQueue": [], "runs": 0}


def save_state(st: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st), encoding="utf-8")
    tmp.replace(STATE_FILE)


def queue_push(queue: list[dict], ca: str, reason: str, vol: float,
               now_iso: str) -> bool:
    """Dedupe by CA (first reason wins), cap length (drop oldest)."""
    if any(e["ca"] == ca for e in queue):
        return False
    queue.append({"ca": ca, "reason": reason, "vol": vol, "ts": now_iso,
                  "tries": 0})
    del queue[0:max(0, len(queue) - QUEUE_MAX)]
    return True


def merge_pool(entries: dict[str, dict]) -> bool:
    """Merge harvested wallets into results/wallet_pool.json (trending
    scanner's pool) so one file lists every candidate. Atomic replace.
    On a corrupt/concurrent parse, SKIP this merge — never reset the file."""
    pool = None
    try:
        if POOL_FILE.exists():
            pool = json.loads(POOL_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        pool = None
    if pool is None:
        if POOL_FILE.exists():
            return False  # corrupt mid-write by scanner — retry next cycle
        pool = {"wallets": {}, "updated_at": None, "runs": 0}
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
    return True


def append_log(record: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


async def process_queue(queue: list[dict], budget: int) -> list[dict]:
    """FIFO run_track_by_ca for queued tokens. Success pops; None (no
    DexScreener pair, token likely dead) or exceptions retry then drop.
    One token's failure never kills the cycle."""
    done: list[dict] = []
    if budget <= 0 or not queue:
        return done
    from src.track_by_ca import run_track_by_ca

    processed = 0
    for entry in list(queue):
        if processed >= budget:
            break
        ca = entry["ca"]
        try:
            payload = await run_track_by_ca(ca, top_n=50)
        except Exception as e:  # lock contention, network, apapun — retry
            entry["tries"] = int(entry.get("tries") or 0) + 1
            entry["error"] = str(e)[:160]
            if entry["tries"] >= QUEUE_DROP_TRIES:
                queue.remove(entry)
            append_log({"ts": datetime.now(timezone.utc).isoformat(),
                        "event": "track_ca_error", "token": ca,
                        "tries": entry["tries"], "error": entry["error"]})
            continue
        if payload is None:
            entry["tries"] = int(entry.get("tries") or 0) + 1
            if entry["tries"] >= QUEUE_DROP_TRIES:
                queue.remove(entry)
            append_log({"ts": datetime.now(timezone.utc).isoformat(),
                        "event": "track_ca_unresolved", "token": ca,
                        "tries": entry["tries"]})
            continue
        queue.remove(entry)
        processed += 1
        ranked = payload.get("ranked_wallets") or []
        rec = {"ts": datetime.now(timezone.utc).isoformat(),
               "event": "track_ca_done", "token": ca,
               "wallets_analyzed": payload.get("total_wallets_analyzed"),
               "top_score": ranked[0]["composite_score"] if ranked else None}
        done.append(rec)
        append_log(rec)
    return done


async def run_cycle() -> dict:
    st = load_state()
    st["runs"] = int(st.get("runs") or 0) + 1
    tags = TagState(st["tags"], st["tagTrough"], st["tagHotSince"])
    queue: list[dict] = st["caQueue"]
    g = GmgnClient(rps=1.5)
    now_ms = time.time() * 1000
    now_iso = datetime.now(timezone.utc).isoformat()
    fired: list[dict] = []
    pool_entries: dict[str, dict] = {}
    items: list = []

    try:
        items = g.trending(CHAIN, "5m", order_by="volume", limit=50)
        for it in dedupe_by_symbol_keep_highest_volume(items):
            ca = str(pick(it, ("address", "contract", "ca")) or "").lower()
            if not ca or len(ca) != 42:
                continue
            key = token_key(CHAIN, ca)
            vol = float(pick(it, ("volume", "vol", "volume_5m", "vol_5m")) or 0)
            liq = float(pick(it, ("liquidity", "liq", "liquidity_usd")) or 0)
            st["lastSeen"][key] = now_iso

            reason = tags.evaluate(key, vol, now_ms)
            if reason is None:
                continue

            rug = bool(st["rug"].get(key))
            if reason == "first":
                rug = liq > 0 and (vol / liq) >= RUG_RATIO
                st["rug"][key] = rug
            tags.commit(key, vol, now_ms)  # bot.js: commit BEFORE slow sends
            queue_push(queue, ca, reason, vol, now_iso)

            # GMGN top traders feed the pool REPORT only; wallet harvest
            # itself happens inside run_track_by_ca (on-chain, complete).
            traders = g.token_top_traders(CHAIN, ca, limit=TOP_TRADERS)
            traders = traders if isinstance(traders, list) else []

            sym = str(pick(it, ("symbol", "token_symbol", "name")) or "?")
            rec = {"ts": now_iso, "event": "fired", "chain": CHAIN,
                   "token": ca, "symbol": sym, "volume_5m": vol,
                   "liquidity": liq, "reason": reason, "rug_risk": rug,
                   "gmgn_traders": len(traders),
                   "queued": queue[-1]["ca"] == ca}
            fired.append(rec)
            append_log(rec)

            for tr in traders:
                addr = str(tr.get("address") or tr.get("wallet") or "").lower()
                if not addr or addr in (ZERO_ADDR, BURN_ADDR):
                    continue
                e = pool_entries.setdefault(addr, {
                    "chains": [], "tokens": [], "tags": [],
                    "pnl_30d": None, "win_rate": None})
                if CHAIN not in e["chains"]:
                    e["chains"].append(CHAIN)
                if ca not in e["tokens"]:
                    e["tokens"].append(ca)
                for t in (tr.get("tags") or []):
                    e["tags"].append(f"sweep:{t}" if ":" not in str(t) else str(t))
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
        keep = set(fresh_ls) | set(k for k in tags.tags if k not in st["lastSeen"])
        st["lastSeen"] = fresh_ls
        st["tags"] = {k: v for k, v in tags.tags.items() if k in keep}
        st["tagTrough"] = {k: v for k, v in tags.troughs.items() if k in keep}
        st["tagHotSince"] = {k: v for k, v in tags.hot.items() if k in keep}
        st["rug"] = {k: v for k, v in st["rug"].items() if k in keep}
        st["caQueue"] = queue
        save_state(st)
        merge_pool(pool_entries)
        g.close()

    # queue processing AFTER state is committed — a crash here loses nothing
    done = await process_queue(queue, TRACK_BUDGET)
    save_state(st)  # queue changed during processing

    return {"tokens_polled": len(items), "fired": fired,
            "processed": done, "queue_len": len(queue)}


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
                      "processed": len(result["processed"]),
                      "queue": result["queue_len"],
                      "tokens_polled": result["tokens_polled"]}))
    for r in result["fired"]:
        print(f"  {r['symbol']} vol={r['volume_5m']:.0f} {r['reason']}"
              f"{' RUG-RISK' if r['rug_risk'] else ''}")
    for r in result["processed"]:
        print(f"  track-ca {r['token'][:10]}… wallets={r['wallets_analyzed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
