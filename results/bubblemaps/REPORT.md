# Bubblemaps Re-Verify — 12 Token Robinhood Chain (Goal #5)

Tanggal: 2026-09-24 · Sesi login user via Brave CDP · sumber:
`api.bubblemaps.io/relationships/subgraph` + `token-top-holders` + panel
Address List (grup resmi Bubblemaps). Data mentah: `results/bubblemaps/<ca>.json`.

## Kesimpulan utama

1. **Wallet INSIDER kita = distributor historis yang sudah exit.** Dari 12
   token, hampir nol wallet INSIDER kita yang masih ada di top-250 holder
   Bubblemaps (total temuan: 1). Label INSIDER tetap valid sebagai SEJARAH
   (pola pendanaan fleet), tapi bukan sinyal "mereka masih memegang".

2. **5 dari 12 token = hantu supply ~90% satu kantong** (0x98650ab3 90,2%,
   0x9eb5d70f 91,5%, 0xe660cda9 91,8%, 0xec625498 91,7%, 0xeba7bf6c 87,0%;
   top10 = 99-100%). Pola deployer yang tak pernah distribusi → untuk
   copytrade: HINDARI (valuasi kertas, tak ada pasar).

3. **HOOD (0xdaa8f3f5) = insider-exited, distribusi sehat**: top1 cuma
   14,9%, top10 24,0% — tapi likuiditas $1,14K vs FDV $65,35M (rasio
   ~57.000×) → harga tidak bisa dipercaya; FDV fiktif.

4. **Konsentrasi + kontrak aktif (RISK):** 0x39dbed3a top1 31,6% + 27
   kontrak di top250 + panel cluster 23 addr (5,42%) → fleet masih pegang.

5. **0x77b0aa38 kosong total di Bubblemaps** (0 relasi, 0 holder) padahal
   66 wallet INSIDER kita — token mati/sepi, konsisten dgn insider exit.

## Tabel

| token | INS# kita | relasi | top1% | top10% | kontrak | panel cluster (member, %) |
|---|---|---|---|---|---|---|
| 0x12d5ee79 | 0 | 7040 | 7,7 | 27,9 | 7 | C1 15@2,72 · C2 2@2,51 · C3 3@1,32 |
| 0x18e67423 | 3 | 8720 | 4,4 | 17,8 | 9 | C1 2@2,51 · C2 13@2,33 |
| 0x39dbed3a | 2 | 6850 | 31,6 | 48,1 | 27 | C1 23@5,42 · C2 6@1,45 |
| 0x56910d44 | 4 | 5008 | 2,6 | 15,4 | 10 | C1 3@2,03 · C2 4@1,10 |
| 0x77b0aa38 | 66 | 0 | — | — | 0 | (token kosong di bubblemaps) |
| 0x98650ab3 | 15 | 347 | 90,2 | 99,9 | 6 | — |
| 0x9eb5d70f | 38 | 420 | 91,5 | 100,0 | 5 | — |
| 0xdaa8f3f5 | 158 | 273 | 14,9 | 24,0 | 1 | C1 6@8,67 |
| 0xe660cda9 | 17 | 255 | 91,8 | 100,0 | 2 | — |
| 0xe8ffd7e2 | 5 | 7381 | 10,0 | 27,2 | 15 | C1 12@4,34 · C2 14@2,27 |
| 0xeba7bf6c | 20 | 2851 | 87,0 | 99,0 | 6 | — |
| 0xec625498 | 0 | 287 | 91,7 | 100,0 | 2 | — |

## Implikasi untuk audit cluster (keputusan, menunggu ronde audit)

- Jangan pakai "INSIDER masih pegang" sebagai premis copytrade — data
  membantah. Gunakan sebagai sinyal konteks token (exit = token ditinggal
  operator).
- Token ~90% single-holder: kandidat label tambahan `GHOST_SUPPLY` pada
  level TOKEN (bukan wallet) supaya rating paste-CA (Goal #4) otomatis
  menghukum.
- Metode capture ini reusable: `scripts/bubblemaps_capture.py --tokens
  <queue>` — menempuh UI resmi (sesi login), tanpa memalsukan auth.

## Cara pakai ulang

```
python scripts/bubblemaps_capture.py --tokens results/bubblemaps_token_queue.json --max 12
# hasil: results/bubblemaps/<ca>.json (subgraph + top-holders + panel)
```
