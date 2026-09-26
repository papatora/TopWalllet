import asyncio
import json
import sys

sys.path.insert(0, "/opt/topwallet")
sys.path.insert(0, "/opt/topwallet/scripts")

from x_attribution import load_env, search_wallet  # noqa: E402


async def main() -> None:
    env = load_env()
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900})
        await ctx.add_cookies([
            {"name": "auth_token", "value": env["X_AUTH_TOKEN"], "domain": ".x.com",
             "path": "/", "httpOnly": True, "secure": True},
            {"name": "ct0", "value": env.get("X_CT0", ""), "domain": ".x.com",
             "path": "/", "secure": True},
        ])
        page = await ctx.new_page()
        # whale PIPEDOG (SELL $30,5 jt, kasus viral dari temuan P2) — alamat
        # ditemukan dari laporan debat: 0xa359e619...e814; ambil lengkap dari
        # wallet_labels via query sederhana kalau perlu. Uji juga alamat
        # FOMOFIED whale yang jelas ramai dibicarakan.
        tests = ["0xa359e619", "0xf3f7dc25cad40e4d88e6876895a7606089a71d16"]
        for q in tests:
            found = await search_wallet(page, q if len(q) == 42 else q)
            print(f"{q[:14]} → {len(found)} tweet")
            for t in found[:3]:
                print("   @", t["user"], "|", t["url"][:60])
        await browser.close()


asyncio.run(main())
