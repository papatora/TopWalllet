# Legacy VPS and publishing workflows

The following scripts are retained for historical review and have an
unconditional `SystemExit` before any executable body. Do not remove that guard
or run the old workflow without a separately reviewed WalletIntel deployment:

- `deploy_vps.py` — previous install flow, repository, and live pipeline start.
- `deploy_fix.py` — previous VPS reset/reinstall and supervisor restart.
- `finish_s34.py` — previous local database mutation, credential read, and VPS restart.
- `_vps_ops_once.py` — previous forced Git bundle/publish flow.
- `night_delta.py` — previous VPS data extraction, local database rebuild, and publish flow.

Other SSH helpers use `/opt/walletintel` and `walletintel-supervisor`, but
`scripts/_vps.py` refuses connections unless the user explicitly enables and
configures a new WalletIntel target. Current `.env` keeps that gate disabled.
`setup.sh` requires a new `REPO_URL` and rejects the retired TopWallet remote.
No deployment, SSH session, publish, or pipeline was run during migration.
