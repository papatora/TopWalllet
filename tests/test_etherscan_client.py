"""Etherscan V2 client mappers — response shape translation must be exact.

Landmine being pinned: the whole pipeline consumes Blockscout-SHAPED transfer
items (from.hash / token.address / total.value / block_number). The Etherscan
adapter must translate tokentx/txlist items faithfully or enrichment silently
mis-parses (the exact failure mode that poisoned Blockscout after its API
shape changed).
"""
from __future__ import annotations

from src.utils.etherscan_client import (
    decode_abi_string,
    decode_abi_uint,
    tx_to_blockscout_shape,
    tx_to_funding_shape,
)


def test_tokentx_maps_to_blockscout_shape():
    raw = {
        "blockNumber": "57042707",
        "timeStamp": "1789123456",
        "hash": "0xABC",
        "from": "0xAAAA",
        "contractAddress": "0xTOK",
        "to": "0xBBBB",
        "value": "1000000000000000000",
        "tokenName": "Test",
        "tokenSymbol": "TST",
        "tokenDecimal": "18",
    }
    it = tx_to_blockscout_shape(raw)
    assert it["from"]["hash"] == "0xaaaa"
    assert it["to"]["hash"] == "0xbbbb"
    assert it["token"]["address"] == "0xtok"
    assert it["token"]["decimals"] == 18
    assert it["total"]["value"] == "1000000000000000000"
    assert it["block_number"] == 57042707
    assert it["transaction_hash"] == "0xabc"
    # garansi: _transfer_items verifier membaca field ini
    assert it["token"]["address"] == it["token"].get("address_hash") or it["token"]["address"]


def test_tokentx_bad_decimals_defaults_18():
    raw = {"blockNumber": "1", "hash": "0x1", "from": "0xa", "to": "0xb",
           "contractAddress": "0xc", "value": "5", "tokenDecimal": ""}
    it = tx_to_blockscout_shape(raw)
    assert it["token"]["decimals"] == 18
    assert it["total"]["value"] == "5"


def test_txlist_maps_to_funding_shape():
    raw = {"blockNumber": "42", "timeStamp": "1789123000", "hash": "0xH",
           "from": "0xFUNDER", "to": "0xWALLET", "value": "2000000000000000000"}
    it = tx_to_funding_shape(raw)
    assert it["from"]["hash"] == "0xfunder"
    assert it["to"]["hash"] == "0xwallet"
    assert it["value"] == "2000000000000000000"
    assert it["block_number"] == 42
    assert it["internal"] is False
    # first_funding membaca field ini
    assert float(it["value"]) / 1e18 == 2.0


def test_decode_abi_string_and_uint():
    # symbol() -> "TST" (0x545354)
    data = "0x" + "00" * 32 + hex(3)[2:].zfill(64) + b"TST".hex() + "00" * 29
    assert decode_abi_string(data) == "TST"
    assert decode_abi_uint("0x" + hex(18)[2:].zfill(64)) == 18
    assert decode_abi_string("0x") == ""
    assert decode_abi_uint("0xzz") is None
