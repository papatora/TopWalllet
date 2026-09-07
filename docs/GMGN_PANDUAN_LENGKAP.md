# 📘 Panduan Lengkap GMGN.ai — Baca Token, Metrik, & Mekanik On-Chain

> Rangkuman lengkap dari sesi belajar 2026-09-07.
> Sumber: dokumentasi resmi GMGN + data on-chain + observasi langsung dari 2 token nyata.
>
> ⚠️ **Disclaimer:** Dokumen ini murni edukasi cara membaca UI dan data on-chain.
> Ini **bukan** nasihat keuangan dan **bukan** rekomendasi beli/jual token apapun.

---

## Daftar Isi

1. [Apa itu GMGN](#1-apa-itu-gmgn)
2. [Panel Security / Risk Grid — arti tiap label](#2-panel-security--risk-grid)
3. [Panel Dev Token — rapor si developer](#3-panel-dev-token--rapor-si-developer)
4. [Arti "Migrated" & Bonding Curve](#4-arti-migrated--bonding-curve)
5. [Callout / Connect X](#5-callout--connect-x)
6. [Phishing vs Bundler — bedanya di mana](#6-phishing-vs-bundler--bedanya-di-mana)
7. [Bundler secara on-chain (deep dive)](#7-bundler-secara-on-chain-deep-dive)
8. [Ekonomi Launchpad & Creator Fees](#8-ekonomi-launchpad--creator-fees)
9. [Studi Kasus: 2 Token Dibandingkan](#9-studi-kasus-2-token-dibandingkan)
10. [Checklist Baca Token 30 Detik](#10-checklist-baca-token-30-detik)
11. [Kesalahan Umum & Jebakan](#11-kesalahan-umum--jebakan)
12. [Glosarium Singkat](#12-glosarium-singkat)
13. [Sumber](#13-sumber)

---

## 1. Apa itu GMGN

GMGN.ai adalah **terminal trading memecoin multi-chain**. Fungsinya bukan cuma chart —
yang bikin dia dipakai adalah **layer analisis on-chain**-nya: dia baca data blockchain
mentah, lalu menerjemahkannya jadi label-label risiko yang gampang dibaca.

Fitur utama:
- **Trenches** — feed token baru dibuat / hampir bonding / baru migrate
- **Token page** — chart + panel keamanan + panel developer
- **Wallet Tracker / CopyTrade** — pantau & tiru wallet tertentu
- **Callout** — sinyal sosial dari wallet yang terverifikasi X-nya

**Prinsip paling penting:** semua angka di GMGN adalah **hasil interpretasi**, bukan
kebenaran mutlak. GMGN sendiri menulis di dokumentasinya bahwa data insider/sniper/
first-70 **tidak dijamin real-time dan hanya untuk referensi tambahan**.

---

## 2. Panel Security / Risk Grid

Ini panel kotak-kotak di kanan bawah halaman token.

### Tabel Lengkap

| Label | Definisi | Cara Baca |
|---|---|---|
| **Top 10** | % total supply yang dipegang 10 wallet terbesar | GMGN pakai patokan **< 30% = relatif aman**. Makin tinggi = makin gampang di-dump segelintir orang |
| **DEV** | % supply yang masih dipegang pembuat token | `0%` **tidak otomatis bagus** — bisa berarti sudah dijual habis, atau sudah dipindah ke wallet lain (cek kolom Insiders) |
| **Holders** | Jumlah wallet yang memegang token | Angka paling gampang dipalsukan. **Jangan pernah dibaca sendirian** — silang dengan Phishing & Bundler |
| **Snipers** | Wallet yang beli dalam **beberapa block pertama** setelah pool dibuka. Format `x / 70` = berapa sniper yang masih hold dari 70 pembeli pertama | Sniper yang masih nyangkut = tekanan jual yang menunggu keluar |
| **Insiders** | Wallet yang **tidak pernah beli** setelah trading buka tapi memegang token. Terdeteksi dari kesamaan waktu pembuatan wallet + sumber funding | Indikasi supply dev dipecah ke banyak wallet untuk dijual diam-diam. Makin besar % makin mencurigakan |
| **Phishing** | % supply yang berada di wallet ber-tag phishing/scammer | Lihat [bagian 6](#6-phishing-vs-bundler--bedanya-di-mana) |
| **Bundler** | % supply yang dibeli lewat **bundled transaction** (banyak wallet, satu block, atomic) | Lihat [bagian 6](#6-phishing-vs-bundler--bedanya-di-mana) & [bagian 7](#7-bundler-secara-on-chain-deep-dive) |
| **Dex Paid** | Dev sudah membayar **Enhanced Token Info** di DEX Screener (logo, banner, link sosial). Angkanya = nominal yang dibayar | Hanya membuktikan **ada yang mau keluar duit untuk visibility**. Bukan tanda legit — rugger juga bayar |
| **CTO** | *Community Take Over* — proyek sudah dilepas dev ke komunitas | Netral. Sering muncul setelah dev kabur/berhenti |
| **NoHoneypot** | Kontrak tidak mengunci penjualan | ✅ **Wajib**. Honeypot = bisa beli, tidak bisa jual |
| **Verified** | Source code kontrak dipublikasikan di Etherscan | ✅ Bagus, tapi "verified" ≠ "aman". Kode jahat juga bisa di-verify |
| **Renounced** | Ownership kontrak sudah dilepas | ⚠️ Docs GMGN sendiri memperingatkan: **ada proyek yang memalsukan status ini** |
| **Burnt** | % LP token yang dibakar (tidak bisa ditarik lagi) | `100%` = likuiditas tidak bisa di-rug lewat jalur ini. `95%` = sisa 5% masih bisa ditarik |
| **Mint Disable** | Creator tidak bisa mencetak token tambahan | ✅ Penting — kalau `No`, supply bisa digelembungkan sewaktu-waktu |
| **Blacklist** | Ada wallet yang di-blacklist dev dan tidak bisa jual | ❌ `Yes` = bahaya besar |
| **Buy / Sell Tax** | Pajak transaksi tambahan | Sell tax ekstrem (mis. 99%) = honeypot terselubung |
| **Rug Probability** | Estimasi kemungkinan rug, dihitung dari apakah para holder-nya sering beli token rug | Statistik perilaku, bukan ramalan |
| **Rug History** | Token rug yang pernah diluncurkan creator yang sama | Salah satu sinyal paling kuat. Kalau ada isinya → berhenti di sini |

### Yang paling sering disalahpahami

- **`DEV 0%` bukan berarti aman.** Supply-nya bisa pindah ke wallet lain — itulah kenapa metrik `Insiders` ada.
- **`Renounced ✓` bukan jaminan.** Dokumentasi resmi GMGN sendiri bilang ini bisa dipalsukan.
- **`Holders` besar bisa 100% artifisial.** Airdrop massal bikin angka ini meledak tanpa satupun pembeli asli.

---

## 3. Panel Dev Token — rapor si developer

Panel ini **bukan tentang token yang sedang kamu buka.** Ini rapor **orang yang bikin token itu.**
Buat memecoin, ini sering lebih informatif daripada metrik token itu sendiri.

| Field | Artinya | Kenapa penting |
|---|---|---|
| **DEV** `0x…` | Alamat wallet pembuat token | Titik awal pelacakan |
| **Funding** `0x…` ⧫0.064 · 43m | Wallet yang **memberi modal** ke dev, jumlahnya, dan kapan | 🔥 **Field paling underrated.** Kalau funding wallet yang sama pernah mendanai 10 rug, semuanya jelas |
| **Blacklist funding wallet** | Tombol untuk mem-blacklist sumber dana itu | Token dari sumber dana yang sama tidak akan muncul lagi di feed kamu |
| **Total Pairs** | Berapa token yang pernah dilaunch dev ini | Kalau puluhan dalam sehari → serial launcher / spam |
| **Migrated** | Berapa token dev ini yang **lulus bonding curve** ke DEX | Ukuran "kualitas" launch |
| **Non Migrated** | Berapa yang mati sebelum lulus | |
| **Lingkaran % Migrated** | Rasio `migrated / total pairs` | Rapor keberhasilan dev |
| **Dev's Best Token (ATH MC)** | Market cap tertinggi yang pernah dicapai token terbaiknya | Ceiling realistis dev ini |
| **Last Token Launched** | Kapan terakhir dia launch | Baru launch beberapa menit lalu + langsung launch lagi = pola spam |

### Cara membacanya

Dev dengan **1 token, 100% migrated, ATH $671K** ≠ dev dengan **50 token, 4% migrated**.
Yang pertama mungkin serius (atau baru mulai). Yang kedua jelas main volume.

Tapi hati-hati: **100% dari 1 token itu sampel kecil**. Statistik dengan n=1 tidak berarti apa-apa.

---

## 4. Arti "Migrated" & Bonding Curve

### Bonding curve itu apa

Launchpad (Pons, Pump.fun, dsb) tidak langsung bikin pool di DEX. Token dijual dulu lewat
**bonding curve** — algoritma di mana **harga naik otomatis seiring makin banyak yang beli**.
Tidak ada penjual lain, tidak ada order book. Kamu beli dari kurva, harga naik.

### Migrate itu apa

Kalau market cap mencapai ambang tertentu, **likuiditasnya otomatis dipindah ke DEX sungguhan**
(mis. Uniswap). Itulah **migrated** — istilah lain: *graduated* / *bonded*.

```
[ Token dibuat ]
       ↓
[ Bonding curve ] ← harga naik tiap ada pembeli
       ↓
   Capai target MC?
    ├── YA  → 🎓 MIGRATED → likuiditas pindah ke Uniswap/DEX
    └── TIDAK → 💀 mati di kurva (Non Migrated)
```

### Kenapa dua token bisa punya % Migrated berbeda

Karena itu **statistik dev-nya**, bukan statistik token-nya:

- Dev A: launch 1 token, lulus → **100%**
- Dev B: launch 2 token, 1 lulus 1 gagal → **50%**

Mayoritas token memecoin **tidak pernah migrate**. Jadi migrate itu sendiri sudah semacam filter.

---

## 5. Callout / Connect X

- **Callout** = fitur di mana wallet yang sudah **memverifikasi akun X/Twitter**-nya bisa
  "memanggil" (shill) sebuah token secara publik di GMGN.
- **Connect X** = menyambungkan akun X kamu ke GMGN.
- **"Hold at least $8.00 of $TOKEN · Now: $0.00"** = syarat minimal kamu memegang token
  senilai $8 supaya boleh mengeluarkan callout untuk token tersebut. Tujuannya anti-spam —
  supaya orang tidak asal shill token yang tidak dia pegang.

📌 **Ini fitur sosial, bukan indikator keamanan.** Callout ramai ≠ token bagus. Justru
callout yang tiba-tiba membanjir di token berumur 30 menit adalah pola yang perlu dicurigai.

---

## 6. Phishing vs Bundler — bedanya di mana

Ini dua label yang **paling sering dikira sama**, karena keduanya sama-sama berarti
"banyak wallet, satu dalang". Bedanya ada pada **dimensi yang diukur**.

### Bundler = soal CARA BELI (mekanika transaksi)

- Diukur dari **struktur block**
- Banyak wallet beli di **block yang sama**, transaksi dibungkus jadi satu bundle
- Terjadi **di detik launch**
- Uangnya **keluar beneran** (mereka beli pakai ETH/SOL)
- Tujuan: menyerok supply besar tapi terlihat seperti "banyak orang beli"
- Deteksi: **struktural**, dari data block itu sendiri

### Phishing = soal SIAPA YANG PEGANG (reputasi wallet)

- Label menempel di **alamat wallet**-nya, dibawa dari **riwayat wallet itu sendiri**
  (pernah terlibat drainer / scam / kampanye phishing)
- Token biasanya sampai ke situ lewat **transfer / airdrop**, bukan beli
- Terjadi **setelah** launch
- Deteksi: **reputasional**, dari database alamat + pelacakan pola sebaran

### 🧠 Analogi

> **Bundler** = *caranya orang-orang itu masuk ke ruangan.*
> **Phishing** = *catatan kriminal orang yang ada di dalam ruangan.*

### Siapa yang memberi tag Phishing?

**Bukan voting komunitas.** Ini sistem internal GMGN — sama seperti label "rats"/insiders.
Metodenya lewat **token transfer detection**: melacak pola penyebaran token, lalu
mencocokkannya dengan database alamat yang pernah terlibat aktivitas phishing.

### Kenapa % Phishing bisa setinggi 50–60%?

GMGN menyebut dua skenario resmi:

1. **Satu sumber menyemprot token ke banyak wallet ber-tag phishing** — supaya angka
   "Holders" terlihat ramai padahal palsu. Ini manipulasi metrik murni.
2. **Dev airdrop ke wallet KOL / wallet terkenal** — supaya retail melihat
   *"wah wallet si anu pegang token ini, berarti dia beli dong!"* padahal dikasih gratis.

Ditambah satu skenario yang perlu disadari:

3. **Semi false-positive.** Kalau token di-airdrop massal ke ribuan alamat acak, sebagian
   alamat itu memang sudah ter-flag dari kasus lain yang tidak berhubungan. Dev-nya
   mungkin tidak sengaja — tapi **efeknya buat kamu sama saja: angka holder tidak valid.**

### Kombinasi yang perlu dibaca

| Kombinasi | Artinya |
|---|---|
| Bundler tinggi, Phishing rendah | Supply terkonsentrasi diam-diam **sejak block 0**. Dump bisa serempak. **Lebih berbahaya secara langsung** |
| Bundler rendah, Phishing tinggi | Launch-nya natural, tapi supply sekarang nyangkut di wallet reputasi buruk. **Angka Holders tidak bisa dipercaya** |
| Dua-duanya tinggi | Kombinasi terburuk |
| Dua-duanya rendah | Belum tentu aman — cek metrik lain |

---

## 7. Bundler secara on-chain (deep dive)

### Beli biasa vs Bundle — bedanya bukan "banyak wallet"

**Beli biasa:**
1 transaksi → masuk mempool publik → block builder/sequencer memasukkannya ke block manapun.
Kamu **tidak mengontrol** landing di block ke berapa, tidak mengontrol urutan, dan
transaksinya berdiri sendiri.

> ❗ **Punya 50 wallet lalu beli satu-satu manual TETAP BUKAN bundling.**
> Itu 50 transaksi terpisah yang mendarat di block acak. GMGN tidak akan mengetag itu sebagai bundler.

**Bundle:**
Sekumpulan transaksi yang dijamin:
- masuk **block/slot yang sama**
- dengan **urutan yang ditentukan**
- bersifat **atomic** (satu gagal = semua batal)

> 🔑 **Kuncinya bukan "banyak wallet" — kuncinya ATOMICITY + KONTROL URUTAN.**

### Mekanisme per chain

| Chain | Cara bundling |
|---|---|
| **Solana** | **Jito bundle** — maksimal 5 tx, dikirim ke **Jito Block Engine** (bukan RPC biasa), bayar *tip* ke validator. Validator menjamin masuk slot yang sama, urutan sesuai, all-or-nothing |
| **Ethereum / L2 (EVM)** | **(a)** *Flashbots / builder bundle* — private, bypass mempool. **(b)** — dan ini yang paling umum untuk launch — **satu smart contract yang di dalam 1 transaksi melakukan: deploy token → buy dari wallet A → wallet B → wallet C → …**. Atomic secara desain, tidak butuh block builder sama sekali |

📌 **Robinhood Chain itu L2/EVM, bukan Solana.** Jadi di Pons, bundling paling praktis =
jalur **(b)**: satu transaksi kontrak yang membuat token sekaligus menyerok supply ke banyak wallet.

**Cara mengeceknya:** buka block explorer di pool creation. Kalau puluhan buy menempel di
**satu tx hash** atau **satu block**, dan wallet-wallet itu funding-nya dari sumber yang sama
→ itu bundle.

### ⚠️ Dua arti "bundler" yang berlawanan

Kata "bundler" di CT dipakai untuk **dua hal yang bertolak belakang**. Ini sumber kebingungan terbesar.

#### Arti #1 — Dev-side bundler (yang di-flag GMGN)

Deployer yang membundling **launch-nya sendiri**: create token + buy dari 20–30 wallet
dalam block 0. Hasilnya dia memegang 30% supply tapi on-chain terlihat tersebar di 30
alamat "berbeda".

→ Inilah yang menaikkan metrik **`Bundler %`** di panel GMGN.
→ Motif: menyembunyikan konsentrasi, atau mengalahkan sniper di launch-nya sendiri.

#### Arti #2 — Sniper-side bundler

**Bot pihak ketiga** yang memantau new pair, lalu menembak bundle beli begitu pool terbuka.

→ Ini yang dimaksud kalau orang bilang *"bundler-nya masuk"* atau *"pasti ada bundler masuk"*.
→ Di sini bundler **bukan dev** — dev hanya jadi umpan yang berharap tertangkap filter bot.

> Jadi kalau ada yang bilang *"tergantung bundle-nya masuk enggak"*, artinya:
> *"tergantung bot-bot itu mau memborong token gue apa enggak."*
> **Sama sekali berbeda** dari "gue yang bundling".

### "Emangnya kita bisa jadi bundler?"

Secara teknis **bisa** — dan itu justru masalahnya, tool-nya dijual bebas. Yang dibutuhkan
secara konsep:

1. Banyak wallet yang sudah di-fund
2. Akses ke jalur eksekusi atomic (Jito tip di Solana / kontrak multicall di EVM)
3. Skrip yang menyusun urutan tx
4. Modal — karena buy-nya benar-benar mengeluarkan uang

Tapi realistisnya: **ini bukan "beli biasa versi canggih".** Ini infrastruktur yang dibangun
untuk dua tujuan — **menang cepat** atau **menyamarkan kepemilikan**. Yang kedua itulah yang
membuatnya jadi red flag di semua dashboard.

### 🚩 Catatan penting soal false positive

`Bundler %` tinggi **tidak selalu berarti dev jahat** — sniper bot pihak ketiga yang bundling
juga ikut terhitung. Makanya **jangan baca sendirian**. Silang dengan:
- `Insiders`
- `Funding wallet` (di panel Dev Token)
- Rekam jejak dev (rasio Migrated + Dev's Best Token + Rug History)

---

## 8. Ekonomi Launchpad & Creator Fees

Bagian ini menjelaskan **kenapa banyak token sampah terus bermunculan** — ada insentif ekonominya.

### Modelnya

Launchpad modern memberi **bagian dari trading fee kepada deployer token**:

1. Deploy token, modal receh (beberapa dolar)
2. Token mendapat volume perdagangan
3. Deployer menarik % dari fee itu — **tanpa perlu menjual token sendiri**

Contoh nyata di **Pons (Robinhood Chain)**:
- Pons mengambil **1% dari setiap buy & sell**
- Sebagian mengalir ke creator (sejak V2, dibayar dalam ETH)
- Contoh: volume $3.000 × 1% = $30 total fee → creator dapat sekitar **$16**

### Skalanya nyata, bukan main-main

- Creator di Pons tercatat sudah menarik **$25 juta+ kumulatif** fee
- Protokolnya sempat mencatat fee harian jutaan dolar
- Pons berperan di Robinhood Chain seperti Pump.fun di Solana

### Di mana bundler masuk ke persamaan ini

Deployer tidak butuh komunitas — dia butuh **volume**. Dan volume tercepat datang dari
**bot sniper/bundler** yang otomatis memborong token baru dengan narasi viral.

Maka strateginya jadi: **bikin ticker/narasi yang lolos filter bot.** Begitu bot masuk
memborong di 10 detik pertama → volume langsung ada → fee langsung mengalir → modal balik.

### 🧊 Baca implikasinya dingin-dingin

> Fee yang didapat creator itu asalnya dari **1% yang dibayar setiap orang yang beli dan jual**.
> **Uang creator = uang trader.** Yang menyediakan volume awal adalah bot bundler —
> yang ujungnya menjual ke retail.
>
> **Modelnya zero-sum. Uangnya tidak muncul dari udara.**

### Bias yang perlu diwaspadai

- **Survivorship bias** — yang bercerita di grup hanya yang berhasil. Yang deploy 20 token
  dan nol volume tidak posting.
- Cerita "modal $4 jadi $16" itu benar secara matematis, tapi tidak menceritakan berapa
  kali gagal.

### ⚖️ Wilayah yang bermasalah

Beberapa praktik yang sering menyertai model ini **bukan sekadar berisiko rugi**, tapi bisa
bermasalah secara hukum tergantung yurisdiksi:

- **VPN/proxy untuk mengakali pembatasan geografis** platform (Robinhood & produk
  tokenized-equity punya aturan yurisdiksi yang mengikat)
- **Tool "untraceable funding"** yang mendanai ratusan wallet dalam hitungan detik —
  fungsi utamanya membuat wallet terlihat tidak berhubungan padahal satu pemilik
- **Akun sosial baru + identitas palsu** untuk membangun narasi

Ini definisi teknis dari **membuat profil supply palsu**. Pahami mekaniknya untuk
melindungi diri — itu berbeda dari mempraktikkannya.

---

## 9. Studi Kasus: 2 Token Dibandingkan

Data diambil langsung dari GMGN, 2026-09-07.

| Metrik | **Parlay** `0xb3…cf05` | **UPS** `0xb1…bd81` |
|---|---|---|
| Market Cap | $500.70K | $648.38K |
| Umur | 31 menit | 20 jam |
| Top 10 | 14.74% ✅ | 11.66% ✅ |
| DEV | 0% | 0% |
| Holders | 2,008 | 890 |
| Snipers | 1 / 70 ✅ | 3 / 70 |
| Insiders | 2.5% | 0% ✅ |
| **Phishing** | **50.5%** 🔴 | **63.2%** 🔴 |
| Bundler | 0.2% ✅ | 0% ✅ |
| Dex Paid | $299 (CTO) | $398 (CTO) |
| NoHoneypot / Verified / Renounced | ✓ ✓ ✓ | ✓ ✓ ✓ |
| Burnt | 95% | 95% |
| **Dev — Total Pairs** | 1 | 2 |
| **Dev — Migrated** | **100%** (1/1) | **50%** (1/2) |
| Dev's Best Token ATH | $671K | $660K |

### Analisis

**Kenapa % Migrated beda?**
Dev Parlay baru meluncurkan 1 token dan lulus → 100%. Dev UPS meluncurkan 2 token,
satu lulus satu gagal (yang gagal hanya sampai ATH $27.8K dengan 18 holders) → 50%.

**Yang terlihat wajar di keduanya:**
Top 10 rendah (< 15%), Bundler ~0%, Insiders rendah, Burnt 95%, semua flag kontrak hijau.
Artinya launch-nya tidak dibundling, dan kontraknya tidak punya jebakan teknis.

**🔴 Yang jadi masalah utama — Phishing 50–63% di keduanya:**
Mayoritas "holder" adalah wallet ber-tag phishing hasil sebaran dari satu sumber.
Artinya angka **Holders 2,008 / 890 kemungkinan besar digelembungkan** — komunitas riilnya
jauh lebih kecil dari itu.

**Kesimpulan pembacaan:**
Bukan berarti "pasti rug". Tapi metrik sosial (Holders) di kedua token ini **tidak bisa
dipakai untuk menilai hype**, dan itu menghapus salah satu alasan utama orang membeli memecoin.

---

## 10. Checklist Baca Token 30 Detik

Urutan ini disusun dari yang **paling cepat mematikan** ke yang paling nuansa.

### 🔴 Tahap 1 — Deal breaker (kalau kena, berhenti)

- [ ] **Honeypot?** → kalau ya, **STOP**
- [ ] **Blacklist = Yes?** → **STOP**
- [ ] **Sell tax ekstrem** (mis. > 20%, apalagi 99%)? → **STOP**
- [ ] **Mint Disable = No?** → supply bisa digelembungkan → **STOP**
- [ ] **Dev punya Rug History?** → **STOP**

### 🟡 Tahap 2 — Konsentrasi supply

- [ ] **Top 10 > 30%?** → merah
- [ ] **Bundler tinggi?** → supply terkonsentrasi diam-diam sejak block 0
- [ ] **Insiders tinggi?** → supply dev kemungkinan dipecah ke banyak wallet
- [ ] **Snipers masih banyak yang hold (x/70)?** → tekanan jual menunggu
- [ ] **Burnt < 100%?** → sisa LP masih bisa ditarik

### 🟠 Tahap 3 — Validitas metrik sosial

- [ ] **Phishing tinggi?** → **angka Holders tidak valid**, jangan dipakai menilai hype
- [ ] **Holders besar tapi token baru beberapa menit?** → kemungkinan airdrop, bukan pembeli
- [ ] **Callout tiba-tiba membanjir di token super muda?** → pola shill terkoordinasi

### 🔵 Tahap 4 — Rapor developer (sering paling menentukan)

- [ ] **Total Pairs** — berapa token yang pernah dia launch?
- [ ] **% Migrated** — berapa yang lulus? (ingat: n kecil = tidak berarti)
- [ ] **Dev's Best Token ATH** — ceiling realistisnya di mana?
- [ ] **Last Token Launched** — kalau launch beruntun tiap jam → serial spammer
- [ ] **🔥 Funding wallet** — telusuri. Pernah mendanai rug? Ini sinyal terkuat
- [ ] **DEV 0%?** → jangan lega dulu, silang dengan Insiders

### ⚪ Tahap 5 — Konteks (paling lemah, jangan dijadikan alasan utama)

- [ ] Dex Paid — hanya berarti ada yang bayar iklan
- [ ] Verified / Renounced — bagus, tapi bisa dipalsukan
- [ ] CTO — netral, sering muncul setelah dev berhenti

### 🧠 Aturan emas

> **Tidak ada satu metrik pun yang boleh dibaca sendirian.**
> Selalu silang minimal 3: **konsentrasi supply** + **validitas holder** + **rekam jejak dev**.

---

## 11. Kesalahan Umum & Jebakan

| Kesalahan | Kenapa salah |
|---|---|
| "Holders 2000, ramai nih!" | Bisa 100% palsu dari airdrop ke wallet phishing |
| "DEV 0%, dev udah gak pegang, aman" | Bisa dipindah ke wallet lain → cek Insiders |
| "Renounced ✓, aman" | Dokumentasi GMGN sendiri bilang status ini bisa dipalsukan |
| "Dex Paid $398, dev serius nih" | Itu cuma bayar iklan. Rugger juga bayar |
| "Volume 10 detik pertama gede, minatnya tinggi!" | Itu bot. Bot punya **satu tombol jual** |
| "Migrated 100%, dev-nya jago" | Kalau Total Pairs = 1, itu sampel n=1. Tidak berarti apa-apa |
| "Bundler tinggi = pasti dev jahat" | Sniper bot pihak ketiga juga terhitung. Silang dengan Funding & Insiders |
| "Semua flag hijau, aman" | Semua flag hijau hanya berarti **tidak ada jebakan teknis di kontrak**. Rug lewat penjualan supply tetap bisa terjadi |
| "Caller besar ngomongin, pasti bagus" | Airdrop ke wallet KOL adalah taktik yang GMGN sebut eksplisit |

---

## 12. Glosarium Singkat

| Istilah | Arti |
|---|---|
| **Bonding curve** | Algoritma harga naik otomatis seiring pembelian, sebelum token masuk DEX |
| **Migrate / Graduate / Bonded** | Token lulus dari bonding curve, likuiditas pindah ke DEX sungguhan |
| **Bundle** | Kumpulan transaksi atomic, satu block, urutan terkontrol |
| **Bundler** | (1) Dev yang membundling launch-nya sendiri, atau (2) bot pihak ketiga yang memborong token baru |
| **Sniper** | Wallet/bot yang beli di beberapa block pertama setelah pool dibuka |
| **Insider / "rats"** | Wallet yang memegang token tanpa pernah membelinya setelah trading buka |
| **Honeypot** | Kontrak yang membuatmu bisa beli tapi tidak bisa jual |
| **Renounce** | Melepas ownership kontrak |
| **LP Burn** | Membakar LP token supaya likuiditas tidak bisa ditarik |
| **CTO** | Community Take Over — proyek dilepas dev ke komunitas |
| **Dex Paid** | Dev membayar Enhanced Token Info di DEX Screener |
| **Creator fee** | Bagian trading fee yang mengalir ke deployer token |
| **Jito bundle** | Mekanisme bundling atomic di Solana (maks 5 tx, pakai tip validator) |
| **Flashbots bundle** | Mekanisme bundling private di Ethereum, bypass mempool publik |
| **Multicall** | Satu transaksi EVM yang menjalankan banyak aksi sekaligus — cara bundling termudah di EVM |
| **Paper hand / Diamond hand** | Holder jangka pendek / jangka panjang |
| **ATH MC** | All-Time-High Market Cap |

---

## 13. Sumber

**Dokumentasi resmi GMGN:**
- [CA Security Checks](https://docs.gmgn.ai/index/ca-security-checks)
- [Insider Traders, Snipers, First 70 Buyers](https://docs.gmgn.ai/index/insider-traders-snipers-first-70-buyers)
- [Featured Icon Definition](https://docs.gmgn.ai/index/featured-icon-definition)
- [Token page: Chart, Activity, Trading system](https://docs.gmgn.ai/index/token-page-chart-multicharts-activity-trading-system)
- [GMGN Callout OpenAPI](https://docs.gmgn.ai/index/gmgn-callout-openapi)
- [GMGN Q&A](https://docs.gmgn.ai/index/q-a)
- [GMGN.Ai — "Phishing icon: What does it mean?" (pengumuman resmi)](https://x.com/gmgnai/status/1963882916460769393)

**Teknis bundling:**
- [What is a Crypto Bundler? — Alchemy](https://www.alchemy.com/overviews/what-is-a-bundler)

**Ekonomi launchpad:**
- [Pons vs Pump.fun: the launchpad war nobody expected — crypto.news](https://crypto.news/pons-vs-pumpfun-launchpad-war-robinhood-chain/)
- [PONS, LONG and the Robinhood Chain Launchpad Boom: Where the Fees Are Coming From — MEXC](https://www.mexc.com/learn/article/pons-long-and-the-robinhood-chain-launchpad-boom-where-the-fees-are-coming-from/1)
- [Pons: Token Creators Have Earned Over $25 Million in Cumulative Fees — Lookonchain](https://www.lookonchain.com/feeds/70811)
- [Pons Fees, Revenue & Volume — DefiLlama](https://defillama.com/protocol/pons)

**Token yang dianalisis:**
- [Parlay — GMGN](https://gmgn.ai/robinhood/token/0xb37bb72725ff0e0a08be1b0942dab0d61f66cf05)
- [UPS — GMGN](https://gmgn.ai/robinhood/token/0xb1f8bafb97d40a011715c1ba8a822030b20bbd81)

---

*Dokumen dibuat 2026-09-07. Metrik token bersifat snapshot dan berubah setiap saat.*
*Sekali lagi: ini materi edukasi cara membaca data, bukan nasihat keuangan.*
