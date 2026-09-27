import json
from playwright.sync_api import sync_playwright

POSTS = [
    "https://x.com/wazzcrypto/status/2104194307628621976",
    "https://x.com/WazzCrypto/status/2104195256397033835",
]

JS_TEXT = """
() => {
  const art = document.querySelector('article');
  const main = art ? art.innerText : '';
  // komentar: semua article setelah yang pertama
  const arts = [...document.querySelectorAll('article')];
  const replies = arts.slice(1).map(a => {
    const links = [...a.querySelectorAll('a[href^="/"]')];
    const st = links.find(l => /\\/status\\/\\d+/.test(l.getAttribute('href') || ''));
    const u = links.find(l => /^\\/[^/]+$/.test(l.getAttribute('href') || ''));
    return { user: u ? u.getAttribute('href').slice(1) : '?',
             url: st ? 'https://x.com' + st.getAttribute('href') : '',
             text: a.innerText.slice(0, 1200) };
  });
  return { main: main.slice(0, 5000), replies };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    out = {}
    for url in POSTS:
        pg.goto(url, wait_until="domcontentloaded", timeout=60_000)
        pg.wait_for_timeout(6_000)
        # scroll untuk memuat komentar
        for _ in range(6):
            pg.mouse.wheel(0, 2500)
            pg.wait_for_timeout(1_500)
        d = pg.evaluate(JS_TEXT)
        out[url] = d
        print("=" * 60)
        print(url)
        print("POST:", d["main"][:1500].replace("\n", " | ")[:1500])
        print(f"replies tertangkap: {len(d['replies'])}")
    pg.close()
    json.dump(out, open(r"C:/Users/ROG/Documents/ClaudeCode/SniperToken/TopWalllet/results/wazz_thread.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved results/wazz_thread.json")
