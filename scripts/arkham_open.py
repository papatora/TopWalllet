"""Open a REAL Chrome (not an embedded WebView) with a dedicated profile for
the Arkham session — the "chromium temp" flow the user defined.

- Profile: data/arkham-profile (gitignored; persists → login sekali berlaku
  lintas hari; JANGAN dipakai browsing lain, khusus Arkham).
- Remote debugging :9222 → harvest scripts attach via playwright
  connect_over_cdp (browser tetap hidup independen dari script ini).

User logs in MANUALLY in the opened window (his account, his machine).
Runs LOCALLY by explicit user design (PRE_COMPACT S-37-E) — bukan scraping
VPS; panen datanya tetap lewat sesi ber-login ini saja.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = 9222
URL = "https://arkm.com/login"

# browser pilihan: brave (default, permintaan user 2026-09-18) | chrome | edge
BROWSERS = {
    "brave": {
        "paths": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ],
        "profile": REPO / "data" / "arkham-profile-brave",
    },
    "chrome": {
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "profile": REPO / "data" / "arkham-profile",
    },
    "edge": {
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "profile": REPO / "data" / "arkham-profile-edge",
    },
}


def port_live() -> bool:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/version", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def main() -> int:
    which = (sys.argv[1] if len(sys.argv) > 1
             else os.getenv("ARKHAM_BROWSER", "brave")).lower()
    if which not in BROWSERS:
        sys.exit(f"browser '{which}' tidak dikenal — pilih: {', '.join(BROWSERS)}")
    spec = BROWSERS[which]

    if port_live():
        print(f"browser sudah jalan di :{PORT} — pakai sesi itu")
        return 0

    exe = next((c for c in spec["paths"] if os.path.exists(c)), None)
    if not exe:
        sys.exit(f"{which} tidak ketemu — cek path di BROWSERS")

    profile = spec["profile"]
    profile.mkdir(parents=True, exist_ok=True)
    DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [exe,
         f"--user-data-dir={profile}",
         f"--remote-debugging-port={PORT}",
         "--no-first-run", "--no-default-browser-check",
         "--window-size=1500,950",
         URL],
        creationflags=DETACHED,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(1)
        if port_live():
            break
    if not port_live():
        sys.exit("debug port tidak naik — cek apakah window muncul")
    info = json.loads(urllib.request.urlopen(
        f"http://127.0.0.1:{PORT}/json/version", timeout=5).read())
    print("browser siap:", info.get("Browser"), f"({which})")
    print("profile:", profile)
    print("→ LOGIN MANUAL di window itu; session tersimpan di profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
