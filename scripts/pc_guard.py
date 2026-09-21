"""[PC] Night guard — memantau workflow A-J selama user tidur.

Sinyal terukur (semua lokal, tanpa SSH):
  - data/topwallet.db mtime      → ekstraksi+rebuild sudah lewat?
  - git log commit "fix(audit-*)"→ ronde audit maju?
  - explorer 8787 hidup?         → auditor butuh ini

EXIT (bangunkan main agent via task-notification) hanya saat:
  - explorer yang tadinya hidup mati 2x cek beruntun
  - fase audit sudah mulai (DB pernah di-rebuild) tapi >4 jam tanpa commit baru
  - >12 commit fix(audit) — melewati cap 10 ronde = melenceng
  - deadline 10 jam tercapai (normal — lapor ringkasan)

Normal = diam & lanjut polling. Print tiap cek biar bisa dibaca belakangan.
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "topwallet.db"
CHECK_EVERY = 30 * 60
MAX_HOURS = 10
AUDIT_STALL_HOURS = 4
MAX_AUDIT_COMMITS = 12


def sh(cmd: str, timeout: int = 30) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return (r.stdout or "").strip()
    except Exception as e:
        return f"ERR {e}"


def explorer_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/", timeout=5) as r:
            return r.status == 200
    except OSError:
        return False


def db_mtime() -> float:
    try:
        return DB.stat().st_mtime
    except OSError:
        return 0.0


def last_commits(n: int = 5) -> list[tuple[float, str]]:
    out = sh(f'git -C "{REPO}" log -{n} --format="%ct %s"')
    rows = []
    for ln in out.splitlines():
        if " " in ln:
            ts, _, msg = ln.partition(" ")
            try:
                rows.append((float(ts), msg))
            except ValueError:
                pass
    return rows


def audit_commit_count() -> int:
    out = sh(f'git -C "{REPO}" log -20 --format="%s"')
    return sum(1 for ln in out.splitlines() if ln.startswith("fix(audit"))


def main() -> int:
    t0 = time.time()
    db0 = db_mtime()
    explorer_was_up = explorer_up()
    audit_phase_since = None
    down_streak = 0
    checks = 0
    print(f"[guard] start · db_mtime_age={time.time()-db0:.0f}s · "
          f"explorer={'up' if explorer_was_up else 'down'}", flush=True)

    while time.time() - t0 < MAX_HOURS * 3600:
        checks += 1
        time.sleep(CHECK_EVERY)
        notes = []

        db_now = db_mtime()
        if db_now != db0:
            db0 = db_now
            notes.append("DB di-rebuild (ekstraksi lewat)")
            if audit_phase_since is None:
                audit_phase_since = time.time()

        commits = last_commits(5)
        audit_commits = audit_commit_count()
        last_commit = commits[0] if commits else (0, "")
        age_h = (time.time() - last_commit[0]) / 3600
        notes.append(f"last commit {age_h:.1f}j lalu: {last_commit[1][:50]}")

        up = explorer_up()
        if explorer_was_up and not up:
            down_streak += 1
            notes.append(f"explorer DOWN (streak {down_streak})")
            if down_streak >= 2 and audit_phase_since is not None:
                print(f"[guard] ANOMALI: explorer mati saat fase audit. "
                      f"{notes}", flush=True)
                return 1
        else:
            down_streak = 0
            notes.append("explorer up")
        explorer_was_up = explorer_was_up or up

        if audit_phase_since is not None:
            stall_h = (time.time() - max(audit_phase_since, last_commit[0])) / 3600
            if stall_h > AUDIT_STALL_HOURS:
                print(f"[guard] ANOMALI: fase audit diam {stall_h:.1f} jam "
                      f"tanpa commit. {notes}", flush=True)
                return 1
            if audit_commits > MAX_AUDIT_COMMITS:
                print(f"[guard] ANOMALI: {audit_commits} commit fix(audit) — "
                      f"lewat cap 10 ronde, melenceng. {notes}", flush=True)
                return 1

        print(f"[guard #{checks}] OK · {'; '.join(notes)} · "
              f"audit_commits={audit_commits}", flush=True)

    phase, _st = "", {}
    try:
        phase = json.loads((REPO / "results" / "arkham_status.json")
                           .read_text(encoding="utf-8")).get("phase", "?")
    except (OSError, ValueError):
        pass
    print(f"[guard] deadline 10 jam — laporan akhir: audit_commits="
          f"{audit_commit_count()}, arkham_phase={phase}, "
          f"last_commits={[c[1][:40] for c in last_commits(3)]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
