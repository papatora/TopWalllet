"""Upload Xlogin + converted accounts ke VPS /opt/xlogin (SFTP, tanpa git)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
import _vps  # noqa: E402

SRC = r"C:\Users\ROG\Documents\antigravity\xlogin_extract\Xlogin"
ACCOUNTS = r"C:\Users\ROG\Documents\antigravity\xlogin_accounts.txt"

ssh = _vps.connect()
sftp = ssh.open_sftp()
try:
    sftp.mkdir("/opt/xlogin")
except IOError:
    pass
for root, dirs, files in os.walk(SRC):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "examples", "screenshots")]
    for fn in files:
        lp = os.path.join(root, fn)
        rel = os.path.relpath(lp, SRC).replace(os.sep, "/")
        rp = "/opt/xlogin/" + rel
        d = os.path.dirname(rel)
        if d:
            try:
                sftp.mkdir("/opt/xlogin/" + d)
            except IOError:
                pass
        sftp.put(lp, rp)
        print(" up:", rel)
sftp.put(ACCOUNTS, "/opt/xlogin/accounts.txt")
sftp.close()
_, out, _ = ssh.exec_command(
    "chmod 600 /opt/xlogin/accounts.txt && ls /opt/xlogin/ && python3 --version",
    timeout=60)
print(out.read().decode(errors="replace").strip())
ssh.close()
print("UPLOAD OK")
