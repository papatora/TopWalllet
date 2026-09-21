"""[PC] Night guard v2 — MANDOR + PENJAGA KEAMANAN (murni deterministik).

Lapisan keamanan (scan tiap 60 detik, kejar & bunuh + bangunkan boss):
  - Proses install tanpa izin: pip/npm/yarn/pnpm/poetry install, uv pip
  - Pola malware: curl|bash, PowerShell -EncodedCommand / IEX /
    DownloadString / Set-ExecutionPolicy bypass
  - File sensitif berubah: requirements.txt, package.json, package-lock
    → REVERT otomatis via git checkout (tracked)
  - .venv/Lib/site-packages berubah mtime → ada yg ter-install diam-diam

Lapisan mandor (tiap 30 menit):
  - DB lokal di-rebuild? (ekstraksi lewat) · commit fix(audit-*) maju?
  - explorer 8787 hidup? · commit fix ≤ 12 (cap 10 ronde)?

ANTI-HALU: guard ini KODE MURNI — aturannya pola byte + hash + hitungan,
nol penilaian subjektif. Exit(1) = ada anomali → bangunkan main agent.
Self-match dihindari: enumerasi proses polos, pola dicocokkan di Python,
proses yg cmdline-nya mengandung "pc_guard" dikecualikan.
"""
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
SEC_EVERY = 60          # detik — scan keamanan
DEEP_EVERY = 30         # scan keamanan per deep check
MAX_HOURS = 10
AUDIT_STALL_HOURS = 4
MAX_AUDIT_COMMITS = 12
GUARD_TAG = "pc_guard"

GUARDED_FILES = [
    REPO / "requirements.txt",
    REPO / "desktop-electron" / "package.json",
    REPO / "desktop-electron" / "package-lock.json",
]
SITE_PACKAGES = REPO / ".venv" / "Lib" / "site-packages"

KILL_PATTERNS = (
    "pip install", "pip3 install", "npm install", "npm i ", "yarn add",
    "pnpm add", "poetry add", "uv pip install",
    "invoke-expression", "iex (", "iex(", "-encodedcommand",
    "downloadstring", "set-executionpolicy bypass", "curl -l |",
)


def sh(cmd: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"ERR {e}"


def sha256(p: Path) -> str:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def dir_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def explorer_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/", timeout=5) as r:
            return r.status == 200
    except OSError:
        return False


def kill_pid(pid: int) -> None:
    sh(f"taskkill /F /PID {pid}")


def security_scan(baselines: dict) -> tuple[list[str], bool]:
    """Return (alerts, killed_something). Setiap alert menyertakan bukti."""
    alerts: list[str] = []
    killed = False
    me = os.getpid()

    # 1. enumerasi semua proses (polos — tanpa pola di cmdline enumerator)
    raw = sh("powershell -NoProfile -Command "
             "\"Get-CimInstance Win32_Process | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json\"", 90)
    procs = []
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        procs = [(int(p.get("ProcessId") or 0), (p.get("CommandLine") or "").lower())
                 for p in data if p.get("ProcessId")]
    except (ValueError, TypeError):
        alerts.append("SEC: gagal enumerasi proses (parse)")  # jangan diam

    for pid, cmd in procs:
        if pid == me or GUARD_TAG in cmd:
            continue
        hit = next((pat for pat in KILL_PATTERNS if pat in cmd), None)
        if hit:
            kill_pid(pid)
            killed = True
            alerts.append(f"SEC-KILL pid={pid} pattern='{hit}' cmd={cmd[:140]}")

    # 2. file sensitif — hash drift → revert
    for f in GUARDED_FILES:
        cur = sha256(f)
        if cur != baselines.get(str(f), cur):
            if baselines.get(str(f)):  # pernah dibaseline = berubah
                r = sh(f'git -C "{REPO}" checkout -- "{f}"')
                alerts.append(f"SEC-REVERT {f.name} berubah (reverted) git={r[:60]}")
            baselines[str(f)] = cur  # baseline ulang setelah revert

    # 3. site-packages berubah = ada install lolos
    m = dir_mtime(SITE_PACKAGES)
    if m != baselines.get("__sp__"):
        if baselines.get("__sp__"):
            alerts.append("SEC: site-packages BERUBAH — ada install diam-diam!")
        baselines["__sp__"] = m
    return alerts, killed


def deep_check(state: dict) -> list[str]:
    notes: list[str] = []
    db_now = db_mtime()
    if db_now != state.get("db0", db_now):
        state["db0"] = db_now
        state["audit_since"] = state.get("audit_since") or time.time()
        notes.append("DB di-rebuild (ekstraksi lewat)")

    commits = sh(f'git -C "{REPO}" log -6 --format="%ct %s"')
    rows = []
    for ln in commits.splitlines():
        if " " in ln:
            ts, _, msg = ln.partition(" ")
            try:
                rows.append((float(ts), msg))
            except ValueError:
                pass
    state["rows"] = rows
    audit_commits = sum(1 for _, msg in rows if msg.startswith("fix(audit"))
    state["audit_commits"] = audit_commits
    notes.append(f"last: {rows[0][1][:46] if rows else '-'}")
    notes.append(f"fix(audit)={audit_commits}")

    up = explorer_up()
    if state.get("explorer_was_up") and not up:
        state["down_streak"] = state.get("down_streak", 0) + 1
        notes.append(f"explorer DOWN ({state['down_streak']})")
    else:
        state["down_streak"] = 0
        notes.append("explorer up")
    state["explorer_was_up"] = up or state.get("explorer_was_up", False)
    return notes


def main() -> int:
    t0 = time.time()
    baselines = {str(f): sha256(f) for f in GUARDED_FILES}
    baselines["__sp__"] = dir_mtime(SITE_PACKAGES)
    state = {"db0": db_mtime(), "audit_since": None, "down_streak": 0,
             "explorer_was_up": explorer_up(), "audit_commits": 0,
             "rows": []}
    print(f"[guard v2] start · security scan tiap {SEC_EVERY}s · "
          f"deep tiap {SEC_EVERY*DEEP_EVERY}s", flush=True)

    it = 0
    while time.time() - t0 < MAX_HOURS * 3600:
        it += 1
        # --- lapisan keamanan (60s) ---
        alerts, killed = security_scan(baselines)
        for a in alerts:
            print(f"[guard] ALERT: {a}", flush=True)
        if killed:
            print("[guard] proses berbahaya DIBUNUH — bangunkan boss", flush=True)
            return 1

        # --- lapisan mandor (30 menit) ---
        if it % DEEP_EVERY == 0:
            notes = deep_check(state)
            age_h = 0.0
            if state["rows"]:
                age_h = (time.time() - state["rows"][0][0]) / 3600
            notes.append(f"last commit {age_h:.1f}j")
            audit_since = state.get("audit_since")
            if audit_since:
                stall_h = (time.time() - max(audit_since,
                           state["rows"][0][0] if state["rows"] else audit_since)) / 3600
                if stall_h > AUDIT_STALL_HOURS:
                    print(f"[guard] ANOMALI: fase audit diam {stall_h:.1f}j. "
                          f"{'; '.join(notes)}", flush=True)
                    return 1
                if state["audit_commits"] > MAX_AUDIT_COMMITS:
                    print(f"[guard] ANOMALI: {state['audit_commits']} commit "
                          f"fix(audit) — lewat cap. {'; '.join(notes)}", flush=True)
                    return 1
            print(f"[guard #{it}] OK · {'; '.join(notes)}", flush=True)
        time.sleep(SEC_EVERY)

    print(f"[guard] deadline {MAX_HOURS} jam — serah ke pagi", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
