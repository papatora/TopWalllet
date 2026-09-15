// Guide — cara membaca data TopWallet.
import { esc } from '../lib/fmt.js';
import { chip, labelMeta } from '../lib/ui.js';
import { S } from '../lib/store.js';

const $ = s => document.querySelector(s);

const sec = (title, body) => `<section class="panel" style="margin-bottom:16px"><div class="panel-b">
  <h2 style="font-size:15px;font-weight:600;margin-bottom:10px">${title}</h2>
  <div class="t2" style="line-height:1.75">${body}</div></div></section>`;

const row = (k, v) => `<div class="kv-row"><span>${k}</span><span>${v}</span></div>`;

export function render() {
  const allLabels = [
    ['GENERALIST', 'Wallet trader biasa — tidak ada sinyal khusus. Mayoritas wallet masuk sini.'],
    ['INSIDER', 'Terbukti on-chain MENERIMA token tanpa membelinya (transfer murni / mint, tanpa Swap log di transaksi). Blok INDUKAN menunjukkan dari siapa token itu berasal. Sub-jenis: MINT (dari 0x0 — alokasi dev), CLUSTER (dari funder armada), TRANSFER (dari wallet personal - OTC/hibah?).'],
    ['TRADER_COVERAGE_GAP', 'Pernah salah dilabel insider — ternyata dia BENAR membeli (ada Swap log) tapi transaksi belinya tidak tertangkap scan lama. Menunggu re-enrich.'],
    ['SNIPER', 'Pembeli pertama ≤10 blok sejak swap pertama pool. Mengambil posisi di detik-detik awal kelahiran token.'],
    ['BUNDLER_SUSPECT', 'Beli di transaksi yang sama dengan ≥5 wallet lain di blok pertama pool — pola bundle launch.'],
    ['AIRDROP_FARMER', 'Hampir semua aktivitasnya menerima token, tidak pernah membeli — kolektor airdrop/dust.'],
    ['PHISHING_TARGET', 'Menerima token dari mass-spreader (pengirim menyebar ke ≥20 wallet dalam ≤100 blok) — kampanye sebaran/scam. Bukan insider.'],
    ['DEV', 'Pembeli pertama ≤300 blok sejak pool lahir lalu flip cepat — pola dev/alokasi launch.'],
    ['CT_ATTRIBUTED', 'Terhubung ke akun Crypto Twitter yang dikenal (attribusi bisa berubah).'],
    ['MEV_BOT', 'Median hold ≤10 menit, ≥30 round-trip — pola sandwich/arbitrase bot.'],
    ['BOT', 'Pola eksekusi mesin: swap tiap beberapa detik nonstop di banyak token acak. (baru — dari pola timing swap)'],
    ['SNIPER_BOT', 'BOT yang spesialis menyidam token baru di blok paling awal di BANYAK token berbeda.'],
    ['WHALE', 'Modal organik besar: PnL est. ≥$100K, tanpa hubungan airdrop/insider/cluster — wealth murni dari trading.'],
    ['WHALE_SUS', 'PnL est. tinggi TAPI terhubung ke something (airdrop/insider/cluster) — kekayaan bisa turunan alokasi, bukan murni skill.'],
    ['CLUSTER_MEMBER:*', 'Dana pertamanya dari funder yang sama dengan ≥3 wallet lain — anggota armada. Klik untuk melihat indukan.'],
    ['SMART_TRACKER', 'Lolos verifikasi PnL keras (R1 oracle, R2 re-derivasi, R3 cek posisi basi).'],
  ];
  const chips = S.labels.map(l => {
    const meta = labelMeta(l) || {};
    const d = allLabels.find(x => x[0] === l || l.startsWith(x[0].split(':')[0]));
    return `<div class="panel" style="padding:12px 14px;margin-bottom:10px">
      <div style="margin-bottom:6px">${chip(l)}</div>
      <div class="t2" style="font-size:12.5px;line-height:1.6">${esc(d ? d[1] : meta.desc || '')}</div></div>`;
  }).join('');

  $('#app').innerHTML = `<div class="page">
    <h1 class="page-title">Guide — cara baca data</h1>
    <p class="t2" style="margin-bottom:18px">Semua angka USD di explorer ini adalah <b>estimasi</b> dari harga pool saat swap (ditandai "est."). Bukan PnL terverifikasi — PnL terverifikasi hanya muncul setelah tahap analyze berjalan penuh (chips "verifier").</p>

    ${sec('Cara baca Visualizer', `
      <b>Ukuran bubble</b> = volume est. yang lewat di wallet/token itu dalam scope aktif.
      <b>Garis</b> = arah aliran dana (klik FLOW untuk ganti All/In/Out).
      <b>Warna</b> = cluster (Group clusters) atau label.
      <div style="margin-top:10px">
      ${row('Node kotak/kubus besar (DEX pool)', 'Pool kontrak — wajar volumenya menarik ke mana-mana karena SEMUA swap lewat dia. Bukan aktivitas mencurigakan. Sembunyikan lewat LAYERS → DEX pools kalau mau fokus antar-wallet.')}
      ${row('Bundle tx', 'Satu transaksi launch yang berisi beli dari banyak wallet sekaligus — indikasi koordinasi.')}
      ${row('Funder', 'Sumber dana pertama yang dipakai banyak wallet (indukan armada).')}
      ${row(' klik / double-click', 'klik = pilih & lihat kartu detail (termasuk INDUKAN untuk insider) · double-click = buka profil wallet · drag = pin posisi')}
      </div>`)}
    ${sec('Membaca INDUKAN (asal token insider)', `
      Kalau wallet punya label insider terverifikasi, kartu node & halaman profil menampilkan <b>INDUKAN — ASAL TOKEN</b>: dari wallet siapa token itu diterima, jenisnya (mint dev / cluster / transfer personal), dan pola sebaran pengirimnya (mis. "mass-spreader 30 wallet/≤100 blok"). Itu menjawab "wallet ini di-induki siapa".`)}
    ${sec('Glosarium label', chips)}
    ${sec('Skala keyakinan', `
      ${row('on-chain PROVEN', 'Diverifikasi langsung ke transaksi (receipt/log) — tertinggi')}
      ${row('verifier R1-R3', 'PnL lolos oracle + re-derivasi + cek posisi basi')}
      ${row('est. / preliminary', 'Estimasi dari harga pool — angka bisa bergeser setelah analyze penuh')}
      ${row('attribusi', 'Dari sumber eksternal (GMGN/CT) — selalu cek ulang')}`)}
  </div>`;
}
