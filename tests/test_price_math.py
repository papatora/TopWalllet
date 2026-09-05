"""Tests for on-chain price math (sqrtPriceX96 → USD) and EIP-55 checksums."""
from src.enrich.price_fetcher import _sqrt_to_raw_price, _word
from src.rank.export import eip55
from src.utils.rpc_client import v4_swap_topic0


def test_v4_swap_topic_matches_onchain():
    # empirically verified: Swap logs on Robinhood Chain's PoolManager carry
    # this exact topic0 (candidate hashes with parameter names do NOT match)
    assert v4_swap_topic0() == \
           "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"


def test_sqrt_price_conversion():
    # sqrtPriceX96 = 2^96 → price ratio 1.0
    assert abs(_sqrt_to_raw_price(2 ** 96) - 1.0) < 1e-12
    # 2x price → sqrt(2) * 2^96
    two_x = int((2 ** 0.5) * (2 ** 96))
    assert abs(_sqrt_to_raw_price(two_x) - 2.0) < 1e-9
    assert _sqrt_to_raw_price(0) == 0.0


def test_word_extraction():
    data = "0x" + "00" * 32 + "ff" * 32  # word0=0, word1=0xff...
    assert _word(data, 0) == 0
    assert _word(data, 1) == int("ff" * 32, 16)


def test_eip55_checksum():
    # canonical test vector from EIP-55
    assert eip55("0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed") == \
           "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    assert eip55("0x52908400098527886E0F7030069857D2E4169EE7") == \
           "0x52908400098527886E0F7030069857D2E4169EE7"
