"""Quick check: is verifier running? (non-hanging pgrep)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402

ssh = _vps.connect()
_, o, e = ssh.exec_command(
    "pgrep -f '[r]everify_tags' && echo RUNNING || echo NOT-RUNNING; "
    "tail -3 /opt/topwallet/logs/reverify.log | grep -v httpx", timeout=20)
print(o.read().decode(), e.read().decode())
ssh.close()
