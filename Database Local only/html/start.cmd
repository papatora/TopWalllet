@echo off
rem TopWallet explorer — local only. Opens http://127.0.0.1:8787
cd /d "%~dp0"
python server.py --port 8787 --open
pause
