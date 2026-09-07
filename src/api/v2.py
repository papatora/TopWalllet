"""API v2 — Smart Money Feed endpoints (spec docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md §8.1).

Additive to v1. Every response carries generated_at + data_age_seconds.
Cursor-based pagination (never offset). Read-only over the pipeline DB.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, text

from config.settings import settings
from src.db.models import FeedEvent

router = APIRouter(prefix="/api/v2")

RATE = {"count": 0, "window": 0.0}


def _rate_limit(request: Request) -> None:
    """Token bucket: 120 req/min per process (single-IP deploy behind proxy)."""
    now = time.time()
    if now - RATE["window"] >= 60:
        RATE["window"] = now
        RATE["count"] = 0
    RATE["count"] += 1
    if RATE["count"] > 120:
        raise HTTPException(429, detail={"error": {"code": "RATE_LIMITED",
                              "message": "60 req/min per IP", "hint": "retry in 60s"}})


def _validate_ca(ca: str) -> str:
    ca = ca.strip().lower()
    if not (ca.startswith("0x") and len(ca) == 42 and all(ch in "0123456789abcdef" for ch in ca[2:])):
        raise HTTPException(400, detail={"error": {"code": "BAD_CA",
                              "message": "ca must be 0x + 40 hex chars", "hint": "check the address"}})
    return ca


def _results() -> Path:
    p = settings.results_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(name: str):
    path = _results() / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _data_age(stats: dict | None) -> int:
    if not stats:
        return -1
    try:
        ts = datetime.fromisoformat(stats["updated_at"])
        return int((datetime.now(timezone.utc) - ts).total_seconds())
    except (KeyError, ValueError):
        return -1


def _envelope(request: Request, payload: dict, stats: dict | None) -> dict:
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["data_age_seconds"] = _data_age(stats)
    return payload


def _thresholds() -> dict:
    try:
        cfg = json.loads((Path(settings.weights_path)).read_text())
        return cfg.get("thresholds", {})
    except (OSError, json.JSONDecodeError):
        return {}


@router.get("/feed")
async def feed(request: Request, cursor: str | None = None, limit: int = Query(50, ge=1, le=200),
               types: str | None = None, token: str | None = None, wallet: str | None = None):
    _rate_limit(request)
    from src.db.database import get_session_factory

    stats = _load_json("stats.json")
    async with get_session_factory()() as session:
        q = "SELECT id, payload FROM feed_events"
        conds, params = [], {"limit": limit}
        if cursor:
            try:
                ts_str, last_id = cursor.split("|", 1)
                ts_dt = datetime.fromisoformat(ts_str)
                conds.append("(ts < :c_ts OR (ts = :c_ts AND id < :c_id))")
                params.update({"c_ts": ts_dt, "c_id": last_id})
            except ValueError:
                raise HTTPException(400, detail={"error": {"code": "BAD_CURSOR",
                                      "message": "cursor must be '<iso_ts>|<event_id>'", "hint": "use next_cursor"}})
        if types:
            tl = [t.strip().upper() for t in types.split(",") if t.strip()]
            if tl:
                ph = ",".join(f":t{i}" for i in range(len(tl)))
                conds.append(f"type IN ({ph})")
                params.update({f"t{i}": t for i, t in enumerate(tl)})
        if token:
            conds.append("token_address = :tok")
            params["tok"] = token.strip().lower()
        if wallet:
            conds.append("wallet_address = :wal")
            params["wal"] = wallet.strip().lower()
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY ts DESC, id DESC LIMIT :limit"
        rows = (await session.execute(text(q), params)).all()

    events = [json.loads(r.payload) for r in rows]
    next_cursor = f"{rows[-1][0].split('_')[0]}|{rows[-1][0]}" if rows and len(rows) == limit else None
    # cursor needs the ts, not the id parts — re-derive from payload
    if next_cursor and events:
        next_cursor = f"{events[-1]['ts']}|{rows[-1][0]}"
    return _envelope(request, {"events": events, "next_cursor": next_cursor,
                               "thresholds_in_force": _thresholds()}, stats)


@router.get("/stream")
async def stream(request: Request, since: str | None = None):
    _rate_limit(request)
    from src.db.database import get_session_factory

    async def gen():
        last_id = since or ""
        while True:
            if await request.is_disconnected():
                break
            async with get_session_factory()() as session:
                q = "SELECT id, payload FROM feed_events"
                if last_id:
                    q += " WHERE id > :lid"
                q += " ORDER BY id DESC LIMIT 20"
                params = {"lid": last_id} if last_id else {}
                rows = (await session.execute(text(q), params)).all()
            for rid, payload in rows:
                last_id = rid
                yield f"id: {rid}\ndata: {payload}\n\n"
            if not rows:
                yield ": keepalive\n\n"
            await asyncio.sleep(5)

    import asyncio
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/wallets")
async def wallets(request: Request, limit: int = Query(100, ge=1, le=500)):
    _rate_limit(request)
    data = _load_json("top_wallets_latest.json")
    if not data:
        raise HTTPException(404, detail={"error": {"code": "NO_DATA",
                              "message": "pipeline has not produced results yet",
                              "hint": "run the pipeline on the VPS"}})
    return _envelope(request, {"wallets": data.get("wallets", [])[:limit],
                               "total": data.get("total_ranked", 0),
                               "thresholds_in_force": _thresholds()},
                     _load_json("stats.json"))


@router.get("/wallet/{address}")
async def wallet_dossier(request: Request, address: str):
    ca = _validate_ca(address)
    _rate_limit(request)
    dossier = _load_json(f"wallet_details/{ca[:20]}.json")
    if not dossier:
        data = _load_json("top_wallets_latest.json")
        match = next((w for w in (data or {}).get("wallets", [])
                      if w["wallet_address"].lower() == ca), None)
        if not match:
            raise HTTPException(404, detail={"error": {"code": "NOT_FOUND",
                                  "message": "wallet not in verified set", "hint": "it may exist on-chain but failed verification"}})
        dossier = match
    labels = _load_json("wallet_labels.json")
    if labels:
        dossier["labels"] = labels.get("wallets", {}).get(ca)
    funding = _load_json("funding_forensics.json")
    if funding:
        dossier["funding"] = next((w for w in funding.get("wallets", [])
                                   if w["wallet"].lower() == ca), None)
    return _envelope(request, dossier, _load_json("stats.json"))


@router.get("/token/{ca}/whale-map")
async def whale_map(request: Request, ca: str):
    ca = _validate_ca(ca)
    _rate_limit(request)
    maps = _load_json("whale_entry_maps.json")
    m = (maps or {}).get("maps", {}).get(ca.lower())
    if not m:
        raise HTTPException(404, detail={"error": {"code": "NO_WHALE_MAP",
                              "message": "no whale entry map for this token",
                              "hint": "map builds during analyze when the token has trades"}})
    return _envelope(request, {"ca": ca, **m}, _load_json("stats.json"))


@router.get("/clusters")
async def clusters(request: Request):
    _rate_limit(request)
    data = _load_json("funder_clusters.json")
    if not data:
        raise HTTPException(404, detail={"error": {"code": "NO_CLUSTERS",
                              "message": "no funder clusters captured yet"}})
    return _envelope(request, data, _load_json("stats.json"))


@router.get("/status")
async def status(request: Request):
    _rate_limit(request)
    stats = _load_json("stats.json") or {}
    return _envelope(request, {
        "last_pipeline_run": stats.get("updated_at"),
        "supervisor": _load_json("supervisor_status.json"),
        "thresholds_in_force": _thresholds(),
        "wallets_scored": stats.get("stage_counts", {}).get("wallets_scored"),
        "wallets_excluded": stats.get("stage_counts", {}).get("wallets_excluded"),
        "verified_count": stats.get("top_wallets_count"),
        "stage_counts": stats.get("stage_counts"),
    }, stats)


@router.get("/methodology")
async def methodology(request: Request):
    _rate_limit(request)
    try:
        cfg = json.loads(Path(settings.weights_path).read_text())
    except (OSError, json.JSONDecodeError):
        cfg = {}
    return _envelope(request, {
        "weights": cfg.get("weights", {}),
        "normalization": cfg.get("normalization", {}),
        "thresholds": cfg.get("thresholds", {}),
        "verifier_rules": {
            "R1": "ETH price cross-checked vs most liquid WETH/USDG pool (<=2% deviation)",
            "R2": "top-3 trades re-derived from raw Blockscout legs; >=2/3 must match within 25%",
            "R3": "no unrealized claims resting on price points older than 24h",
        },
        "caveats": ["chain is young (~2 months) — samples are early",
                    "single-token wallets are flagged SINGLE_TOKEN_SAMPLE",
                    "past performance predicts nothing"],
    }, None)
