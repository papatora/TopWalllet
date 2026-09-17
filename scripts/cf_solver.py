"""Cloudflare Turnstile solver via 2captcha (user-provided key, .env).

The arkm.com "Just a moment..." page embeds a Turnstile widget plus the
managed-challenge params (window._cf_chl_opt: cData/chlPageData). Recipe:
  1. read the challenge page HTML → sitekey + cData + chlPageData
  2. 2captcha TurnstileTaskProxyless → token (poll res.php)
  3. inject: fill [name="cf-turnstile-response"] + submit challenge-form
  4. reload & verify the title no longer says "Just a moment"

Key lives in local .env (TWOCAPTCHA_KEY) — NEVER in git (ATURAN 4).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

API = "https://api.2captcha.com"


def _post(path: str, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(url: str, timeout: int = 20) -> dict | str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = r.read().decode()
    try:
        return json.loads(body)
    except ValueError:
        return body


def extract_params(html: str) -> dict:
    sitekey = None
    m = re.search(r'data-sitekey="([0-9a-fx]{20,})"', html, re.I)
    if m:
        sitekey = m.group(1)
    if not sitekey:
        m = re.search(r'"?sitekey"?\s*[:=]\s*"(0x[0-9a-f]{20,})"', html, re.I)
        if m:
            sitekey = m.group(1)
    cdata = None
    m = re.search(r'"cData"\s*:\s*"([^"]+)"', html)
    if m:
        cdata = m.group(1)
    chlpagedata = None
    m = re.search(r'"chlPageData"\s*:\s*("(\{.*?\})")', html)
    if m:
        chlpagedata = m.group(2)
    return {"sitekey": sitekey, "cData": cdata, "chlPageData": chlpagedata}


def solve_turnstile(website_url: str, html: str, api_key: str | None = None,
                    timeout_s: int = 150) -> str | None:
    """Order a Turnstile solve for this challenge page, return the token."""
    key = api_key or os.getenv("TWOCAPTCHA_KEY")
    if not key:
        print("[2captcha] TWOCAPTCHA_KEY kosong")
        return None
    params = extract_params(html)
    if not params["sitekey"]:
        print("[2captcha] sitekey tidak ketemu di halaman challenge")
        return None
    task = {
        "type": "TurnstileTaskProxyless",
        "websiteURL": website_url,
        "websiteKey": params["sitekey"],
    }
    if params["cData"]:
        task["cData"] = params["cData"]
    if params["chlPageData"]:
        task["chlPageData"] = params["chlPageData"]
    order = _post("/createTask", {"clientKey": key, "task": task})
    if order.get("errorId"):
        print("[2captcha] createTask error:", order.get("errorDescription"))
        return None
    task_id = order.get("taskId")
    print(f"[2captcha] task {task_id} sitekey={params['sitekey'][:10]}…")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(5)
        res = _post("/getTaskResult",
                    {"clientKey": key, "taskId": task_id})
        if res.get("errorId"):
            print("[2captcha] result error:", res.get("errorDescription"))
            return None
        if res.get("status") == "ready":
            token = res["solution"].get("token")
            print(f"[2captcha] solved dalam {time.time()-t0:.0f}s")
            return token
    print("[2captcha] timeout")
    return None


INJECT_JS = """
(token) => {
  const inp = document.querySelector('[name="cf-turnstile-response"]')
           || document.querySelector('input[name="cf-turnstile-response"]');
  if (inp) inp.value = token;
  const f = document.querySelector('form#challenge-form')
         || document.querySelector('form');
  if (f) { f.submit(); return 'submitted'; }
  if (inp && window.turnstile) {
    try { window.turnstile.getResponse(); } catch (e) {}
    return 'filled-noform';
  }
  return 'no-inject-point';
}
"""
