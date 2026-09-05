#!/usr/bin/env bash
# TopWallet — one-command VPS setup (Ubuntu 22.04+).
#   curl -fsSL <repo>/setup.sh | bash    or:  sudo bash setup.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/papatora/TopWalllet.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/topwallet}"

log() { echo -e "\033[1;32m[topwallet]\033[0m $*"; }

# --- 1. system deps -------------------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl git python3 python3-venv docker.io docker-compose-v2 2>/dev/null \
    || apt-get install -y ca-certificates curl git python3 python3-venv docker.io docker-compose
  systemctl enable --now docker
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y git python3 python3-pip docker git-docker-compose-plugin || true
  systemctl enable --now docker
fi

# --- 2. clone / update repo ----------------------------------------------
if [ -d "$INSTALL_DIR/.git" ]; then
  log "updating existing repo at $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only || log "pull failed, keeping current copy"
else
  log "cloning $REPO_URL → $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# --- 3. env file ----------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  log "created .env — EDIT IT and add your EVM_RPC_ENDPOINTS / GITHUB_TOKEN keys"
  "${EDITOR:-nano}" .env || true
fi

# --- 4. build + start -----------------------------------------------------
docker compose build
log "running first pipeline (worker)…"
docker compose run --rm worker
docker compose up -d scheduler api
log "stack is up: scheduler (weekly cron), api (:8000)"
docker compose ps
log "done. results land in $INSTALL_DIR/results and are auto-pushed to GitHub."
