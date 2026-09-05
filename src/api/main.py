"""FastAPI dashboard backend (optional service in docker-compose).

  GET /health
  GET /api/v1/top-wallets?limit=100
  GET /api/v1/stats
  GET /api/v1/track-by-ca?ca=0x...&top=50
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from config.settings import settings

app = FastAPI(title="TopWallet API", version="0.1.0")


def _results() -> Path:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    return settings.results_dir


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "chain": settings.chain, "chain_id": settings.chain_id}


@app.get("/api/v1/top-wallets")
async def top_wallets(limit: int = Query(100, ge=1, le=1000)) -> dict:
    path = _results() / "top_wallets_latest.json"
    if not path.exists():
        raise HTTPException(404, "no results yet — run the pipeline first")
    data = json.loads(path.read_text())
    data["wallets"] = data.get("wallets", [])[:limit]
    return data


@app.get("/api/v1/stats")
async def stats() -> dict:
    path = _results() / "stats.json"
    if not path.exists():
        raise HTTPException(404, "no stats yet — run the pipeline first")
    return json.loads(path.read_text())


@app.get("/api/v1/track-by-ca")
async def track_by_ca(ca: str, top: int = Query(50, ge=1, le=500)) -> dict:
    ca = ca.strip().lower()
    if not ca.startswith("0x") or len(ca) != 42:
        raise HTTPException(400, "ca must be a 42-char contract address")
    cached = _results() / "by_ca" / f"{ca}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    from src.track_by_ca import run_track_by_ca

    result = await run_track_by_ca(ca, top_n=top)
    if result is None:
        raise HTTPException(404, f"no DEX pair or transfers found for {ca}")
    return result
