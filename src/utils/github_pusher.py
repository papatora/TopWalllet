"""Push pipeline results back to the GitHub repo (results/, PROGRESS.md, stats).

The token is read from the environment at runtime and never written to disk
or logs. Designed to be called by the export stage after every pipeline run.
"""
from __future__ import annotations

import logging
import subprocess

from config.settings import settings
from src.utils.logger import jlog

log = logging.getLogger(__name__)


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def push_results() -> bool:
    """Stage results/ + PROGRESS.md, commit, and push. Returns success bool."""
    if not settings.github_token:
        jlog(log, logging.WARNING, "AUTO_PUSH_RESULTS is on but GITHUB_TOKEN is empty; skipping")
        return False
    try:
        _run_git(["add", "results", "PROGRESS.md", "--"])
        status = _run_git(["status", "--porcelain"])
        if not status.stdout.strip():
            jlog(log, logging.INFO, "nothing new to push")
            return True
        _run_git(["-c", "user.name=TopWallet Bot", "-c", "user.email=topwallet-bot@users.noreply.github.com",
                  "commit", "-m", "chore(results): automated pipeline output update"])
        url = f"https://x-access-token:{settings.github_token}@github.com/{settings.github_repo}.git"
        _run_git(["push", url, f"HEAD:{settings.github_branch}"])
        jlog(log, logging.INFO, "pushed results to GitHub", repo=settings.github_repo)
        return True
    except subprocess.CalledProcessError as e:
        jlog(log, logging.ERROR, "git push failed", stderr=(e.stderr or "")[-500:])
        return False
