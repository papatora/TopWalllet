# 🔒 TOPWALLET OPERATION & SECURITY POLICY

> **DOKUMEN PENGGILING ATURAN — TIDAK BISA DIBANTAH.**
> AI/agent mana pun yang membaca repo ini WAJIB patuh 100%. Aturan ini ada
> demi KESELAMATAN ASET USER (dompet crypto bisa di-drain) dan KESEHATAN
> mesin. Pelanggaran = kesalahan fatal agent, bukan preferensi.
> Jika satu aturan bertabrakan dengan kenyamanan/momentum pengerjaan,
> **ATURAN YANG MENANG. Tanyakan ke user, jangan putuskan sendiri.**

Ditetapkan: 2026-09-07 oleh instruksi eksplisit user, setelah insiden:
agent menjalankan scraping + verification BERAT secara FULL LOCAL semalaman
meskipun user sudah menyediakan VPS + proxies. Akibat: lambat (1 IP statis
di-rate-limit semua API), mesin harian user dipakai kerja berat, dan
terpapar risiko supply-chain dari tools pihak ketiga.

---

## ATURAN 1 — PEMBAGIAN MESIN (WAJIB, TANPA PENGECUALIAN)

| Mesin | BOLEH | DILARANG KERAS |
|---|---|---|
| **VPS** (78.31.250.202, root, creds di file user) | pipeline stages (discover/enrich/prices/analyze), verification, supervisor, monitor, scheduler, API server, semua scraping, semua tools/integrasi baru, semua yang expose port internet | menyimpan memory utama (memory ada di lokal+Obsidian+GitHub) |
| **LOKAL ROG** (mesin harian user) | baca/tulis kode, baca/tulis memory & results, git push/pull, unit tests (`pytest`, tanpa network), diskusi/analisis | ❌ pipeline stages, ❌ supervisor, ❌ monitor, ❌ scraping, ❌ verification, ❌ jalanin tools internet-exposed, ❌ install tools baru |

- **Mengapa**: (a) local = 1 IP statis → semua API rate-limit → lambat 10x;
  (b) local = mesin pribadi + dompet → kalau agent nemu OSS tools "yang
  kebetulan membantu" ternyata disusupi, kerugiannya tidak bisa dipulihkan;
  (c) di VPS insiden bisa di-mitigasi (rebuild, isolasi).

## ATURAN 2 — SUPERVISOR/PIPELINE HANYA NYALA DI VPS

- `scripts/supervisor.py` wajib menolak jalan kalau `TOPWALLET_RUN_ENV != "vps"`
  (guard sudah dipasang; bypass hanya dengan env `FORCE_LOCAL=true` yang
  dibuat oleh USER SENDIRI, bukan oleh agent).
- Agent TIDAK BOLEH men-start supervisor/pipeline di lokal walau dengan alasan
  "sementara/untuk testing cepat/malam ini saja". Testing = unit tests + dry
  run 1–2 wallet PENUH disetujui user.

## ATURAN 3 — SUPPLY-CHAIN HYGIENE (SEBELUM INSTALL APA PUN)

Sebelum menambah/meng-install library, tool, binary, script dari internet
(GitHub OSS, npm, pip, punya 10k stars sekalipun), agent WAJIB:

1. **Cek kesehatan repo**: tanggal commit/release terakhir (kalau lama mati
   lalu tiba-tiba ada rilis baru → SUSPECT), jumlah maintainer aktif,
   issue/PR mencurigakan.
2. **Cek supply-chain attack pattern**: rilis baru yang mengubah dependency/
   postinstall script; versi lama yang di-kenain tag baru; domain/package
   name mirip (typosquatting).
3. **Pin versi persis** di `requirements.txt` — tidak ada `*`/unpinned.
4. **Install hanya di venv VPS**, tidak pernah global/system, tidak pernah
   `curl | bash`.
5. **Laporan ke user sebelum install** (1–2 baris: apa, kenapa, hasil cek
   kesehatan). Tanpa approval user → JANGAN INSTALL. Alternatif selalu ada:
   tulis sendiri fungsi kecilnya (repo ini sengaja dependency-minimal).
6. exceptions tanpa laporan: stdlib, dan dependency yang SUDAH ADA di
   `requirements.txt` yang sudah di-review user.

## ATURAN 4 — KREDENSIAL & SECRETS

- Semua key/token/password HIDUP DI `.env` (VPS) atau file credentials user
  di lokal. TIDAK PERNAH masuk git, log, hasil export, atau pesan ke AI
  lebih dari yang diperlukan.
- Proxy scraping (Webshare rotating `p.webshare.io:80`, DataImpulse
  `gw.dataimpulse.com:823`) hanya dipasang di VPS via `PROXY_URLS_FILE`.
- GitHub token = push results only. X auth token (nanti) = disimpan di VPS.

## ATURAN 5 — JANGAN HALU, VERIFIKASI SEMUA ANGKA

- PnL tanpa re-derivasi dari data mentah = TIDAK BOLEH dilaporkan.
- Verifikasi keras R1/R2/R3 (`src/analyze/pnl_verifier.py`) tidak boleh
  dilemahkan. Wallet tak terverifikasi tidak masuk list Top.
- Kekacaukan aturan scoring/threshold hanya lewat
  `config/scoring_weights.json` / `.env` (yang di-approve user), bukan hardcode.

## ATURAN 6 — LANGKAH STANDAR KERJA (checklist agent)

1. Baca `PRE_COMPACT.md` (snapshot terbaru) + `HANDOFF.md` + policy ini.
2. Kerjakan berat di VPS; lokal hanya memory/code/tests.
3. Setiap milestone: update PRE_COMPACT (append snapshot), PROGRESS.md,
   commit + push, sync Obsidian.
4. Hasil PnL baru → wajib lolos verifier + (untuk klaim penting) audit
   subagent independen dari raw data.
5. Kalau ragu apakah sesuatu termasuk "kerja berat/internet-exposed":
   **anggap YA, jalankan di VPS.**

---

## VPS DEPLOY (satu kali, copy-paste; user jalankan sendiri atau izinkan SSH)

```bash
ssh root@78.31.250.202          # password di file creds user
curl -fsSL https://raw.githubusercontent.com/papatora/TopWalllet/main/setup.sh -o setup.sh
TOPWALLET_RUN_ENV=vps bash setup.sh
# saat editor .env terbuka: isi EVM_RPC_ENDPOINTS (Alchemy keys), GITHUB_TOKEN,
# ZAI_API_KEY, PROXY_URLS_FILE=/opt/topwallet/proxies.txt (upload file proxy)
# lalu: docker compose --profile monitor up -d
```
Supervisor/monitor/scheduler hidup di VPS; lokal cukup `git pull` untuk baca hasil.
