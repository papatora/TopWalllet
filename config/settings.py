"""Central configuration for TopWallet.

Every tunable is either an environment variable (see .env.example) or lives in
config/scoring_weights.json. Nothing is hardcoded at call sites, so the whole
pipeline can be re-tuned without code changes.

Primary chain: Robinhood Chain (EVM L2, Arbitrum-Orbit stack, chain id 4663).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

# --- Public contract addresses on Robinhood Chain (not secrets) ---
USDG_ADDRESS = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"
WETH_ADDRESS = "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73"
NATIVE_ETH = "0x0000000000000000000000000000000000000000"
DEFAULT_POOL_MANAGER = "0x8366a39CC670B4001A1121B8F6A443A643e40951"

# Quote tokens treated as $1 stables (position USD math assumes these ≈ $1)
STABLE_SYMBOLS = {"USDG", "USDC", "USDT", "USDG+", "RLUSD", "FDUSD"}


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, "").strip() or default)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(float(os.getenv(key, "").strip() or default))
    except ValueError:
        return default


@dataclass
class Settings:
    # chain / network
    chain: str = os.getenv("CHAIN", "robinhood")
    chain_id: int = _env_int("CHAIN_ID", 4663)
    evm_rpc_endpoints: list[str] = field(default_factory=list)
    rpc_rps: float = _env_float("RPC_RPS", 3.0)
    blockscout_url: str = os.getenv("BLOCKSCOUT_API_URL", "https://robinhoodchain.blockscout.com")
    blockscout_rps: float = _env_float("BLOCKSCOUT_RPS", 8.0)

    # contracts
    pool_manager: str = os.getenv("UNISWAP_V4_POOL_MANAGER", DEFAULT_POOL_MANAGER).lower()
    weth_address: str = os.getenv("WETH_ADDRESS", WETH_ADDRESS).lower()
    usdg_address: str = os.getenv("USDG_ADDRESS", USDG_ADDRESS).lower()

    # discovery
    discovery_queries: list[str] = field(default_factory=lambda: [
        q.strip() for q in os.getenv("DISCOVERY_QUERIES", "USDG,ETH,WETH,robinhood").split(",") if q.strip()
    ])
    dexscreener_search_rpm: float = _env_float("DEXSCREENER_SEARCH_RPM", 240)
    dexscreener_profiles_rpm: float = _env_float("DEXSCREENER_PROFILES_RPM", 55)
    min_liquidity_usd: float = _env_float("MIN_LIQUIDITY_USD", 5000)
    min_volume_24h_usd: float = _env_float("MIN_VOLUME_24H_USD", 3000)
    max_tokens: int = _env_int("MAX_TOKENS", 200)
    max_wallets: int = _env_int("MAX_WALLETS", 20000)
    holders_per_token: int = _env_int("HOLDERS_PER_TOKEN", 25)
    trader_pages_per_token: int = _env_int("TRADER_PAGES_PER_TOKEN", 2)
    enable_gmgn: bool = _env_bool("ENABLE_GMGN", False)

    # enrichment
    enrich_concurrency: int = _env_int("ENRICH_CONCURRENCY", 3)
    enrich_max_pages_per_wallet: int = _env_int("ENRICH_MAX_PAGES_PER_WALLET", 6)
    enrich_limit_per_run: int = _env_int("ENRICH_LIMIT_PER_RUN", 0)
    lookback_days: int = _env_int("LOOKBACK_DAYS", 70)
    price_lookback_days: int = _env_int("PRICE_LOOKBACK_DAYS", 70)
    getlogs_start_window: int = _env_int("GETLOGS_START_WINDOW", 2_000_000)
    # light safety margin below the chain tip for log queries (tip reorgs /
    # indexer catch-up); the real index on public RPC is much fresher
    safe_log_lag_blocks: int = _env_int("SAFE_LOG_LAG_BLOCKS", 50_000)
    price_max_logs_per_pool: int = _env_int("PRICE_MAX_LOGS_PER_POOL", 60000)
    dip_window_days: int = _env_int("DIP_WINDOW_DAYS", 7)

    # analysis thresholds
    min_positions: int = _env_int("MIN_POSITIONS", 5)
    min_distinct_tokens: int = _env_int("MIN_DISTINCT_TOKENS", 3)
    dip_percentile: float = _env_float("DIP_PERCENTILE", 0.2)
    top_percentile: float = _env_float("TOP_PERCENTILE", 0.8)
    unrealized_big_multiple: float = _env_float("UNREALIZED_BIG_MULTIPLE", 5.0)

    # infra / plumbing
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/topwallet.db")
    proxy_urls_file: str = os.getenv("PROXY_URLS_FILE", "")
    results_dir: Path = REPO_ROOT / "results"
    logs_dir: Path = REPO_ROOT / "logs"
    weights_path: Path = REPO_ROOT / "config" / "scoring_weights.json"

    # github
    github_repo: str = os.getenv("GITHUB_REPO", "papatora/TopWalllet")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_branch: str = os.getenv("GITHUB_BRANCH", "main")
    auto_push_results: bool = _env_bool("AUTO_PUSH_RESULTS", False)

    # scheduler / monitor
    pipeline_cron: str = os.getenv("PIPELINE_CRON", "0 3 * * 0")
    monitor_interval_seconds: int = _env_int("MONITOR_INTERVAL_SECONDS", 30)
    enable_monitor: bool = _env_bool("ENABLE_MONITOR", False)
    top_wallets_for_monitor: int = _env_int("TOP_WALLETS_FOR_MONITOR", 100)

    # alerts
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # HTTP proxies loaded from file (one per line) — optional, for scraping resilience
    proxy_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        endpoints = os.getenv(
            "EVM_RPC_ENDPOINTS", "https://rpc.mainnet.chain.robinhood.com"
        )
        self.evm_rpc_endpoints = [e.strip() for e in endpoints.split(",") if e.strip()]
        self.pool_manager = self.pool_manager.lower()
        self.weth_address = self.weth_address.lower()
        self.usdg_address = self.usdg_address.lower()
        if self.proxy_urls_file:
            p = Path(self.proxy_urls_file)
            if p.exists():
                lines = [ln.strip() for ln in p.read_text().splitlines() if ln.strip()]
                # accept ip:port:user:pass (webshare style) or full URL lines
                for ln in lines:
                    if "://" in ln:
                        self.proxy_urls.append(ln)
                    elif ln.count(":") == 3:
                        host, port, user, pwd = ln.split(":")
                        self.proxy_urls.append(f"http://{user}:{pwd}@{host}:{port}")

    def load_weights(self) -> dict:
        with open(self.weights_path, "r", encoding="utf-8") as f:
            return json.load(f)


settings = Settings()
