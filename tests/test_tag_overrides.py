"""tag_overrides — on-chain verification verdicts must survive re-classification.

Landmine being pinned: the classifier derives INSIDER from LOCAL swap_events
only ("sells a token it never bought"). A scan-coverage hole produces false
INSIDERs. scripts/reverify_tags.py checks on-chain and writes overrides; the
pipeline must re-apply them after every classification pass.
"""
from __future__ import annotations

from src.analyze.tag_overrides import apply_overrides


def _labels_payload() -> dict:
    return {
        "wallets": {
            "0xaaa": {
                "primary_type": "INSIDER",
                "labels": ["INSIDER"],
                "evidence": {"INSIDER": {"tokens": ["0xtoken"]}},
                "confidence": {"INSIDER": 0.6},
            },
            "0xbbb": {
                "primary_type": "INSIDER",
                "labels": ["INSIDER"],
                "evidence": {"INSIDER": {"tokens": ["0xtok2"]}},
                "confidence": {"INSIDER": 0.6},
            },
            "0xccc": {"primary_type": "GENERALIST", "labels": ["GENERALIST"],
                      "evidence": {}, "confidence": {}},
        }
    }


def test_override_demotes_false_insider():
    payload = _labels_payload()
    overrides = {"0xaaa": {
        "set_primary": "TRADER_COVERAGE_GAP",
        "remove_labels": ["INSIDER"],
        "add_labels": ["TRADER_COVERAGE_GAP"],
        "confidence": {"TRADER_COVERAGE_GAP": 0.85},
        "evidence": {"TRADER_COVERAGE_GAP": {"proof_txs": ["0xdeadbeef"]}},
        "note": "swap log found in transfer tx",
    }}
    out, changed = apply_overrides(payload, overrides)
    assert changed == 1
    w = out["wallets"]["0xaaa"]
    assert w["primary_type"] == "TRADER_COVERAGE_GAP"
    assert "INSIDER" not in w["labels"]
    assert "TRADER_COVERAGE_GAP" in w["labels"]
    ev = w["evidence"]["TRADER_COVERAGE_GAP"]
    assert ev["onchain_verified"] is True
    assert ev["verified_at"]


def test_override_confirms_real_insider():
    payload = _labels_payload()
    overrides = {"0xbbb": {
        "set_primary": "INSIDER",
        "remove_labels": ["INSIDER"],
        "add_labels": ["INSIDER"],
        "confidence": {"INSIDER": 0.95},
        "evidence": {"INSIDER": {"kind": "MINT_ALLOCATION"}},
        "note": "mint transfer from 0x0, no swap log",
    }}
    out, changed = apply_overrides(payload, overrides)
    assert changed == 1
    w = out["wallets"]["0xbbb"]
    assert w["primary_type"] == "INSIDER"
    assert w["confidence"]["INSIDER"] == 0.95
    assert w["evidence"]["INSIDER"]["kind"] == "MINT_ALLOCATION"


def test_override_ignores_unknown_wallet_and_empty_overrides():
    payload = _labels_payload()
    out, changed = apply_overrides(payload, {"0xzzz": {"set_primary": "DEV"}})
    assert changed == 0
    assert out["wallets"]["0xccc"]["primary_type"] == "GENERALIST"
    out2, changed2 = apply_overrides(payload, {})
    assert changed2 == 0 and out2 is payload
