"""Smart Money Feed data layer — milestone M1 (docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md).

FeedEvent persistence with deterministic ids, signal typing per taxonomy §6.3,
an idempotent backfill from existing swap history, and the freshness bands of
§6.9. The API (M2) and the live block follower (M5) build on this module.
"""
from src.feed.events import backfill, build_ranked_lookup, freshness_band, make_event_id

__all__ = ["backfill", "build_ranked_lookup", "freshness_band", "make_event_id"]
