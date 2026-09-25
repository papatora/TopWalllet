import sqlite3

c = sqlite3.connect("file:/opt/topwallet/data/topwallet.db?mode=ro", uri=True)
print("== token terbaru (first_seen):")
for r in c.execute(
        "select address, symbol, first_seen from tokens order by first_seen desc limit 5"):
    n = c.execute("select count(*) from swap_events where token_address=?",
                  (r[0],)).fetchone()[0]
    iw = c.execute(
        "select count(distinct wallet_address) from wallet_token_interest "
        "where token_address=?", (r[0],)).fetchone()[0]
    print(" ", r[0][:14], r[1], str(r[2]), "| swaps:", n, "| interest wallets:", iw)

print()
print("== swap per hari (>=10 Sep):")
for r in c.execute("select date(ts), count(*) from swap_events where ts >= '2026-09-10' "
                   "group by 1 order by 1"):
    print(" ", r[0], r[1])

print()
print("== trader token terbaru — contoh wallet + interest:")
row = c.execute(
    "select i.wallet_address, i.token_address, t.first_seen from wallet_token_interest i "
    "join tokens t on t.address = i.token_address "
    "order by t.first_seen desc limit 3").fetchall()
for w, tk, fs in row:
    n = c.execute("select count(*), max(ts) from swap_events where wallet_address=?",
                  (w,)).fetchone()
    print(" ", w[:14], "token", tk[:10], "first_seen", fs,
          "| swap wallet:", n[0], "| max ts:", n[1])
