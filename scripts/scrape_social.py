"""Browser-based scraper for fomo.family + GMGN robinhood (runs on VPS).

Captures: rendered wallet addresses + PnL text, AND the actual JSON API
responses (prod-api.fomo.family + gmgn rank) via real browser session.
"""
import asyncio
import json
import re

CA = "0x39dbed3a2bd333467115de45665cc57f813c4571"
OUT = "/opt/topwallet/results/external_leaderboards.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


async def main():
    from playwright.async_api import async_playwright

    cookies = json.load(open("/opt/topwallet/fomo_cookies.json"))
    ss_map = {"no_restriction": "None", "lax": "Lax", "strict": "Strict", "unspecified": "Lax"}
    for c in cookies:
        c["sameSite"] = ss_map.get(str(c.get("sameSite", "Lax")).lower(), "Lax")
        c.pop("storeId", None)
        c.pop("hostOnly", None)
    api_captures = []
    result = {"generated_at": time.time(), "sources": {}}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ── fomo.family (with user cookies) ──
        ctx = await browser.new_context(user_agent=UA)
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        async def on_response(resp):
            if "prod-api.fomo.family" in resp.url:
                try:
                    api_captures.append({"url": resp.url, "data": await resp.json()})
                except Exception:
                    pass
        page.on("response", on_response)

        for label, url in [("fomo_token", f"https://fomo.family/tokens/robinhood/{CA}"),
                           ("fomo_chain", "https://fomo.family/tokens/robinhood")]:
            try:
                await page.goto(url, timeout=45000, wait_until="networkidle")
                await page.wait_for_timeout(4000)
                text = await page.evaluate("document.body.innerText")
                addrs = sorted(set(re.findall(r"0x[a-fA-F0-9]{40}", text)))
                result["sources"][label] = {"addresses": addrs, "text_sample": text[:3000]}
            except Exception as e:
                result["sources"][label] = {"error": str(e)[:200]}
        result["sources"]["fomo_api_captures"] = api_captures
        await ctx.close()

        # ── GMGN robinhood smart money (browser carries CF clearance after landing) ──
        ctx2 = await browser.new_context(user_agent=UA)
        page2 = await ctx2.new_page()
        try:
            await page2.goto("https://gmgn.ai/robinhood", timeout=45000,
                             wait_until="domcontentloaded")
            await page2.wait_for_timeout(8000)
            # fetch the rank API from within page context (browser has CF cookies)
            js = """
            async () => {
                const r = await fetch('/defi/quotation/v1/rank/robinhood/wallets/30d?orderby=pnl&direction=desc',
                    {headers: {'accept': 'application/json'}});
                return {status: r.status, body: await r.text()};
            }"""
            res = await page2.evaluate(js)
            body = res.get("body", "")
            try:
                result["sources"]["gmgn_smartmoney_30d"] = json.loads(body)
            except Exception:
                result["sources"]["gmgn_smartmoney_30d"] = {"raw": body[:2000], "status": res.get("status")}
        except Exception as e:
            result["sources"]["gmgn_smartmoney_30d"] = {"error": str(e)[:200]}
        await ctx2.close()
        await browser.close()

    with open(OUT, "w") as f:
        json.dump(result, f, indent=1)
    print("saved", OUT)


import time
asyncio.run(main())
