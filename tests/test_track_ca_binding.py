"""Regression pins for the track-by-CA ↔ Pipeline integration.

The P0 class this guards: run_track_by_ca calling a Pipeline method that
does not exist (stage_enrich_for lived only in someone's head — discovered
by debate Round B AFTER deploy). Parse the source and assert every
`helper.<method>(...)` call exists on Pipeline.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def test_track_ca_helper_methods_exist_on_pipeline():
    from src.pipeline import Pipeline
    from src.track_by_ca import run_track_by_ca  # import proves module loads

    src = (REPO / "src" / "track_by_ca.py").read_text(encoding="utf-8")
    calls = set(re.findall(r"helper\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", src))
    assert calls, "guard itself broken: no helper.* calls found in source"
    missing = [m for m in sorted(calls) if not hasattr(Pipeline, m)]
    assert not missing, (
        f"run_track_by_ca memanggil method Pipeline yang TIDAK ADA: {missing} "
        "(crash setelah kerja discovery+pricing mahal)")


def test_analyze_wallets_has_offswitch_params():
    """track-by-CA must be able to avoid wiping global exports/scores."""
    import inspect

    from src.pipeline import Pipeline

    sig = inspect.signature(Pipeline.analyze_wallets)
    for p in ("do_export", "do_push", "persist_replace"):
        assert p in sig.parameters, f"analyze_wallets kehilangan param {p}"


def test_sweep_bleed_trough_repin():
    """Long bleed with a single >=30% leg may re-fire once per collapse,
    but NEVER twice within one collapse (anchor ratchets)."""
    from scripts.volume_sweep import TagState

    t = TagState()
    t.commit("k", 400_000, 0)
    fires = 0
    vol = 400_000.0
    for i, factor in enumerate([0.95, 0.60, 0.58, 0.57, 0.56, 0.55, 0.54]):
        vol *= factor
        if t.evaluate("k", vol, i + 1) is not None:
            fires += 1
            t.commit("k", vol, i + 1)
    assert fires <= 2  # collapse legs may re-fire, but not every leg
