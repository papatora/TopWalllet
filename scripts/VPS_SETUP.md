# VPS autonomy setup (jalankan SETELAH setup.sh, sebagai root di VPS)

## 1. systemd service — supervisor auto-restart + auto-start on boot
```bash
cat > /etc/systemd/system/topwallet-supervisor.service << 'EOF'
[Unit]
Description=TopWallet overnight supervisor
After=network-online.target docker.service

[Service]
WorkingDirectory=/opt/topwallet
Environment=TOPWALLET_RUN_ENV=vps
ExecStart=/opt/topwallet/.venv/bin/python scripts/supervisor.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now topwallet-supervisor
systemctl status topwallet-supervisor --no-pager
```

## 2. crontab — hourly LLM watchdog (independent of supervisor; can revive it)
```bash
( crontab -l 2>/dev/null; echo "0 * * * * cd /opt/topwallet && TOPWALLET_RUN_ENV=vps .venv/bin/python scripts/watchdog.py >> logs/watchdog_cron.log 2>&1" ) | crontab -
crontab -l
```

## 3. Verifikasi
```bash
systemctl is-active topwallet-supervisor          # active
tail -5 /opt/topwallet/logs/supervisor.log        # cycle progress
tail -5 /opt/topwallet/results/night_watch.log    # hourly GLM verdicts (OK/PROBLEM)
cat /opt/topwallet/results/supervisor_status.json # heartbeat (updated_at bergerak)
```

## Cara kerja lapisannya
- **supervisor (systemd)**: loop pipeline enrich→prices→analyze, resume otomatis, crash → Restart=always.
- **watchdog (cron 1 jam)**: kumpulkan fakta keras (proses hidup? heartbeat <30 menit?) → injek ke GLM-5.3-flash → verdict JSON. Kalau ada yang mati/stuck → eksekusi restart (whitelist). Kalau semua jalan walau pelan → cukup catat OK.
- Dua lapis independen: watchdog bisa membangunkan supervisor yang mati; systemd membangunkan supervisor yang crash; checkpoint DB membuat pipeline lanjut dari posisi terakhir.
