import json

# Diamond wallets from VAPE + Life K-line
diamonds = {
    "0x472e619c30ea725ed9ca2f60e54a307d3044d05f": {"token": "VAPE", "entry": "5.3h pre-pump", "pnl_pct": 3166, "wr": 100},
    "0x30b6d90dc881ecc2e17080af12af0b0146888485": {"token": "VAPE", "entry": "6.8h pre-pump", "pnl_pct": 2704, "wr": 100},
    "0x43dcf4cb1c6d84e54f0b11025a8fbb845e8e212a": {"token": "VAPE", "entry": "2.7h post-start", "pnl_pct": 9150, "wr": 64, "pnl_30d": 136910, "tok_30d": 1356},
    "0xdc137c78c17500223031a2ca326c11062be0bad1": {"token": "Life K-line", "entry": "51 DAYS pre-pump", "pnl_pct": 18075, "wr": 100},
}

# MEME traders from cross-token analysis
meme_traders = {
    "0xff2bcd8e3a12d6930518a45519da1c5e67129948": {"pnl_30d": 1010545, "wr": 37.9, "tok": 353, "type": "HIGH_FREQ"},
    "0xf7b95fa5c0291319c0d14d098b19ec9d3533fe48": {"pnl_30d": 1094768, "wr": 19.1, "tok": 130, "type": "HIGH_FREQ"},
    "0x00d78daf782921b27a6b407d34f19842c10a4a6b": {"pnl_30d": 759171, "wr": 24.8, "tok": 2000, "type": "ULTRA_HFT"},
    "0xda6fad6284d5920fad1418d29ac28ec146f4e61d": {"pnl_30d": 502952, "wr": 15.8, "tok": 49, "type": "MULTI_TOKEN"},
    "0xa72a5b06927badb020d235f5f43ce56507ab2399": {"pnl_30d": 348943, "wr": 66.7, "tok": 14, "type": "DEV_FEE_COLLECTOR"},
}

# Combine all profiles
all_wallets = {}
for addr, info in diamonds.items():
    all_wallets[addr] = {**info, "source": "pump_analysis", "chain": "bsc"}
for addr, info in meme_traders.items():
    all_wallets[addr] = {**info, "source": "meme_top_traders", "chain": "bsc"}

# Build groups
groups = {
    "VAPE_COORDINATED": [a for a, i in all_wallets.items() if i.get("token") == "VAPE"],
    "SOLO_ACCUMULATOR": [a for a, i in all_wallets.items() if i.get("token") == "Life K-line"],
    "HIGH_FREQ_TRADERS": [a for a, i in all_wallets.items() if i.get("type") in ("HIGH_FREQ", "ULTRA_HFT")],
    "DEV_OPERATORS": [a for a, i in all_wallets.items() if i.get("type") == "DEV_FEE_COLLECTOR"],
}

output = {
    "generated": "2026-09-08",
    "chain": "bsc",
    "total_wallets": len(all_wallets),
    "groups": groups,
    "wallets": all_wallets,
}

with open("results/diamond_groups.json", "w") as f:
    json.dump(output, f, indent=1)

print("=== DIAMOND WALLET GROUPS ===")
print(f"Total unique wallets: {len(all_wallets)}")
for gname, members in groups.items():
    print(f"\n{gname}: {len(members)} wallets")
    for addr in members:
        info = all_wallets[addr]
        print(f"  {addr[:16]}... pnl={info.get('pnl_pct', info.get('pnl_30d', '?'))} wr={info.get('wr', '?')}%")
EOF_MARKER = None
