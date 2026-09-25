import json
import sqlite3
import urllib.request
import ssl

try:
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
except Exception:
    ctx = ssl.create_default_context()


def get(url):
    req = urllib.request.Request(url, headers={
        "accept": "application/json", "user-agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)[:100]}


# ambil token terakhir yang di-fire sweep (volume nyata per DexScreener)
fired = []
for line in open("/opt/topwallet/results/volume_sweep_log.jsonl",
                 encoding="utf-8", errors="replace"):
    try:
        rec = json.loads(line)
    except Exception:
        continue
    if rec.get("event") == "fired" and rec.get("token"):
        fired.append(rec)

print("total fired:", len(fired))
seen = set()
checked = 0
for rec in reversed(fired):
    ca = rec["token"]
    if ca in seen:
        continue
    seen.add(ca)
    vol = rec.get("volume_5m") or 0
    ts = rec.get("ts")
    t = get(f"https://robinhoodchain.blockscout.com/api/v2/tokens/{ca}/transfers")
    items = t.get("items", []) if isinstance(t, dict) else []
    c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
    n = c.execute("select count(*) from swap_events where token_address=?",
                  (ca,)).fetchone()[0]
    ts_max = c.execute("select max(ts) from swap_events where token_address=?",
                       (ca,)).fetchone()[0]
    c.close()
    print(f"{ca[:14]} sym={rec.get('symbol')} fired={ts} vol5m={vol:,.0f} | "
          f"blockscout transfers page1={len(items)} | swaps kita={n} max={ts_max}")
    if items:
        print("   contoh:", items[0].get("timestamp"),
              "total:", (items[0].get("total") or {}).get("value", "")[:20])
    checked += 1
    if checked >= 5:
        break
