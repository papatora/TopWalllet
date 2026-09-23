"""Apply WF-1 verification verdicts to the local database + labels.

Deterministic resolver per named filter (dari results/verification_verdicts.json).
Output: tag_overrides.json additions + results/wallet_labels.json re-applied +
before/after label counts. Rebuild dataset setelahnya (POST /api/rebuild).
"""
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
NOW = datetime.now(timezone.utc).isoformat()

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

# ---- basis data in-memory ----
labels: dict[str, dict] = defaultdict(dict)
for r in con.execute("SELECT wallet_address, label, confidence FROM wallet_labels"):
    labels[r["wallet_address"].lower()][r["label"]] = round(r["confidence"] or 0, 2)

stats: dict[str, sqlite3.Row] = {}
for r in con.execute("""SELECT wallet_address,
        COUNT(*) n, SUM(side='BUY') buys, SUM(side='SELL') sells,
        COUNT(DISTINCT token_address) toks,
        SUM(CASE WHEN side='BUY' THEN usd_value ELSE -usd_value END) net,
        MIN(block_num) b0, MAX(block_num) b1
        FROM swap_events GROUP BY wallet_address"""):
    stats[r["wallet_address"].lower()] = r

sell_only_tokens: dict[str, int] = defaultdict(int)
buy_has: set[str] = set()
for r in con.execute("SELECT wallet_address, token_address, side FROM swap_events"):
    a = r["wallet_address"].lower()
    if r["side"] == "SELL":
        sell_only_tokens[a] += 1
    else:
        buy_has.add(a)

snipe_count: dict[str, int] = {}
for r in con.execute("SELECT wallet_address, evidence FROM wallet_labels WHERE label='SNIPER'"):
    try:
        snipe_count[r["wallet_address"].lower()] = len(json.loads(r["evidence"] or "{}").get("snipes") or [])
    except ValueError:
        pass

toks_of: dict[str, set] = defaultdict(set)
for a, s in stats.items():
    pass  # toks sudah di stats

def L(a):
    return labels.get(a, {})

def insiders():
    return {a for a, lab in labels.items() if "INSIDER" in lab}

def snipers():
    return {a for a, lab in labels.items() if "SNIPER" in lab}

def bundlers():
    return {a for a, lab in labels.items() if "BUNDLER_SUSPECT" in lab}

def airdrops():
    return {a for a, lab in labels.items() if "AIRDROP_FARMER" in lab}

new_overrides: dict[str, dict] = {}

def ov(addr: str, action: str, set_primary=None, remove=None, add=None,
       conf_label=None, conf_val=None, reason=""):
    a = addr.lower()
    entry = new_overrides.setdefault(a, {
        "set_primary": None, "remove_labels": [], "add_labels": [],
        "confidence": {}, "evidence": {}, "note": "",
    })
    if set_primary:
        entry["set_primary"] = set_primary
    for lab in (remove or []):
        if lab not in entry["remove_labels"]:
            entry["remove_labels"].append(lab)
    for lab in (add or []):
        if lab not in entry["add_labels"]:
            entry["add_labels"].append(lab)
    if conf_label and conf_val is not None:
        entry["confidence"][conf_label] = conf_val
    if reason:
        entry["note"] = reason[:200]
    entry["verified_at"] = NOW


# ===== INSIDER =====
ins = insiders()
stale = {a for a in ins if sell_only_tokens.get(a, 0) == 0}
with_buy = {a for a in ins if a in buy_has}
core = ins - stale - with_buy
for a in stale:
    ov(a, "relabel", set_primary="GENERALIST", remove=["INSIDER"],
       reason=f"STALE: kini 0 token sell-only di swap_events lokal (ada BUY) — basis insider hilang")
for a in with_buy - stale:
    ov(a, "downgrade", conf_label="INSIDER", conf_val=0.5,
       reason=f"DOWNGRADE: wallet punya BUY swap (bukan murni sell-only) — conf turun 0.5")
# core keep — no entry

# ===== SNIPER =====
sn = snipers()
same_tx = sn & bundlers()
single = {a for a in sn if snipe_count.get(a, 0) <= 1} - same_tx
multi = sn - same_tx - single
for a in same_tx:
    ov(a, "downgrade", conf_label="SNIPER", conf_val=0.5,
       reason="DOWNGRADE: SNIPER+BUNDLER same-tx — snipe sekalian bundling, bukan spesialis")
for a in single:
    ov(a, "downgrade", conf_label="SNIPER", conf_val=0.5,
       reason="DOWNGRADE: single snipe (snipe_count<=1) — belum terbukti spesialis")
for a in multi:
    ov(a, "upgrade", conf_label="SNIPER", conf_val=0.9,
       reason=f"UPGRADE: repeat multi-token sniper ({snipe_count.get(a,0)} snipes)")

# ===== MEV_BOT downgrades (verdict Ronde K: 2 wallet RT<30) =====
for a in ("0x505d2e7a715c9af1d690204f43d75eaea4efaf10",
          "0x1cc65d09d81e4656e72444217e201064226d2c3c"):
    ov(a, "downgrade", conf_label="MEV_BOT", conf_val=0.5,
       reason="DOWNGRADE: round trips < 30 (gagal ambang individu classifier)")

# ===== CLUSTER_MEMBER f70d (funder = bridge solver) =====
f70d = [r[0].lower() for r in con.execute(
    "SELECT wallet_address FROM wallet_labels WHERE label='CLUSTER_MEMBER:cluster_f70d'")]
for a in f70d:
    ov(a, "downgrade", remove=[], add=["BRIDGE_FUNDED"],
       conf_label="CLUSTER_MEMBER:cluster_f70d", conf_val=0.4,
       reason="funder 0xf70da978 = Relay.link Bridge Solver (Arkham BRIDGE) — didanai bridge, bukan operator insider")

# ===== AIRDROP_FARMER =====
af = airdrops()
ov_tcg = {}   # addr -> TRADER_MISREAD overrides yg sudah ada
overrides_doc = json.loads((REPO / "results" / "tag_overrides.json").read_text(encoding="utf-8"))
for a, o in overrides_doc["wallets"].items():
    note = (o.get("note") or "") + json.dumps(o.get("evidence") or {})
    if "TRADER_MISREAD" in note or "TRADER_MISREAD" in json.dumps(o.get("evidence") or {}):
        ov_tcg[a] = True
af_tcg = af & set(ov_tcg)
af_insider_ov = {a for a, o in overrides_doc["wallets"].items()
                 if o.get("set_primary") == "INSIDER" and a in af}
af_buys_contra = {a for a in af if a in buy_has and a not in af_tcg and a not in af_insider_ov}
# CATATAN: rule "armada" (BUY/SELL count seimbang) DIHAPUS — farmer beli kecil
# utk kualifikasi lalu jual, count-nya memang seimbang → salah tangkap 2.268
# wallet (kejadian nyata sebelum revert).
af_unverified_zero = af - af_tcg - af_insider_ov - af_buys_contra

for a in af_tcg:
    ov(a, "relabel", set_primary="TRADER_COVERAGE_GAP",
       remove=["AIRDROP_FARMER", "PHISHING_TARGET"], add=["TRADER_COVERAGE_GAP"],
       conf_label="TRADER_COVERAGE_GAP", conf_val=0.9,
       reason="reverify TRADER_MISREAD on-chain: wallet benar-benar trading (bukan farmer)")
for a in af_insider_ov:
    ov(a, "relabel", set_primary="INSIDER", remove=["AIRDROP_FARMER"],
       conf_label="INSIDER", conf_val=0.85,
       reason="reverify CONFIRMED_INSIDER on-chain: transfer murni non-swap")
for a in af_buys_contra:
    ov(a, "relabel", set_primary="GENERALIST", remove=["AIRDROP_FARMER", "PHISHING_TARGET"],
       reason="KONTRADIKSI: ada BUY swap — bukan farmer murni")
for a in af_unverified_zero:
    ov(a, "downgrade", conf_label="AIRDROP_FARMER", conf_val=0.5,
       reason="unverified zero-buy: conf diturunkan 0.5 sampai re-verify")

# ===== DEV disputed (butuh re-derive first-buyer per token — tandai review) =====
# di-skip otomatis: butuh re-derive token-level; dicatat sbg pending di laporan.

# ===== GENERALIST hidden MEV bots (spesifik dr verdict) =====
gen_mev = ["0xc87b51c71707cfdd08cd374a596a6946cb1d6a66",
           "0x2a4d34cd09a36f59ae3bedc0880cd5da929321d7",
           "0x53e68553ca08f512423628d64c01b0a14dfcda99",
           "0xc207df8dc9ee5113c6374c70c2a29bb87e94cfdf",
           "0xd01d7d0f1d7db0aa59fd346762aa4a9c10da2257",
           "0x1c66ae54d5e4ee86980c90edbc55ddb29161b4ea",
           "0x5c87ecc36bb97380469be09ef95dc4daf50165ec",
           "0x1c35438a169cc8480e955e0d24ad6964280b8cf2",
           "0xac032e1a03b4b5f32cc10de7addfcd0cf1342440",
           "0xc0b3535e207830706656016b62806d8fe9e6ae6e",
           "0xf4bbb2b6cc81a3a7339cdbfa085aa59d65525b00",
           "0xb5b93f7647118dbc8ba73f8b67e1ed6e6acad4be",
           "0xcf392f62151fe078a5c26c6fd7e6bc5f15d9735a"]
for a in gen_mev:
    ov(a, "relabel", set_primary="MEV_BOT", add=["MEV_BOT"],
       conf_label="MEV_BOT", conf_val=0.85,
       reason="lolos aturan MEV_BOT repo persis (_mev_signal: pairing >=30 RT, median hold <=10 min)")

WRITE = "--write" in sys.argv

# ===== tulis overrides baru ke tag_overrides.json =====
op = REPO / "results" / "tag_overrides.json"
odoc = json.loads(op.read_text(encoding="utf-8"))
ow = odoc.setdefault("wallets", {})
fresh = {a: e for a, e in new_overrides.items() if a not in ow}
for a, e in fresh.items():
    cur = ow.get(a) or {}
    cur.update({k: v for k, v in e.items() if v not in (None, [], {})})
    cur["verified_at"] = NOW
    ow[a] = cur
if WRITE:
    odoc["generated_at"] = NOW
    op.write_text(json.dumps(odoc, indent=1), encoding="utf-8")
print(f"tag_overrides: +{len(fresh)} baru (total {len(ow)}) {'[WRITTEN]' if WRITE else '[DRY-RUN]'}")

# ===== apply SEMUA overrides ke wallet_labels.json =====
if not WRITE:
    print("[DRY-RUN] wallet_labels.json tidak diubah")
    import collections as _c
    acts = _c.Counter(e["note"].split(":")[0][:40] or "?" for e in new_overrides.values())
    for a, n in acts.most_common(10):
        print(f"  {n:5d}  {a}")
    print(f"new_overrides total: {len(new_overrides)}")
    sys.exit(0)

import sys
sys.path.insert(0, str(REPO))
from src.analyze.tag_overrides import apply_overrides

lp = REPO / "results" / "wallet_labels.json"
doc = json.loads(lp.read_text(encoding="utf-8"))
before = Counter()
for v in doc["wallets"].values():
    before[v["primary_type"]] += 1
doc, changed = apply_overrides(doc, ow)
after = Counter(v["primary_type"] for v in doc["wallets"].values())
doc["generated_at"] = NOW
lp.write_text(json.dumps(doc, indent=1), encoding="utf-8")

print(f"\nwallets berubah: {changed}")
print("=== BEFORE → AFTER (primary type) ===")
for t in sorted(set(before) | set(after), key=lambda x: -after.get(x, 0)):
    print(f"  {t:24s} {before.get(t,0):6d} → {after.get(t,0):6d}")
print(f"\nnew_overrides: {len(new_overrides)}")
json.dump({"applied": len(ow), "changed": changed,
           "at": NOW}, open(REPO / "results" / "verification_applied.json", "w"), indent=1)
