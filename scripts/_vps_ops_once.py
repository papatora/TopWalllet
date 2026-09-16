"""Push current main via VPS (force, bundle)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _vps  # noqa: E402

LOCAL = Path(r"C:/Users/ROG/Documents/ClaudeCode/SniperToken/TopWalllet")
import subprocess
subprocess.run(["git", "bundle", "create", "C:/Users/ROG/AppData/Local/Temp/twx.bundle", "main"],
               cwd=LOCAL, check=True)

ssh = _vps.connect()
sftp = ssh.open_sftp()
sftp.put(r"C:/Users/ROG/AppData/Local/Temp/twx.bundle", "/tmp/twx.bundle")
sftp.close()


def run(cmd, t=150):
    _, out, err = ssh.exec_command(cmd, timeout=t)
    return out.read().decode() + err.read().decode()


print(run("cd /opt/topwallet && git fetch /tmp/twx.bundle main:twx 2>&1 | tail -1 && "
          "git reset --hard twx 2>&1 | tail -1 && git branch -D twx 2>/dev/null; "
          "git log --oneline -1"))
print(run("cd /opt/topwallet && set -a && . ./.env && set +a && "
          "git push https://x-access-token:$GITHUB_TOKEN@github.com/papatora/TopWalllet.git "
          "master:main --force 2>&1 | sed -E 's/x-access-token:[^@]*@/:***@/' | tail -2", 150))
ssh.close()
