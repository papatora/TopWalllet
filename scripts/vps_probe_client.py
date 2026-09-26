import asyncio
import json
import sys
import urllib.request

sys.path.insert(0, "/opt/topwallet")

CA = "0xf3f7dc25cad40e4d88e6876895a7606089a71d16"


async def main() -> None:
    # 1) raw urllib — persis seperti tes manual kemarin
    key = ""
    for line in open("/opt/topwallet/.env"):
        if line.startswith("ETHERSCAN_API_KEY="):
            key = line.strip().split("=", 1)[1].split(",")[0]
            break
    url = ("https://api.etherscan.io/v2/api?chainid=4663&module=account&action=tokentx"
           f"&contractaddress={CA}&page=1&offset=3&sort=desc&apikey={key}")
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"accept": "application/json", "user-agent": "Mozilla/5.0"}),
            timeout=25) as r:
        d = json.loads(r.read().decode())
    print("RAW urllib result type:", type(d.get("result")).__name__,
          "| len:", len(d["result"]) if isinstance(d.get("result"), list) else str(d.get("result"))[:80])

    # 2) client EtherscanV2 — sama-sama endpoint
    from src.utils.etherscan_client import EtherscanV2Client
    cl = EtherscanV2Client(rps=2.0)
    print("client base_api:", cl.base_api, "| chain_id:", cl.chain_id)
    data = await cl._call({"module": "account", "action": "tokentx",
                           "contractaddress": CA, "page": 1, "offset": 3, "sort": "desc"})
    print("client _call result type:", type(data).__name__,
          "| len:", len(data) if isinstance(data, list) else str(data)[:200])
    items = await cl.token_transfers(CA, 24)
    print("client token_transfers:", len(items))
    try:
        await cl.close()
    except Exception:
        pass


asyncio.run(main())
