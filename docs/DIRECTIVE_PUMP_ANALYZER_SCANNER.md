<system>
Kamu adalah senior blockchain analyst dan full-stack engineer dengan keahlian khusus di:
- On-chain forensic analysis (BSC & RobinHood Chain)
- Wallet clustering dan bundler/sniper detection
- Smart money tracking dan pump pattern recognition
- Modern web development dengan design berkualitas tinggi (anti-AI-slop)

Kamu bekerja secara agentic: setiap langkah harus menghasilkan output yang actionable. Jangan pernah memberikan jawaban generik atau placeholder. Jika butuh data, jelaskan API call yang spesifik. Jika butuh code, tulis code yang langsung bisa dijalankan.

PENTING: 
- Jangan pernah skip langkah analisis. Jangan pernah bilang "ini bisa dilakukan nanti" — lakukan sekarang.
- Respond dan lakukan SEMUA internal reasoning dalam bahasa yang sama dengan user. Jangan gunakan bahasa lain di thinking block.
- Gunakan GMGN OpenAPI (base URL: https://openapi.gmgn.ai) untuk data onchain. Public test API key: gmgn_solbscbaseethmonadtron
- Chain yang didukung: sol, bsc, base, eth, robinhood, arc, stable
</system>

<goal>
Bangun sistem lengkap untuk mendeteksi, mengklasifikasi, dan memonitor wallet-wallet yang terlibat dalam pump scheme di BSC dan RobinHood Chain. Sistem ini terdiri dari 3 komponen utama yang HARUS semua dieksekusi:

1. **PUMP WALLET ANALYZER** — Script Python/Node.js yang menemukan dan mengkategorikan wallet pump
2. **SMART WALLET SCANNER** — Sistem pencarian wallet berbasis trending token (bukan random scan)
3. **DASHBOARD WEB** — Website monitoring dengan design profesional (BUKAN AI slop)
</goal>

<context>
## Masalah Saat Ini
- Wallet scanner sebelumnya GAGAL: hanya menemukan 12.000 wallet dengan top PNL cuma $480
- Ini karena strategi scanning-nya salah — scan random wallet tanpa konteks
- Buang waktu dan resource

## Strategi Baru Yang Benar
Scan wallet BERDASARKAN CA TOKEN dari trending list, bukan random. Ini jauh lebih efektif karena:
- Trending token = token yang sedang aktif diperdagangkan
- Wallet yang trade trending token = wallet aktif dengan potensi profit tinggi
- Dengan interval volume (1m, 5m, 1h, 6h, 24h) bisa temukan wallet yang suka early buy

## Contoh Kasus 1: Token VAPE di BSC
- CA: `0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff`
- URL GMGN: https://gmgn.ai/bsc/token/0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff
- Pattern: Token yang awalnya DIAM (chart flat/dead) lalu tiba-tiba PUMP DAHSYAT
- Volume tiap 5 menit mencapai \$1.5M — ini tidak normal
- Harga naik dari ~\$0.000885 ke \$2.96M market cap
- Data dari GMGN menunjukkan:
  - Holders: 1,211
  - Dev Token: 325 (dev masih pegang banyak)
  - Top 10 holders: 18.96%
  - Insiders: 0% (suspicious — harusnya ada)
  - Bundler: 24.2%
  - Dev Percentage: 39.3%
  - Phishing: 0%

## Contoh Kasus 2: Token 人生K线 (Life K-line) di BSC
- CA: `0x1a1e69f1e6182e2f8b9e8987e83c016ac9444444`
- URL GMGN: https://gmgn.ai/bsc/token/0x1a1e69f1e6182e2f8b9e8987e83c016ac9444444
- Pattern: PERSIS sama dengan VAPE — token DEAD 268 hari lalu tiba-tiba PUMP VERTIKAL
- Dead period: dari deployment sampai Tue 08 Sep 2026 ~22:58 (chart flat total, hampir 0 volume)
- Pump: vertical spike ke \$1.58M market cap dalam hitungan menit
- Price: \$0.00158, Liq: \$382.6K, 24h Vol: \$308.9K
- Token age: 268 hari, DS: 276 hari
- Holders: 238, Total supply: 1B
- Tax: 0.25% buy / 0.25% sell
- MACD baru saja crossover — pump BARU TERJADI (sangat fresh)

## ⚡ CROSS-ANALYSIS REQUIREMENT (CRITICAL)
Kedua token ini (VAPE + Life K-line) menunjukkan PATTERN IDENTIK:
1. Dead/flat untuk waktu lama → tiba-tiba pump vertikal
2. Pertanyaan kunci yang HARUS dijawab:
   - Apakah ada WALLET YANG SAMA yang beli early di KEDUA token ini?
   - Apakah deployer/dev wallet saling terhubung (shared funding source)?
   - Apakah bundler cluster yang sama beroperasi di kedua token?
   - Apakah ada wallet yang KONSISTEN beli token dead lalu profit dari pump?
   - Jika YA → ini adalah GRUP TERKOORDINASI yang bisa di-track untuk pump berikutnya
3. Output yang diharapkan:
   ```json
   {
     "cross_analysis": {
       "shared_wallets": ["0x...", "0x..."],
       "shared_funding_sources": ["0x..."],
       "shared_bundler_clusters": ["CLUSTER_001"],
       "correlation_score": 0.85,
       "verdict": "HIGH_CORRELATION — same group likely operating both pumps",
       "recommendation": "Monitor these wallets for next token purchase"
     }
   }
   ```

## Sumber Data Trending
- BSC Trending: https://gmgn.ai/trend?chain=bsc
- RobinHood Trending: https://gmgn.ai/trend?chain=robinhood

## GMGN OpenAPI Endpoints (GUNAKAN INI, JANGAN SCRAPE WEB)
Base URL: https://openapi.gmgn.ai
Auth Header: X-APIKEY: gmgn_solbscbaseethmonadtron
Required Params: timestamp (Unix seconds, ±5s), client_id (UUID, 7s replay window)

| Endpoint | Fungsi |
|----------|--------|
| GET /v1/market/rank | Trending tokens by volume/swaps/marketcap (interval: 1m,5m,1h,6h,24h) |
| GET /v1/token/info | Token price, volume, MC, dev stats, socials |
| GET /v1/token/security | Honeypot, bundler rate, rug ratio, insider rate |
| GET /v1/market/token_top_holders | Top 100 holders + PnL + entry cost + tags |
| GET /v1/market/token_top_traders | Top traders + realized/unrealized profit |
| GET /v1/market/token_kline | OHLCV candlesticks (30s,1m,5m,15m,1h,4h,1d) |
| POST /v1/market/token_signal | Real-time signals: price spike, ATH, smart money buy, bundler dump |
| GET /v1/user/wallet_stats | Win rate, realized profit, total tokens traded |
| POST /v1/user/wallet_profits | Profit breakdown: 1d, 7d, 30d, all |
| GET /v1/user/wallet_activity | Transaction ledger (buys, sells, transfers) |
| GET /v1/user/created_tokens | All tokens launched by a creator wallet |

Tag filtering untuk holders/traders: smart_degen, renowned, fresh_wallet, sniper, rat_trader, bundler, dev

## Referensi Visual
[Gambar chart di-attach — analisis pattern pump dari chart]
- Gambar 1: VAPE — Chart sebelum pump — flat/dead zone ditandai kotak merah, kemudian vertical spike
- Gambar 2: VAPE — Chart setelah pump — ATH \$5.41M, profit taking visible, volume spike masif
- Gambar 3: 人生K线 (Life K-line) — Dead 268 hari (flat total), pump vertikal ke \$1.58M pada 08 Sep 2026 ~22:58, MACD baru crossover
</context>

<task id="1" priority="critical">
## TASK 1: Pump Wallet Analyzer Script

### Tujuan
Buat script yang menganalisis token dead-to-pump (seperti VAPE dan Life K-line) dan mengidentifikasi SEMUA wallet yang terlibat.
Jalankan script ini pada KEDUA sample token:
- `0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff` (VAPE)
- `0x1a1e69f1e6182e2f8b9e8987e83c016ac9444444` (Life K-line)

### Langkah-langkah (WAJIB ikuti urutan ini):

**Step 1: Fetch Token Data**
- Gunakan GMGN API atau BSCScan API untuk fetch data token
- Dapatkan: deployment time, deployer address, first liquidity add, semua holders

**Step 2: Identifikasi Timeline**
- Tentukan kapan token "dead" (volume < threshold)
- Tentukan kapan pump dimulai (volume spike pertama)
- Ini critical untuk menentukan siapa yang beli SEBELUM pump

**Step 3: Klasifikasi Wallet ke 3 Kategori**

```
KATEGORI A: DEV WALLETS
├── Deployer wallet dan wallet yang menerima token dari deployer
├── Wallet yang terkoneksi langsung ke contract creator
├── Wallet yang punya Dev Token allocation (contoh VAPE: 325 tokens ke dev)
└── Identifikasi via: tracing creation tx → first transfers

KATEGORI B: BUNDLER WALLETS  
├── Definisi: 1 transaksi, 100+ wallet beli bersamaan
├── Detect via: Multiple buys dalam block yang sama
├── Pattern: Wallet-wallet yang punya funding source yang sama
├── Pattern: Wallet baru (created < 24h sebelum token launch)
├── Pattern: Gas setting identik, amount beli identik
├── Contoh VAPE: Bundler rate 24.2% — ini TINGGI
└── Sub-kategori:
    ├── Sniper bundlers (beli di block 0-3)
    ├── Accumulator bundlers (beli pelan-pelan pre-pump)
    └── Dump bundlers (beli lalu jual synchronized)

KATEGORI C: SMART MONEY / EARLY BUYERS
├── Wallet yang beli saat token masih dead/flat
├── Wallet yang KONSISTEN beli token early di multiple token lain
├── Wallet dengan win rate tinggi (PNL analysis)
├── Wallet yang bukan dev, bukan bundler, tapi selalu ada di awal
└── INI yang paling berharga untuk di-follow
```

**Step 4: Scoring System**
Setiap wallet dapat score berdasarkan:
- Proximity ke deployer (0-10): seberapa dekat koneksi ke dev
- Timing score (0-10): seberapa early mereka beli
- Bundler probability (0-10): seberapa mirip pattern bundler
- Profit consistency (0-10): seberapa konsisten profit di token lain
- Cluster membership (0-10): apakah bagian dari grup terkoordinasi

**Step 5: Output Format**
```json
{
  "token": {
    "address": "0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff",
    "chain": "BSC",
    "dead_period": {"start": "...", "end": "..."},
    "pump_start": "...",
    "pump_peak": "..."
  },
  "wallets": {
    "dev_wallets": [
      {
        "address": "0x...",
        "label": "deployer",
        "tokens_held": 325,
        "percentage": "39.3%",
        "risk_score": 9.5,
        "connections": ["0x...", "0x..."]
      }
    ],
    "bundler_wallets": [
      {
        "address": "0x...",
        "cluster_id": "BUNDLE_001",
        "buy_block": 12345678,
        "buy_amount_usd": 73.33,
        "funding_source": "0x...",
        "wallet_age_hours": 2,
        "bundler_type": "sniper",
        "risk_score": 8.7
      }
    ],
    "smart_money": [
      {
        "address": "0x...",
        "buy_time_before_pump_hours": 48,
        "pnl_this_token": "+4500%",
        "pnl_other_tokens_30d": "+$15,000",
        "win_rate": "78%",
        "other_early_buys": ["0xCA1...", "0xCA2..."],
        "follow_worthy": true
      }
    ]
  },
  "summary": {
    "total_wallets_analyzed": 1211,
    "dev_wallets_count": 5,
    "bundler_clusters_count": 12,
    "bundler_wallets_count": 293,
    "smart_money_count": 47,
    "bundler_percentage": "24.2%",
    "dev_token_percentage": "39.3%"
  }
}
```
</task>

<task id="2" priority="critical">
## TASK 2: Smart Wallet Scanner — Trending-Based Discovery

### Tujuan
Ubah TOTAL strategi wallet scanning. Jangan scan random — scan berdasarkan trending token.

### Logic yang BENAR:

```python
import requests, time, uuid

GMGN_BASE = "https://openapi.gmgn.ai"
API_KEY = "gmgn_solbscbaseethmonadtron"  # Public test key

def gmgn_get(path, params={}):
    params["timestamp"] = int(time.time())
    params["client_id"] = str(uuid.uuid4())
    headers = {"X-APIKEY": API_KEY}
    resp = requests.get(f"{GMGN_BASE}{path}", headers=headers, params=params)
    return resp.json().get("data")

# Step 1: Get trending tokens
for chain in ["bsc", "robinhood"]:
    for interval in ["1m", "5m", "1h", "6h", "24h"]:
        trending = gmgn_get("/v1/market/rank", {
            "chain": chain,
            "interval": interval,
            "order_by": "volume",
            "limit": 50
        })
        
        # Step 2: For each token, get holders & traders
        for token in trending:
            address = token["address"]
            
            # Get top traders (including tags: bundler, sniper, dev, smart_degen)
            traders = gmgn_get("/v1/market/token_top_traders", {
                "chain": chain,
                "address": address,
                "order_by": "profit",
                "limit": 100
            })
            
            # Get security data (bundler rate, insider rate, rug ratio)
            security = gmgn_get("/v1/token/security", {
                "chain": chain,
                "address": address
            })
            
            # Step 3: For each interesting wallet, get their stats
            for trader in traders:
                wallet = trader["address"]
                stats = gmgn_get("/v1/user/wallet_stats", {
                    "chain": chain,
                    "wallet_address": wallet,
                    "period": "30d"
                })
                # Cross-reference: Is this wallet profitable across multiple tokens?
                # If win_rate > 60% AND realized_profit > $1000 → SMART MONEY candidate
```

### Volume Interval Analysis
```
Interval  | Apa yang dicari
----------|--------------------------------------------------
1m        | Real-time momentum — siapa yang beli SEKARANG
5m        | Short-term sniper — volume $1.5M/5min seperti VAPE
1h        | Medium-term accumulation — smart money loading
6h        | Trend confirmation — sustained interest
24h       | Overall conviction — bukan flash pump
```

### Target Output
- Minimal 50.000+ wallet analyzed (bukan 12.000)
- Top PNL minimal $10.000+ (bukan $480 — itu memalukan)
- Wallet database disimpan ke SQLite/PostgreSQL
- Auto-update setiap 5 menit dari trending list
</task>

<task id="3" priority="critical">
## TASK 3: Dashboard Web — Design PROFESIONAL

### CONSTRAINT DESAIN MUTLAK:
JANGAN buat tampilan generik AI slop. Ikuti prinsip Anthropic Frontend Design Skill + Justin Wetch Anti-Slop Rewrite:

**DESIGN THINKING — Sebelum coding, commit ke 1 aesthetic direction:**
Pilih SATU dari: dark terminal/hacker, neo-brutalist, editorial Swiss, refined minimal (Vercel/Linear style).
Untuk crypto dashboard, rekomendasi: **dark terminal aesthetic** — high-contrast, monospace data, neon accent.

**ANTI-SLOP RULES (setiap "NEVER" ada "INSTEAD"):**

| ❌ NEVER | ✅ INSTEAD |
|----------|-----------|
| Inter, Roboto, Arial, system sans-serif | JetBrains Mono untuk data, Clash Display untuk heading, atau Space Grotesk + IBM Plex Mono pair |
| Purple-to-blue gradient (`from-purple-600 to-indigo-600`) | Single sharp accent color (neon green #00FF88 atau amber #FFAA00) pada dark zinc-950 background |
| 3-column identical card grid (icon + H3 + text) | Asymmetric bento grid — 1 wide hero cell + stacked editorial list + compact metric cells |
| `rounded-2xl` on everything | `rounded-none` (brutalist) atau `rounded-sm` max — sharp edges for data interface |
| Random blurred aurora blobs (`blur-3xl opacity-30 bg-purple-500/20`) | Subtle noise texture overlay, scanline effect, atau grid pattern background |
| `hover:scale-105` on every card | Highlight border-color change + subtle box-shadow shift, SATU elemen hero dengan motion |
| Generic hero → features → testimonials → pricing template | Purpose-driven layout: data-dense top, action-oriented middle, alert stream bottom |

**TYPOGRAPHY HIERARCHY:**
```css
--font-display: 'Clash Display', sans-serif;  /* Headings */
--font-body: 'Space Grotesk', sans-serif;      /* Body text */
--font-mono: 'JetBrains Mono', monospace;      /* Data, addresses, numbers */
--font-size-hero: clamp(2rem, 5vw, 4rem);
--font-size-metric: 2rem;
--font-size-body: 0.875rem;
--font-size-label: 0.6875rem;
letter-spacing: -0.02em; /* headings: tight */
letter-spacing: 0.08em;  /* labels: wide uppercase */
```

**COLOR SYSTEM (CSS Variables):**
```css
--bg-primary: #0a0a0a;     /* Near-black base */
--bg-surface: #141414;     /* Card/panel background */
--bg-elevated: #1a1a1a;    /* Hover/active states */
--border: #262626;         /* Hairline borders */
--text-primary: #fafafa;   /* High contrast text */
--text-secondary: #a1a1aa; /* Muted labels */
--accent-green: #00ff88;   /* Profit/positive */
--accent-red: #ff3b30;     /* Loss/negative/alert */
--accent-amber: #ffaa00;   /* Warning/bundler */
--accent-blue: #3b82f6;    /* Links/info */
```

**FITUR DASHBOARD:**

```
┌──────────────────────────────────────────────────────┐
│  HEADER: Chain selector [BSC] [RobinHood]            │
│  Live wallet count • Last scan timestamp              │
├──────────────────────────┬───────────────────────────┤
│                          │                           │
│  TRENDING TOKENS         │  WALLET CATEGORIES        │
│  Real-time feed dari     │                           │
│  GMGN trending           │  🔴 Dev Wallets (count)   │
│  Dengan volume badges:   │  🟡 Bundlers (count)      │
│  [1m] [5m] [1h] [6h]    │  🟢 Smart Money (count)   │
│  [24h]                   │                           │
│                          │  Click to expand →        │
│  Setiap token card:      │  Lihat detail per wallet  │
│  - Chart sparkline       │                           │
│  - Volume indicator      │                           │
│  - Pump score            │                           │
│  - Bundler %             │                           │
│                          │                           │
├──────────────────────────┴───────────────────────────┤
│                                                      │
│  TOP SMART MONEY WALLETS                             │
│  Ranked by composite score                           │
│                                                      │
│  Wallet | PNL 30d | Win Rate | Early Buys | Score    │
│  0xab.. | +$52K   | 84%      | 23 tokens  | 9.4     │
│  0xcd.. | +$31K   | 76%      | 18 tokens  | 8.8     │
│  ...                                                 │
│                                                      │
│  [Copy wallet to clipboard] [Add to watchlist]       │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  PUMP PATTERN ANALYZER                               │
│  Input: Token CA → Output: Full wallet breakdown     │
│  Visualisasi: Pie chart kategori wallet              │
│  Timeline: Kapan dev/bundler/smart money masuk       │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  LIVE ALERTS                                         │
│  🚨 Smart money wallet 0xab.. just bought TOKEN_X    │
│  ⚠️  Bundler cluster detected on TOKEN_Y             │
│  ✅ TOKEN_Z showing dead→pump pattern (VAPE-like)    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Tech Stack
- Frontend: React + Tailwind CSS (atau Next.js)
- Backend: Node.js/Python FastAPI
- Database: SQLite (dev) / PostgreSQL (prod)
- Real-time: WebSocket untuk live updates
- Charts: Recharts atau lightweight charting library
- Deploy: Ready to deploy (bukan half-baked)
</task>

<task id="4" priority="high">
## TASK 4: Manual Onchain Cross-Analysis — VAPE + Life K-line

Ini BUKAN opsional. Analisis onchain secara manual untuk KEDUA token di BSC:
- Token 1 (VAPE): `0xa6b53819f5bf521945fceb1f9bbb3a7a7b4effff`
- Token 2 (人生K线 / Life K-line): `0x1a1e69f1e6182e2f8b9e8987e83c016ac9444444`

### Yang harus dicari PER TOKEN:
1. **Deployer wallet** — siapa yang deploy contract ini?
2. **Sebelum pump (saat chart flat/dead)**:
   - Siapa yang beli saat dead? List semua wallet
   - Berapa banyak yang beli vs berapa banyak yang cuma terima transfer dari dev?
   - Apakah ada bundler activity? (multiple buys di block yang sama)
3. **Saat pump dimulai**:
   - Trigger pertama: wallet mana yang mulai buy besar?
   - Volume spike pertama: berasal dari berapa wallet?
   - Apakah ada wallet baru (fresh wallet) yang tiba-tiba muncul?
4. **Puncak pump**:
   - Siapa yang jual di puncak? 
   - Apakah dev/bundler yang jual?
   - Berapa % supply yang di-dump?

### CROSS-ANALYSIS (INI YANG PALING PENTING):
5. **Wallet overlap detection**:
   - Bandingkan SEMUA early buyers VAPE vs SEMUA early buyers Life K-line
   - Cari wallet yang muncul di KEDUA token
   - Cari shared funding source (wallet yang fund early buyers di kedua token)
   - Cari bundler cluster yang sama
6. **Pattern matching**:
   - Apakah pump timing mirip? (jam berapa pump dimulai)
   - Apakah dead period mirip? (berapa lama dead sebelum pump)
   - Apakah volume pattern mirip? (spike magnitude, duration)
   - Apakah holder structure mirip? (bundler %, dev %, insider %)
7. **Grup terkoordinasi**:
   - Jika ada wallet overlap → ini BUKAN kebetulan
   - Buat profil lengkap grup ini: berapa wallet, total modal, token lain yang pernah mereka pump
   - TRACK wallet-wallet ini untuk mendeteksi pump BERIKUTNYA

### Output yang diharapkan:
Laporan lengkap dalam format structured dengan 3 bagian:
1. Analisis individual VAPE
2. Analisis individual Life K-line  
3. **Cross-analysis report** — wallet overlap, correlation score, grup profile
</task>

<constraints>
## YANG HARUS DILAKUKAN:
- Tulis code yang LANGSUNG BISA DIJALANKAN — bukan pseudocode
- Gunakan API yang real dan accessible (BSCScan, GMGN OpenAPI, atau direct RPC)
- Setiap wallet kategori harus ada bukti onchain (tx hash, block number)
- Dashboard harus responsive dan terasa seperti buatan designer profesional
- Semua task harus dieksekusi, bukan hanya direncanakan

## YANG DILARANG:
- ❌ JANGAN bilang "ini bisa ditambahkan nanti" — tambahkan SEKARANG
- ❌ JANGAN gunakan placeholder data — gunakan data real atau simulasi yang realistis
- ❌ JANGAN buat design AI slop (Inter font, purple gradient, generic cards)
- ❌ JANGAN scan wallet secara random — HARUS berdasarkan trending token CA
- ❌ JANGAN skip analisis manual VAPE token — itu contoh yang harus dikerjakan
- ❌ JANGAN puas dengan 12K wallet dan $480 PNL — target 50K+ wallet, $10K+ PNL
- ❌ JANGAN lupakan RobinHood Chain — ini BUKAN hanya BSC
- ❌ JANGAN skip gambar/screenshot yang diberikan — itu bukan dekorasi, itu DATA
</constraints>

<format>
## Struktur Response yang Diharapkan

Berikan response dalam urutan berikut:

### 1. Analisis Chart (dari 3 gambar yang diberikan)
- VAPE: dead zone vs pump zone, volume analysis
- Life K-line: dead 268 hari, pump trigger timing
- Perbandingan pattern visual kedua token

### 2. Manual Onchain Analysis — Per Token
Untuk MASING-MASING token (VAPE + Life K-line):
- Deployer identification
- Pre-pump buyers list
- Bundler cluster detection
- Smart money identification

### 3. Cross-Analysis Report (PALING PENTING)
- Wallet overlap: wallet yang muncul di KEDUA token
- Shared funding sources
- Bundler cluster correlation
- Correlation score + verdict
- Daftar wallet untuk di-monitor (next pump prediction)

### 4. Pump Wallet Analyzer Script
- Full working code (Python)
- Gunakan GMGN OpenAPI endpoints
- Jalankan pada kedua sample token
- Output JSON per token + cross-analysis

### 5. Smart Wallet Scanner Script  
- Full working code
- Trending-based logic via GMGN /v1/market/rank
- Multi-chain support (BSC + RobinHood)
- Volume interval filtering (1m, 5m, 1h, 6h, 24h)

### 6. Dashboard Web
- Complete frontend code (React + Tailwind)
- Backend API code
- Database schema
- Design tokens & style system (CSS variables, fonts)
- ANTI-SLOP design: ikuti INSTEAD rules, dark terminal aesthetic

### 7. Deployment Instructions
- How to run everything
- Environment variables needed
- API keys required
</format>

<thinking_directive>
Sebelum mulai coding, pikirkan step-by-step:
1. Apa data source yang paling reliable untuk BSC dan RobinHood?
2. Bagaimana cara paling efisien detect bundler? (hint: shared funding source + same-block buys)
3. Apa yang membedakan smart money dari lucky buyer? (hint: consistency across multiple tokens)
4. Bagaimana cara menghindari false positive di wallet classification?
5. Design approach apa yang paling cocok untuk crypto dashboard? (hint: terminal/hacker aesthetic, bukan corporate)

Tulis thinking process kamu sebelum code.
</thinking_directive>