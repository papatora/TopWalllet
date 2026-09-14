"""SSH connection helper for the deploy scripts — credentials come from the
environment (repo-root .env, gitignored), never from source.

  VPS_HOST, VPS_PORT (22), VPS_USER (root)
  VPS_SSH_KEY   path to a private key (preferred), or
  VPS_PASSWORD  password auth fallback
"""
import os
import sys
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def connect(timeout: int = 25) -> paramiko.SSHClient:
    host = os.getenv("VPS_HOST")
    key = os.getenv("VPS_SSH_KEY")
    password = os.getenv("VPS_PASSWORD")
    if not host or not (key or password):
        sys.exit("VPS_HOST and VPS_SSH_KEY or VPS_PASSWORD must be set in .env (see .env.example)")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        host,
        port=int(os.getenv("VPS_PORT", "22")),
        username=os.getenv("VPS_USER", "root"),
        key_filename=os.path.expanduser(key) if key else None,
        password=None if key else password,
        timeout=timeout,
    )
    return ssh
