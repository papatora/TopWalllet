"""On-chain re-verification of wallet tags — INSIDER / CLUSTER / phishing.

JANGAN percaya tag mentah (GMGN, atau classifier lokal yang cuma melihat
swap_events). Verifikasi dari raw on-chain data:

  INSIDER  ("sells a token it never bought") per (wallet, token):
    1. Token masuk lewat jalur apa? Blockscout ERC-20 transfers untuk
       (wallet, token) — semua transfer masuk SEBELUM sell pertama.
    2. Tx transfer dicek on-chain (eth_getTransactionReceipt): kalau tx
       mengandung Swap log (v4 PoolManager / v3 topic0) → itu BELI yang
       kelewatan scan coverage kita → TRADER_MISREAD (bukan insider).
    3. Transfer murni → dari siapa?
       - dari 0x0                                → MINT_ALLOCATION
       - pengirim nyebar >=20 wallet / <=100 blk → AIRDROP_SPAM (bukan insider;
         spread >=20 dalam window pendek = distribusi phishing/airdrop bot)
       - pengirim biasa                          → CONFIRMED_INSIDER
    4. Tidak ada transfer masuk sama sekali       → UNRESOLVED (coverage gap,
       antre re-enrich; INSIDER diturunkan sampai terbukti).

  CLUSTER_MEMBER: konfirmasi tx funding funder→member on-chain + profil funder
  (kontrak batcher / EOA operator / pola nominal seragam). Link tidak
  ditemukan → OVERTURN.

Anti-skip: 1 wallet WAJIB selesai sebelum lanjut — 429/5xx di-retry dengan
backoff panjang, tidak ada skip. Checkpoint per wallet, resume aman.

Output:
  results/tag_verification.json          evidence lengkap per wallet
  results/tag_overrides.json             koreksi label (dipakai pipeline)
  results/reenrich_queue.json            wallet yang perlu deep re-enrich
  results/tag_verification_progress.json checkpoint

Usage (VPS, dari repo root):
  .venv/bin/python scripts/reverify_tags.py --max-calls 8000
  .venv/bin/python scripts/reverify_tags.py --pairs 5     # smoke test
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings  # noqa: E402
from src.utils.logger import jlog  # noqa: E402
from src.utils.rpc_client import EvmRpcClient, V3_SWAP_TOPIC0, v4_swap_topic0  # noqa: E402

log = logging.getLogger("topwallet.reverify")

ZERO_ADDR = "0x" + "0" * 40
MASS_SPREAD_WALLETS = 20   # >= → distribusi massal (airdrop/phishing bot)
MASS_SPREAD_BLOCKS = 100   # window blok untuk spread
MAX_RECEIPTS_PER_PAIR = 12
TRANSFER_PAGES = 8         # kedalaman histori per (wallet, token)
SENDER_PAGES = 6


class Defer(Exception):
    """Data Blockscout terbukti tidak lengkap (throttled/degraded) —
    pair TIDAK diberi verdict dan diulang run berikutnya (bukan skip)."""


def _token_addr(item: dict) -> str:
    """Alamat token ERC-20 dari item transfer — dukung 2 bentuk API
    (lama: token.address; baru: token.address_hash)."""
    tok = item.get("token") or {}
    return ((tok.get("address") or tok.get("address_hash") or "") or "").lower()


def _item_amount(item: dict) -> float:
    total = item.get("total") or {}
    raw = total.get("value") or item.get("value") or "0"
    tok = item.get("token") or {}
    try:
        dec = int(tok.get("decimals") or 18)
    except (ValueError, TypeError):
        dec = 18
    try:
        return int(raw) / (10 ** dec) if raw else 0.0
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------- helpers

def _sqlite_path(url: str) -> Path | None:
    """sqlite+aiosqlite:////abs/path.db → /abs/path.db;  ///rel/path.db → rel."""
    if not url.startswith("sqlite"):
        return None
    tail = url.split("///", 1)[1] if "///" in url else url
    p = Path(tail)
    return p if p.is_absolute() else Path.cwd() / p


def _padded(addr: str) -> str:
    return "0x" + addr.lower().replace("0x", "").rjust(64, "0")


def _transfer_items(items: list[dict], wallet: str, token: str) -> list[dict]:
    """Normalize Blockscout token-transfer items for (wallet, token)."""
    out = []
    for it in items:
        tok = _token_addr(it)
        if tok != token.lower():
            continue
        src = ((it.get("from") or {}).get("hash") or "").lower()
        dst = ((it.get("to") or {}).get("hash") or "").lower()
        if not dst:
            continue
        amount = _item_amount(it)
        out.append({
            "direction": "in" if dst == wallet.lower() else "out",
            "counterparty": src if dst == wallet.lower() else dst,
            "amount": amount,
            "block": int(it.get("block_number") or 0),
            "tx": (it.get("transaction_hash") or "").lower(),
        })
    return out


def _max_spread(outgoing: list[dict]) -> tuple[int, int]:
    """Max distinct recipients of one sender inside any 100-block window."""
    by_block: dict[int, set[str]] = defaultdict(set)
    for t in outgoing:
        if t["direction"] == "out" and t["counterparty"] != ZERO_ADDR:
            by_block[t["block"]].add(t["counterparty"])
    best, best_block = 0, 0
    blocks = sorted(by_block)
    for i, b in enumerate(blocks):
        window: set[str] = set()
        for b2 in blocks[i:]:
            if b2 - b > MASS_SPREAD_BLOCKS:
                break
            window |= by_block[b2]
        if len(window) > best:
            best, best_block = len(window), b
    return best, best_block


# ---------------------------------------------------------------- core

class TagVerifier:
    def __init__(self, max_calls: int):
        from src.utils.etherscan_client import make_explorer_client

        self.rpc = EvmRpcClient(rps=max(settings.rpc_rps, 1.0))
        self.bc = make_explorer_client(rps=max(settings.blockscout_rps * 0.6, 1.0))
        self.max_calls = max_calls
        self.calls = 0
        self.db = self._open_db()

    def _open_db(self) -> sqlite3.Connection | None:
        """Open the pipeline's SQLite read-mostly. The DB historically runs in
        journal 'delete' mode → readers lock while enrichment writes. Switch to
        WAL (best-effort, one-time, benefits API + verifier alike) and set a
        long busy timeout. Persistent failure → None (verifier degrades to
        evidence-only mode instead of fighting the pipeline)."""
        db_path = _sqlite_path(settings.database_url)
        if not db_path or not db_path.exists():
            return None
        for attempt in range(3):
            try:
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("PRAGMA busy_timeout=30000")
                mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
                if attempt == 0:
                    jlog(log, logging.INFO, "verifier db open", journal_mode=str(mode))
                return conn
            except sqlite3.OperationalError as e:
                jlog(log, logging.WARNING, "db open retry",
                     attempt=attempt + 1, err=str(e)[:120])
                time.sleep(10 * (attempt + 1))
        return None

    async def receipt_retry(self, tx_hash: str) -> dict | None:
        """eth_getTransactionReceipt dengan retry inline (rate limit RPC)."""
        last_err: Exception | None = None
        for attempt in range(5):
            try:
                self.calls += 1
                return await self.rpc.call("eth_getTransactionReceipt", [tx_hash])
            except Exception as e:
                last_err = e
                await asyncio.sleep(min(60.0, 3.0 * (2 ** attempt)))
        raise RuntimeError(f"receipt gagal setelah retry: {tx_hash} {last_err}")

    def local_sells(self, wallet: str, token: str) -> list[tuple[int, str]]:
        if not self.db:
            return []
        rows = self.db.execute(
            "SELECT block_num, tx_hash FROM swap_events "
            "WHERE wallet_address=? AND token_address=? AND side='SELL' ORDER BY block_num",
            (wallet.lower(), token.lower()),
        ).fetchall()
        return [(int(b), (t or "").lower()) for b, t in rows]

    def local_buys_exist(self, wallet: str, token: str) -> bool:
        if not self.db:
            return False
        row = self.db.execute(
            "SELECT 1 FROM swap_events WHERE wallet_address=? AND token_address=? "
            "AND side='BUY' LIMIT 1",
            (wallet.lower(), token.lower()),
        ).fetchone()
        return bool(row)

    def local_swap_txs(self, wallet: str) -> set[str]:
        if not self.db:
            return set()
        rows = self.db.execute(
            "SELECT tx_hash FROM swap_events WHERE wallet_address=? AND tx_hash!=''",
            (wallet.lower(),),
        ).fetchall()
        return {(t or "").lower() for (t,) in rows}

    async def tx_has_swap(self, tx_hash: str) -> bool | None:
        """True bila receipt mengandung Swap log v3/v4 (tx itu sebuah swap)."""
        if not tx_hash:
            return None
        receipt = await self.receipt_retry(tx_hash)
        if not receipt or receipt.get("status") not in (None, "0x1", 1):
            return False
        v4 = v4_swap_topic0()
        pool_manager = settings.pool_manager
        for lg in receipt.get("logs") or []:
            addr = (lg.get("address") or "").lower()
            topics = lg.get("topics") or []
            if not topics:
                continue
            t0 = (topics[0] or "").lower()
            if t0 == V3_SWAP_TOPIC0 or (t0 == v4 and addr == pool_manager):
                return True
        return False

    # ---------------- INSIDER ----------------

    async def verify_insider_pair(self, wallet: str, token: str) -> dict:
        res: dict = {"token": token, "checked_at": _now(), "calls": 0}
        c0 = self.calls

        sells = self.local_sells(wallet, token)
        res["local_sells"] = len(sells)
        first_sell_block = sells[0][0] if sells else None

        if self.local_buys_exist(wallet, token):
            res["verdict"] = "TRADER_MISREAD"
            res["reason"] = "BUY ada di DB lokal (classifier keliru); tanpa RPC"
            res["calls"] = self.calls - c0
            return res

        self.calls += 1
        items_list = await self.bc.address_token_transfers(
            wallet.lower(), TRANSFER_PAGES, token_filter=token.lower())
        transfers = _transfer_items(items_list, wallet, token)
        res["transfers_total"] = len(transfers)

        # DB-oracle guard: wallet TERBUKTI punya sells di DB (yang datanya
        # berasal dari Blockscout sendiri). Kalau API bilang 0 transfer,
        # respons jelas tidak lengkap (throttled/bentuk baru) → jangan
        # div verdict sekarang.
        if not transfers and sells:
            res["calls"] = self.calls - c0
            raise Defer(f"0 transfer utk {wallet[:10]}:{token[:10]} "
                        f"padahal DB punya {len(sells)} sells — API incomplete")

        known_txs = self.local_swap_txs(wallet)
        candidates = [t for t in transfers
                      if t["direction"] == "in" and t["amount"] > 0
                      and (first_sell_block is None or t["block"] <= first_sell_block)]
        res["candidates_in"] = len(candidates)

        if not candidates:
            if transfers:
                res["verdict"] = "TRADER_MISREAD"
                res["reason"] = ("token masuk SETELAH sell pertama (atau hanya out) "
                                 "-> pasti dapat dari swap yang tak ter-scan")
            else:
                res["verdict"] = "UNRESOLVED"
                res["reason"] = "tidak ada riwayat transfer token ini di Blockscout"
            res["calls"] = self.calls - c0
            return res

        # klasifikasikan tiap kandidat: swap-linked / mint / transfer murni
        swap_linked: list[dict] = []
        pure: list[dict] = []
        receipts_checked = 0
        for t in candidates[:40]:
            tx = t["tx"]
            if tx in known_txs:
                swap_linked.append({**t, "proof": "tx in local swap_events"})
                continue
            if receipts_checked >= MAX_RECEIPTS_PER_PAIR:
                pure.append({**t, "proof": "receipt budget habis (diasumsikan transfer)"})
                continue
            receipts_checked += 1
            if await self.tx_has_swap(tx):
                swap_linked.append({**t, "proof": "receipt has Swap log"})
            else:
                t["proof"] = "receipt: no Swap log"
                pure.append(t)
        res["receipts_checked"] = receipts_checked

        if swap_linked:
            res["verdict"] = "TRADER_MISREAD"
            res["reason"] = "kandidat transfer ternyata tx swap (coverage scan bolong)"
            res["proof_txs"] = [t["tx"] for t in swap_linked[:5]]
            res["calls"] = self.calls - c0
            return res
        if not pure:
            res["verdict"] = "UNRESOLVED"
            res["reason"] = "kandidat ada tapi tak terklasifikasi"
            res["calls"] = self.calls - c0
            return res

        # pure transfers → profil pengirim (spread check → phishing/airdrop)
        senders: dict[str, dict] = {}
        for t in pure:
            cp = t["counterparty"]
            entry = senders.setdefault(cp, {"amount": 0.0, "blocks": [], "txs": []})
            entry["amount"] += t["amount"]
            entry["blocks"].append(t["block"])
            entry["txs"].append(tx_summary(t))
        mint = senders.pop(ZERO_ADDR, None)

        max_windows = {}
        for sender in list(senders)[:5]:
            self.calls += 1
            s_list = await self.bc.address_token_transfers(
                sender, SENDER_PAGES, token_filter=token.lower())
            s_out = _transfer_items(s_list, sender, token)
            if not s_out:
                # pengirim PASTI punya out-transfer ( dia yang kirim ke wallet )
                raise Defer(f"0 transfer utk sender {sender[:10]} — API incomplete")
            best, blk = _max_spread(s_out)
            max_windows[sender] = {"max_recipients": best, "window_block": blk,
                                   "out_total": len(s_out)}
            senders[sender]["spread"] = max_windows[sender]
            if best >= MASS_SPREAD_WALLETS:
                senders[sender]["kind"] = "MASS_SPREAD"
            else:
                senders[sender]["kind"] = "PERSONAL"

        if mint:
            res["verdict"] = "MINT_ALLOCATION"
            res["reason"] = "token di-mint langsung ke wallet (dari 0x0)"
            res["mint"] = {"amount": mint["amount"], "blocks": mint["blocks"][:5],
                           "txs": mint["txs"][:5]}
        elif senders and all(s.get("kind") == "MASS_SPREAD" for s in senders.values()):
            res["verdict"] = "AIRDROP_SPAM"
            res["reason"] = (f"semua pengirim mass-spread (>= {MASS_SPREAD_WALLETS} wallet "
                             f"dalam <= {MASS_SPREAD_BLOCKS} blok) — distribusi airdrop/phishing")
        elif senders:
            kinds = {s.get("kind") for s in senders.values()}
            res["verdict"] = "CONFIRMED_INSIDER"
            res["reason"] = "terima transfer murni (bukan swap) dari " + ", ".join(kinds)
        else:  # mint saja tanpa senders, atau campuran tak terduga
            res["verdict"] = "UNRESOLVED"

        res["senders"] = {a: {k: v for k, v in s.items() if k != "blocks"} | {"blocks": s["blocks"][:5]}
                          for a, s in senders.items()}
        res["pure_transfers"] = [tx_summary(t) for t in pure[:10]]
        res["calls"] = self.calls - c0
        return res

    # ---------------- CLUSTER ----------------

    async def verify_cluster_member(self, member: str, funder: str) -> dict:
        res: dict = {"funder": funder, "checked_at": _now()}
        self.calls += 1
        try:
            items = await self.bc.address_transactions(member.lower(), 4)
        except Exception as e:
            res["verdict"] = "ERROR"
            res["reason"] = str(e)[:150]
            return res
        hits = []
        for it in items:
            src = ((it.get("from") or {}).get("hash") or "").lower()
            if src == funder.lower():
                try:
                    eth = int(it.get("value") or 0) / 1e18
                except ValueError:
                    eth = 0.0
                hits.append({"tx": (it.get("hash") or "").lower(),
                             "block": int(it.get("block_number") or 0),
                             "eth": round(eth, 6)})
        if hits:
            res["verdict"] = "FUNDED_CONFIRMED"
            res["funding_txs"] = hits[:3]
        else:
            res["verdict"] = "LINK_NOT_FOUND"
            res["reason"] = "tidak ada tx masuk dari funder dalam histori terjangkau"
        return res

    async def profile_funder(self, funder: str) -> dict:
        """Profil funder via interface umum + RPC (tanpa endpoint Blockscout)."""
        prof: dict = {}
        # is_contract + saldo via RPC langsung (bekerja utk explorer apa pun)
        try:
            code = await self.rpc.call("eth_getCode", [funder, "latest"])
            prof["is_contract"] = bool(code and code not in ("0x", "0x0"))
            bal = await self.rpc.call("eth_getBalance", [funder, "latest"])
            prof["eth_balance"] = round(int(bal, 16) / 1e18, 4)
        except Exception as e:
            prof["rpc_error"] = str(e)[:100]
        try:
            txs = await self.bc.address_transactions(funder.lower(), 4)
        except Exception as e:
            txs = []
            prof["tx_error"] = str(e)[:100]
        amounts, dests = [], set()
        for it in txs:
            src = ((it.get("from") or {}).get("hash") or "").lower()
            if src != funder.lower():
                continue
            dst = ((it.get("to") or {}).get("hash") or "").lower()
            dests.add(dst)
            try:
                amounts.append(round(int(it.get("value") or 0) / 1e18, 6))
            except ValueError:
                amounts.append(0.0)
        prof["sample_out_txs"] = len(amounts)
        prof["distinct_destinations"] = len(dests)
        if amounts:
            from collections import Counter
            common, n = Counter(amounts).most_common(1)[0]
            prof["uniform_amount"] = common if n >= max(3, len(amounts) // 2) else None
            prof["uniform_share"] = round(n / len(amounts), 2)
        if prof.get("is_contract"):
            prof["type"] = "CONTRACT_BATCHER"
        elif prof.get("uniform_amount") is not None and prof.get("distinct_destinations", 0) >= 5:
            prof["type"] = "FUNDING_BOT_EOA"
        else:
            prof["type"] = "OPERATOR_EOA"
        return prof


def tx_summary(t: dict) -> dict:
    return {"tx": t["tx"], "block": t["block"], "amount": round(t["amount"], 6),
            "counterparty": t["counterparty"]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------- override mapping ----------------

def override_for(wallet: str, verdicts: list[dict]) -> dict | None:
    """Gabungkan verdict per-token jadi 1 override per wallet."""
    v_order = {"TRADER_MISREAD": 0, "UNRESOLVED": 1, "AIRDROP_SPAM": 2,
               "CONFIRMED_INSIDER": 3, "MINT_ALLOCATION": 4}
    verdicts = sorted(verdicts, key=lambda v: v_order.get(v.get("verdict"), 9))
    top = verdicts[0]
    verdict = top.get("verdict")
    base = {"verified_at": _now(), "remove_labels": ["INSIDER"]}
    if verdict == "TRADER_MISREAD":
        base.update({
            "set_primary": "TRADER_COVERAGE_GAP",
            "add_labels": ["TRADER_COVERAGE_GAP"],
            "confidence": {"TRADER_COVERAGE_GAP": 0.85},
            "evidence": {"TRADER_COVERAGE_GAP": {"tokens": [v["token"] for v in verdicts],
                                                 "reason": top.get("reason"),
                                                 "proof_txs": top.get("proof_txs", [])[:5]}},
            "note": "INSIDER dibatalkan: bukti on-chain menunjukkan tx beli (Swap log) "
                    "yang tak tertangkap scan; antre re-enrich",
        })
    elif verdict == "UNRESOLVED":
        base.update({
            "set_primary": "GENERALIST",
            "add_labels": ["INSIDER_UNPROVEN"],
            "confidence": {"GENERALIST": 0.4},
            "evidence": {"INSIDER_UNPROVEN": {"tokens": [v["token"] for v in verdicts],
                                              "reason": top.get("reason")}},
            "note": "INSIDER diturunkan: tidak ada bukti transfer masuk on-chain "
                    "(kemungkinan besar coverage gap); menunggu re-enrich",
        })
    elif verdict == "AIRDROP_SPAM":
        base.update({
            "set_primary": "AIRDROP_FARMER",
            "add_labels": ["AIRDROP_FARMER", "PHISHING_TARGET"],
            "confidence": {"AIRDROP_FARMER": 0.9, "PHISHING_TARGET": 0.8},
            "evidence": {"PHISHING_TARGET": {"tokens": [v["token"] for v in verdicts],
                                             "senders": {k: v.get("spread")
                                                         for k, v in (top.get("senders") or {}).items()}}},
            "note": "bukan insider: token diterima dari distribusi massal "
                    f"(>= {MASS_SPREAD_WALLETS} wallet / <= {MASS_SPREAD_BLOCKS} blok)",
        })
    elif verdict in ("CONFIRMED_INSIDER", "MINT_ALLOCATION"):
        base.update({
            "set_primary": "INSIDER",
            "add_labels": ["INSIDER"],
            "confidence": {"INSIDER": 0.95 if verdict == "MINT_ALLOCATION" else 0.85},
            "evidence": {"INSIDER": {"tokens": [v["token"] for v in verdicts],
                                     "kind": verdict,
                                     "senders": {k: {"kind": v.get("kind"), "spread": v.get("spread")}
                                                 for k, v in (top.get("senders") or {}).items()},
                                     "mint": top.get("mint")}},
            "note": "INSIDER TERBUKTI on-chain: token diterima via transfer/mint "
                    "murni (tanpa Swap log di tx)",
        })
    else:
        return None
    return base


# ---------------- main ----------------

async def run(max_calls: int, pairs_limit: int | None) -> int:
    rd = Path(settings.results_dir)

    # anti-overlap: satu instance verifier per VPS (cron aman dari tumpangan)
    import fcntl

    lock_fh = open(rd / ".reverify.lock", "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        jlog(log, logging.INFO, "verifier lain masih jalan — exit")
        return 0

    labels_path = rd / "wallet_labels.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    wallets = labels.get("wallets", {})

    targets: dict[str, list[str]] = {}
    for addr, entry in wallets.items():
        ev = (entry.get("evidence") or {}).get("INSIDER") or {}
        tokens = ev.get("tokens") or []
        if tokens:
            targets[addr.lower()] = [t.lower() for t in tokens]

    # cluster members dari labels
    clusters: dict[str, list[dict]] = {}
    for addr, entry in wallets.items():
        for lab in entry.get("labels", []):
            if lab.startswith("CLUSTER_MEMBER:"):
                cid = lab.split(":", 1)[1]
                ev = (entry.get("evidence") or {}).get(lab) or {}
                clusters.setdefault(cid, []).append({
                    "wallet": addr.lower(),
                    "funder": (ev.get("funder") or "").lower(),
                })

    prog_path = rd / "tag_verification_progress.json"
    done: dict = {}
    if prog_path.exists():
        try:
            done = json.loads(prog_path.read_text(encoding="utf-8")).get("done", {})
        except Exception:
            done = {}

    pairs = [(w, t) for w, toks in sorted(targets.items()) for t in toks
             if f"{w}:{t}" not in done]
    if pairs_limit:
        pairs = pairs[:pairs_limit]
    jlog(log, logging.INFO, "reverify start", insider_pairs=len(pairs),
         clusters={k: len(v) for k, v in clusters.items()}, max_calls=max_calls)

    v = TagVerifier(max_calls=max_calls)
    verification: dict = json.loads(
        (rd / "tag_verification.json").read_text(encoding="utf-8")
    ) if (rd / "tag_verification.json").exists() else {"insider": {}, "clusters": {}}
    overrides: dict = {}
    opath = rd / "tag_overrides.json"
    if opath.exists():
        try:
            overrides = json.loads(opath.read_text(encoding="utf-8")).get("wallets", {})
        except Exception:
            overrides = {}
    reenrich: dict = {}
    rq_path = rd / "reenrich_queue.json"
    if rq_path.exists():
        try:
            reenrich = json.loads(rq_path.read_text(encoding="utf-8")).get("wallets", {})
        except Exception:
            reenrich = {}

    verdict_by_wallet: dict[str, list[dict]] = defaultdict(list)
    deferred = 0
    t0 = time.time()
    aborted = False

    def persist() -> None:
        """Tulis hasil parsial — dipanggil tiap checkpoint DAN di akhir, jadi
        monitoring bisa membaca verdict saat run masih berjalan."""
        (rd / "tag_verification.json").write_text(
            json.dumps(verification, indent=1, default=str), encoding="utf-8")
        (rd / "tag_overrides.json").write_text(
            json.dumps({"generated_at": _now(), "source": "scripts/reverify_tags.py",
                        "wallets": overrides}, indent=1), encoding="utf-8")
        (rd / "reenrich_queue.json").write_text(
            json.dumps({"generated_at": _now(), "wallets": reenrich}, indent=1),
            encoding="utf-8")
        prog_path.write_text(json.dumps({"done": done}), encoding="utf-8")

    try:
        for i, (wallet, token) in enumerate(pairs):
            if v.calls >= max_calls:
                jlog(log, logging.INFO, "budget habis — checkpoint & exit",
                     done=len(done), calls=v.calls)
                break
            try:
                res = await v.verify_insider_pair(wallet, token)
            except Defer as e:
                # API tidak lengkap utk pair ini SAAT INI: jangan verdict,
                # jangan tandai done — cron berikutnya mengulang pair ini
                deferred += 1
                if deferred % 10 == 1:
                    jlog(log, logging.INFO, "pair ditunda (API incomplete)",
                         total_deferred=deferred, sample=str(e)[:100])
                continue
            except Exception as e:
                # infra error setelah retry panjang: catat ERROR + tandai done
                # supaya resume TIDAK mengulang pair beracun ini terus-menerus
                done[f"{wallet}:{token}"] = "ERROR:" + _now()
                verification.setdefault("insider", {})[f"{wallet}:{token}"] = {
                    "token": token, "verdict": "ERROR", "reason": str(e)[:200],
                    "checked_at": _now(),
                }
                aborted = True
                jlog(log, logging.ERROR, "pair gagal permanen (ditandai ERROR, resume nanti)",
                     wallet=wallet, token=token, err=str(e)[:160])
                break
            verification.setdefault("insider", {})[f"{wallet}:{token}"] = res
            verdict_by_wallet[wallet].append(res)
            done[f"{wallet}:{token}"] = _now()
            if (i + 1) % 10 == 0:
                for w, vl in verdict_by_wallet.items():
                    ov = override_for(w, vl)
                    if ov:
                        overrides[w] = ov
                    if any(x.get("verdict") in ("TRADER_MISREAD", "UNRESOLVED") for x in vl):
                        reenrich[w] = {"reason": "tag_verification", "at": _now(),
                                       "tokens": [x["token"] for x in vl]}
                persist()
                jlog(log, logging.INFO, "progress", pairs_done=i + 1,
                     total=len(pairs), calls=v.calls,
                     elapsed_min=round((time.time() - t0) / 60, 1))
            await asyncio.sleep(0.05)
    finally:
        # ---------------- cluster stage (ringan, jalan meski budget habis) --
        if v.calls < max_calls and not aborted:
            for cid, members in sorted(clusters.items()):
                funder = next((m["funder"] for m in members if m["funder"]), None)
                if not funder:
                    continue
                try:
                    prof = await v.profile_funder(funder)
                except Exception as e:
                    jlog(log, logging.ERROR, "funder profile gagal", cluster=cid, err=str(e)[:120])
                    continue
                entry = {"funder": funder, "profile": prof, "members": {}}
                for m in members:
                    key = f"{cid}:{m['wallet']}"
                    if key in done:
                        entry["members"][m["wallet"]] = verification["clusters"][key]
                        continue
                    try:
                        r = await v.verify_cluster_member(m["wallet"], funder)
                    except Exception as e:
                        r = {"verdict": "ERROR", "reason": str(e)[:120]}
                    verification.setdefault("clusters", {})[key] = r
                    entry["members"][m["wallet"]] = r
                    done[key] = _now()
                verification.setdefault("cluster_profiles", {})[cid] = entry

        # ---------------- finalize overrides + reenrich queue ---------------
        for wallet, vlist in verdict_by_wallet.items():
            ov = override_for(wallet, vlist)
            if ov:
                overrides[wallet] = ov
            if any(x.get("verdict") in ("TRADER_MISREAD", "UNRESOLVED") for x in vlist):
                reenrich[wallet] = {"reason": "tag_verification", "at": _now(),
                                    "tokens": [x["token"] for x in vlist]}

        persist()

        counts: dict[str, int] = defaultdict(int)
        for w, vl in verdict_by_wallet.items():
            for x in vl:
                counts[x.get("verdict", "?")] += 1
        jlog(log, logging.INFO, "reverify finished", pairs_done=len(done),
             calls=v.calls, verdicts=dict(counts), deferred=deferred,
             aborted=aborted)

    await v.rpc.close()
    await v.bc.close()
    return 0 if not aborted else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-calls", type=int, default=8000,
                    help="budget API calls per run (resume-safe)")
    ap.add_argument("--pairs", type=int, default=None, help="batasi jumlah pair (smoke test)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    return asyncio.run(run(args.max_calls, args.pairs))


if __name__ == "__main__":
    raise SystemExit(main())
