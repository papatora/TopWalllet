"""Etherscan V2 explorer client — pengganti Blockscout untuk Robinhood Chain.

robin.etherscan.io (Etherscan V2, chainid 4663) lebih lengkap & stabil daripada
Blockscout deployment yang suka 429/changed-shape. API: https://api.etherscan.io/v2
 dengan parameter chainid=4663; WAJIB pakai ETHERSCAN_API_KEY (gratis di
etherscan.io/myapikey — 5 req/s, 100K/hari pada tier free).

Desain migrasi: client ini mengekspos METHOD YANG SAMA dengan BlockscoutClient
(address_token_transfers, token_transfers, token_holders, stats, dst.) dan
mengembalikan item berbentuk Blockscout (from.hash / token.address / total.value
/ block_number / transaction_hash) sehingga seluruh pipeline tidak perlu berubah.
Pilih client lewat make_explorer_client(): Etherscan bila API key ada, Blockscout
jadi fallback legacy (bila key belum dipasang).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from aiolimiter import AsyncLimiter

from config.settings import settings
from src.utils.logger import jlog

log = logging.getLogger("topwallet.etherscan")

# method id untuk eth_call (token metadata gratis, tanpa endpoint PRO)
SEL_DECIMALS = "0x313ce567"   # decimals()
SEL_SYMBOL = "0x95d89b41"     # symbol()
SEL_NAME = "0x06fdde03"       # name()


def tx_to_blockscout_shape(item: dict) -> dict:
    """tokentx item Etherscan -> bentuk item transfer Blockscout."""
    dec = item.get("tokenDecimal") or ""
    return {
        "from": {"hash": (item.get("from") or "").lower(), "is_contract": False},
        "to": {"hash": (item.get("to") or "").lower(), "is_contract": False},
        "token": {
            "address": (item.get("contractAddress") or "").lower(),
            "decimals": int(dec) if str(dec).isdigit() else 18,
            "symbol": item.get("tokenSymbol") or "",
            "name": item.get("tokenName") or "",
        },
        "total": {"value": str(item.get("value") or "0")},
        "block_number": int(item.get("blockNumber") or 0),
        "timestamp": item.get("timeStamp") or "",
        "transaction_hash": (item.get("hash") or "").lower(),
    }


def tx_to_funding_shape(item: dict, internal: bool = False) -> dict:
    """txlist/txlistinternal item Etherscan -> bentuk transaksi funding."""
    return {
        "from": {"hash": (item.get("from") or "").lower(), "is_contract": False,
                 "name": ""},
        "to": {"hash": (item.get("to") or "").lower(), "is_contract": False},
        "value": str(item.get("value") or "0"),
        "hash": (item.get("hash") or "").lower(),
        "block_number": int(item.get("blockNumber") or 0),
        "timestamp": int(item.get("timeStamp") or 0),
        "internal": internal,
    }


def decode_abi_string(hexstr: str) -> str:
    """Decode return eth_call bertipe string: 0x + offset + len + data."""
    try:
        data = hexstr[2:] if hexstr.startswith("0x") else hexstr
        if len(data) < 128:
            return ""
        length = int(data[64:128], 16)
        raw = bytes.fromhex(data[128:128 + length * 2])
        return raw.decode("utf-8", errors="replace")
    except (ValueError, IndexError):
        return ""


def decode_abi_uint(hexstr: str) -> int | None:
    try:
        data = hexstr[2:] if hexstr.startswith("0x") else hexstr
        return int(data[:64], 16) if len(data) >= 64 else None
    except (ValueError, IndexError):
        return None


class EtherscanV2Client:
    """Client API Etherscan V2 dengan bentuk keluaran Blockscout-compatible."""

    def __init__(self, api_key: str | None = None, chain_id: int | None = None,
                 rps: float | None = None):
        # dukung multi-key "KEY1,KEY2" → rotasi round-robin (2 key = 2x limit)
        raw = (api_key or settings.etherscan_api_key or "").strip()
        self.api_keys = [k.strip() for k in raw.split(",") if k.strip()]
        self._key_idx = 0
        self.chain_id = chain_id or settings.chain_id
        self.base_api = "https://api.etherscan.io/v2/api"
        self.base = settings.explorer_url.rstrip("/")  # untuk link /tx/ /address/
        self._limiter = AsyncLimiter(max(rps or settings.etherscan_rps, 0.1), 1.0)
        self._client: httpx.AsyncClient | None = None
        if not self.api_keys:
            jlog(log, logging.WARNING,
                 "ETHERSCAN_API_KEY kosong — request akan ditolak API; "
                 "isi .env lalu restart, fallback Blockscout dipakai sementara")
        else:
            jlog(log, logging.INFO, "etherscan aktif",
                 keys=len(self.api_keys), chain_id=self.chain_id)

    def _key(self) -> str:
        """Key berikutnya (round-robin); rate-limit memanggil _rotate()."""
        k = self.api_keys[self._key_idx % len(self.api_keys)]
        self._key_idx += 1
        return k

    def _rotate(self) -> None:
        """Lompat ke key berikutnya segera (dipanggil saat kena limit)."""
        if len(self.api_keys) > 1:
            self._key_idx += 1

    @property
    def is_etherscan(self) -> bool:
        return True

    @property
    def is_degraded(self) -> bool:
        # pnl_verifier membaca atribut ini dari client apa pun (Blockscout
        # punya; Etherscan tidak punya konsep degraded) — dulu AttributeError
        # mematikan track-ca di tahap analyze.
        return False

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _call(self, params: dict, retries: int = 6) -> dict | list | None:
        """Satu panggilan API dengan anti-skip: rate-limit/NOTOK di-retry
        backoff; 'No transactions found' → list kosong (bukan error)."""
        client = await self._http()
        params = {"chainid": self.chain_id, "apikey": self._key(), **params}
        last_err = ""
        for attempt in range(retries):
            try:
                async with self._limiter:
                    resp = await client.get(self.base_api, params=params)
                if resp.status_code == 429:
                    last_err = "http 429"
                    self._rotate()
                    await asyncio.sleep(min(60.0, 2.0 * (2 ** attempt)))
                    continue
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == "0":
                    msg = (data.get("message") or "") + " " + str(data.get("result") or "")
                    if "No transactions found" in msg:
                        return []
                    last_err = msg[:120]
                    # Missing/invalid key → percuma di-retry
                    if "Missing/Invalid API Key" in msg:
                        jlog(log, logging.ERROR, "etherscan key ditolak — "
                             "cek ETHERSCAN_API_KEY di .env")
                        return None
                    # rate limit per key → rotasi + backoff singkat
                    if "rate limit" in msg.lower() or "max calls" in msg.lower():
                        self._rotate()
                        await asyncio.sleep(min(15.0, 1.0 + attempt))
                        continue
                    await asyncio.sleep(min(60.0, 2.0 * (2 ** attempt)))
                    continue
                return data
            except (httpx.HTTPError, ValueError) as e:
                last_err = str(e)[:120]
                await asyncio.sleep(min(60.0, 2.0 * (2 ** attempt)))
        jlog(log, logging.WARNING, "etherscan call gagal setelah retry",
             params=str(params.get("action")), err=last_err)
        return None

    # ---------------- transfers (bentuk Blockscout) ----------------

    async def address_token_transfers(self, wallet: str, max_pages: int,
                                      token_filter: str | None = None,
                                      sort: str = "asc") -> list[dict]:
        """Riwayat ERC-20 transfer wallet (opsional difilter 1 token).
        sort=asc menjangkau histori TERLAMA dalam cap 10K baris API."""
        items: list[dict] = []
        for page in range(1, max_pages + 1):
            params = {"module": "account", "action": "tokentx",
                      "address": wallet.lower(), "page": page,
                      "offset": 200, "sort": sort}
            if token_filter:
                params["contractaddress"] = token_filter.lower()
            data = await self._call(params)
            if not isinstance(data, list):
                break
            items.extend(tx_to_blockscout_shape(x) for x in data)
            if len(data) < 200:
                break
        return items

    async def address_transactions(self, wallet: str, max_pages: int) -> list[dict]:
        """Tx native-ETH masuk/keluar (txlist + internal) — terlama dulu.
        Untuk funding provenance: incoming pertama = funding pertama."""
        out: list[dict] = []
        for action, internal in (("txlist", False), ("txlistinternal", True)):
            for page in range(1, max_pages + 1):
                params = {"module": "account", "action": action,
                          "address": wallet.lower(), "page": page,
                          "offset": 200, "sort": "asc",
                          "startblock": 0, "endblock": 99999999}
                data = await self._call(params)
                if not isinstance(data, list):
                    break
                out.extend(tx_to_funding_shape(x, internal) for x in data)
                if len(data) < 200:
                    break
        out.sort(key=lambda x: x["block_number"])
        return out

    async def token_transfers(self, ca: str, max_pages: int) -> list[dict]:
        """Semua transfer sebuah token (discovery trader)."""
        items: list[dict] = []
        for page in range(1, max_pages + 1):
            data = await self._call({"module": "account", "action": "tokentx",
                                     "contractaddress": ca.lower(), "page": page,
                                     "offset": 200, "sort": "desc"})
            if not isinstance(data, list):
                break
            items.extend(tx_to_blockscout_shape(x) for x in data)
            if len(data) < 200:
                break
        return items

    async def token_holders(self, ca: str, max_items: int) -> list[dict]:
        """Tier free Etherscan tidak membuka tokenholderlist (PRO) —
        derivasi dari trader aktif token (address unik di transfer terbaru).
        Secara semantik: kandidat wallet dari AKTIVITAS, bukan posisi diam."""
        items = await self.token_transfers(ca, max_pages=max(1, max_items // 100))
        seen: dict[str, dict] = {}
        for it in items:
            for side in ("from", "to"):
                a = (it.get(side) or {}).get("hash") or ""
                if a and a not in seen and a != "0x" + "0" * 40:
                    seen[a] = {"address": a, "source": "trader",
                               "is_contract": False}
            if len(seen) >= max_items:
                break
        return list(seen.values())[:max_items]

    # ---------------- metadata ----------------

    async def token_info(self, ca: str) -> dict:
        """decimals/symbol/name via eth_call proxy (free tier)."""
        client = await self._http()
        info: dict[str, Any] = {"address": ca.lower()}

        async def call(data_sel: str) -> str:
            # eth_call di luar _call() — retry sendiri: ReadTimeout di sini
            # dulu membunuh seluruh cycle pipeline (prices/analyze mati di
            # tengah jalan, supervisor restart bolak-balik).
            last_err = ""
            for attempt in range(4):
                try:
                    async with self._limiter:
                        resp = await client.get(self.base_api, params={
                            "chainid": self.chain_id, "apikey": self._key(),
                            "module": "proxy", "action": "eth_call",
                            "to": ca.lower(), "data": data_sel})
                    try:
                        r = resp.json()
                        return (r.get("result") or "") if isinstance(r, dict) else ""
                    except ValueError:
                        return ""
                except httpx.HTTPError as e:
                    last_err = str(e)[:100]
                    await asyncio.sleep(min(20.0, 1.5 * (2 ** attempt)))
            jlog(log, logging.WARNING, "eth_call metadata gagal setelah retry",
                 token=ca, err=last_err)
            return ""

        dec_hex, sym_hex = await asyncio.gather(call(SEL_DECIMALS), call(SEL_SYMBOL))
        n = decode_abi_uint(dec_hex)
        if n is not None and 0 <= n <= 36:
            info["decimals"] = str(n)
        sym = decode_abi_string(sym_hex)
        if sym:
            info["symbol"] = sym
            info["name"] = sym
        return info

    async def chain_tokens(self, max_pages: int = 8) -> list[dict]:
        """Tidak ada endpoint 'semua token' di Etherscan — discovery memakai
        DexScreener + GMGN trending (sudah berjalan)."""
        return []

    async def stats(self) -> dict:
        """Harga native coin (ETH) — bentuk sama dgn Blockscout: coin_price."""
        data = await self._call({"module": "stats", "action": "ethprice"})
        try:
            usd = float((data or {}).get("result", {}).get("ethusd"))
            return {"coin_price": usd}
        except (TypeError, ValueError, AttributeError):
            return {}

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def make_explorer_client(rps: float | None = None):
    """Factory explorer: Etherscan V2 bila ETHERSCAN_API_KEY terpasang,
    Blockscout legacy sebagai fallback (sampah tapi masih jalan)."""
    if settings.etherscan_api_key:
        from src.utils.etherscan_client import EtherscanV2Client

        n_keys = len([k for k in settings.etherscan_api_key.split(",") if k.strip()])
        return EtherscanV2Client(rps=(rps or settings.etherscan_rps) * max(n_keys, 1))
    logging.getLogger("topwallet.etherscan").warning(
        "ETHERSCAN_API_KEY belum di-set — memakai Blockscout fallback "
        "(robin.etherscan.io jauh lebih stabil; daftar gratis di "
        "etherscan.io/myapikey lalu isi .env)")
    from src.discover.holder_scraper import BlockscoutClient

    return BlockscoutClient(rps=rps)
