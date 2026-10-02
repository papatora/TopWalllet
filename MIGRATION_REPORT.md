# WalletIntel Migration Report

**Date:** 2026-10-01  
**Canonical project:** `C:\Users\ROG\Documents\ClaudeCode\AlphaIntel\WalletIntel`  
**Read-only source backup:** `C:\Users\ROG\Documents\ClaudeCode\SniperToken\TopWalllet`

## Result

The copied project is repathed for use from the canonical WalletIntel directory. The old backup remains present; all pre-existing contents are preserved. After the final forensic audit passed, only ARCHIVED_SOURCE.md was added to its root. It was not deleted or renamed. The copied repository has no Git remote configured; publishing and VPS access are disabled until a new WalletIntel target is approved.

## Repath and identity changes

- `config/settings.py` derives the default SQLite path from the copied repository root and keeps the existing `data/topwallet.db` filename. Publishing now defaults off and fails closed for an empty or legacy repository setting.
- The copied `.env` has `AUTO_PUSH_RESULTS=false`, an empty `GITHUB_REPO`, and disabled WalletIntel remote settings. A key-by-key comparison found only the intended changes to `AUTO_PUSH_RESULTS` and `GITHUB_REPO`, plus the three new remote settings; all prior secret-valued environment entries matched, and no values were printed.
- `scripts/_vps.py` blocks SSH until the WalletIntel remote is explicitly enabled and configured. Active VPS helpers now target `/opt/walletintel` and `walletintel-supervisor`.
- `setup.sh` requires an explicit `REPO_URL`, defaults the install directory to `/opt/walletintel`, and rejects the retired TopWallet repository. `docker-compose.yml` uses the WalletIntel project name, keeps the existing database/Redis volume names, and defaults automatic result publishing off.
- Five legacy deployment, credential-update, database-refresh, and forced-publish scripts now exit before their former executable bodies: `scripts/deploy_vps.py`, `scripts/deploy_fix.py`, `scripts/finish_s34.py`, `scripts/night_delta.py`, and `scripts/_vps_ops_once.py`. Details are in `scripts/LEGACY_WORKFLOWS.md`.
- Local scripts derive their root from `__file__`; `scripts/read_wazz_thread.py` now writes beneath this checkout. The CLI, API, explorer, launchers, and package metadata use the WalletIntel identity. Database filenames, log filenames, schema, and the `TOPWALLET_RUN_ENV` compatibility guard remain unchanged.
- The copied Git repository has no remotes or upstream configured. Its linked-worktree pointers now resolve within WalletIntel; `git worktree list` contains the main copy and its nested detached snapshot only.
- `.venv/pyvenv.cfg` and activation scripts were repathed without reinstalling packages. Eighteen console `.exe` wrappers that embed the former venv path were moved byte-for-byte to `.venv/legacy-launchers/`; its README explains they are archived. `.venv/Scripts` has no old-root literals in remaining executables.

## Desktop launchers

- Updated the Tauri, WinForms, and Electron launcher sources/configuration to WalletIntel identity and portable project-root discovery.
- Rebuilt the WinForms launcher with the existing Windows compiler and the Rust launcher with `cargo build --release --offline --locked`. No tools or dependencies were installed.
- Repointed the Desktop `TopWallet Launcher.lnk` target, working directory, icon, and description to the copied `desktop\TopWalletLauncher.exe`. The shortcut filename and executable filename remain for compatibility; the app UI identifies as WalletIntel.
- Renamed the Rust launcher INI to `walletintel-launcher.ini` and made its HTML path relative. Two release executable aliases were refreshed from the rebuilt binary.
- Both launchers passed `--check-config` from a temporary working directory and resolved `WalletIntel\Database Local only\html`; no server was started. The unrelated `Sniper.lnk` still targets `Sniperearly` and was not changed.

## Historical and generated references retained

These are intentionally non-operational and are listed so the remaining raw-string search hits are accounted for:

- The root `HANDOFF.md`, `PRE_COMPACT.md`, `ULTIMATE_PROMPT.md`, and `docs/ULTIMATE_PROMPT_SMART_MONEY_FEED.md` preserve pre-migration paths and commands. Each has a prominent historical/non-operational notice. All nine `docs/memory/*.md` snapshots are similarly labeled.
- `.claude/worktrees/clever-kilby-614c36` is a preserved detached historical worktree. Its Git link now points to the WalletIntel copy, and its README, archive note, and old handoff/prompt files mark it non-canonical and non-operational.
- All five saved Zcode workflow drafts and six run payloads were moved from active workflow directories to `.zcode/archive/legacy-workflow-drafts/` and `.zcode/archive/legacy-workflow-runs/`, with `.archived` suffixes. Their bytes were preserved; the archive README warns against execution.
- The five disabled scripts above retain their former VPS/repository commands below an unconditional first-statement `SystemExit`; do not remove the guards without a separate deployment review.
- The 18 old venv console launchers remain under `.venv/legacy-launchers/`, outside the active `Scripts` directory. Their bytes were preserved.
- The earlier text-only build-metadata scan counted 757 paths. The final full-byte scan identifies **1,150** preserved Rust target artifacts with legacy compilation/debug paths, including generated dependency metadata. They are not configured startup surfaces; the rebuilt launchers contain no old-root reference. Every hit is classified in the final forensic evidence.
- Git objects and main reflogs remain as historical repository data. Detaching the copied origin also removed its origin/main remote-tracking ref and corresponding remote-tracking reflog (and their empty origin directories); the legacy source retains them. Credential-bearing values were never displayed.
- Compatibility identifiers intentionally retained include `data/topwallet.db`, `logs/topwallet.log`, the Docker volume names `topwallet_pgdata`/`topwallet_redisdata`, `TOPWALLET_RUN_ENV`, and the shortcut/executable filename `TopWalletLauncher.exe`. None points to the old local checkout.

## Copy and preservation checks

- Before repathing, a full Robocopy dry-run compared the copied tree with its source: **2,964 directories and 20,176 files (7.155 GB), zero mismatches or failures**.
- After repathing, SHA-256 comparison covered 201 preserved data/export/explorer files: **194 were byte-identical**. The seven differences were intentional WalletIntel branding updates to `Database Local only/html/{assets/js/app.js,assets/js/views/guide.js,dataset.py,index.html,lookup_api.py,server.py,start.cmd}`. `data/topwallet.db`, `results/`, `logs/`, and `fomo_cookies.json` were byte-identical to the source copy.
- The original backup still exists with its own Git remote and original worktree registration. Migration writes targeted the WalletIntel copy and the authorized Desktop shortcut. The final forensic task additionally created only the authorized source-root archive marker after the audit passed.
- `results/night_escalation.json` and `results/no_shutdown.flag` were pre-existing untracked files and were preserved.

## Validation

- `python -m pytest -q -p no:cacheprovider`: **112 passed**, 2 existing dependency deprecation warnings. Pytest needed an elevated, project-local temporary directory because the sandbox denied its default temp location; that temporary directory was removed.
- In-memory syntax compilation passed for 123 Python files. CLI `--help`, config/CLI/API imports, JSON config parsing, and Electron `node --check` passed.
- Runtime settings resolve `REPO_ROOT` and `data/topwallet.db` under WalletIntel even when imported from another working directory. API import did not create a database engine.
- `scripts/_vps.py` guard was exercised and blocked before any network connection. Publishing guard checks with a Git stub made zero Git/network calls.
- WinForms and Rust launcher `--check-config` passed from outside the project root. No pipeline, browser/server, SSH session, live wallet/market action, deployment, push, or external service call was performed.
- Bash syntax validation was unavailable: the local `bash` command resolves to an access-denied Windows alias. Review `setup.sh` with `bash -n` on an approved Linux shell before a future deployment.

## Manual follow-up

Provide/approve the new WalletIntel Git remote and VPS target before setting `GITHUB_REPO` or enabling `WALLETINTEL_REMOTE_ENABLED`. No replacement remote was invented. If direct `pip.exe`, `pytest.exe`, or other archived console wrappers are needed, regenerate them for this venv or continue using `python -m ...`. Deleting the original TopWalllet backup remains a separate action and was not performed.

`CalloutTracker` was not opened or modified by this migration; its concurrent authorized task has populated it. `TokenSniper` was not opened or modified and remained empty at final verification.

## Final forensic acceptance — 2026-10-02

**PASS.** The complete saved SHA-256 inventory was refreshed against the current filesystem after the interruption. No new source files, stale hashes, unstable reads, unexplained differences, or unresolved read errors were found. Valid hashes were reused only after path/type/length/normalized modification-time checks; the completed tests and application checks were not rerun.

### Complete inventory and difference accounting

| Evidence before the archive marker | Legacy source | Canonical WalletIntel |
|---|---:|---:|
| Every regular file (including hidden/system entries) | 20,176 | 20,427 |
| Directories, including the root | 2,964 | 3,009 |
| Empty directories | 111 | 113 |
| Named alternate data streams | 0 | 0 |
| Reparse points | 0 | 0 |
| Unresolved file/stream/ACL inventory errors | 0 | 0 |

All **20,044 shared files expected to be unchanged match by SHA-256**, covering **7,665,168,210 bytes**. All source databases, browser-profile data, results, logs, cookies, installed dependencies, Git objects, and caches were included. The literal Windows file named `nul` was read with an extended path and hashed as a regular zero-byte file. The five protected pytest-cache files were included after a bounded elevated read.

Every one of the **464 prior migration path/content differences** has an explicit per-record justification in `classified_diffs.jsonl`: 100 modified files, 283 added files plus 47 added directories, and 32 removed files plus two removed directories. The 29 relocations (18 venv wrappers and 11 Zcode artifacts) retain their exact original hashes. Other differences are the documented source/configuration repath, historical notices, rebuilt launcher aliases, the renamed/repathed INI, local origin tracking removal, and generated artifacts from the offline Rust rebuild. All 111 original empty directories remain present and empty; the two additional empty directories are the retained Git remote parent directories after origin detachment. **Unaccounted differences: zero.**

Readable owner/group, DACLs, attributes, streams, and timestamps were inventoried for every path. Common attributes, owners, and groups match. There are 1,177 enumerated DACL differences (1,169 under data/browser profiles and eight pytest-cache entries), explained by destination ACL inheritance under the original `/COPY:DAT /DCOPY:DAT` copy; the source ACLs remain preserved in the backup. The 152 modification-time/empty-state differences and one creation-time difference are justified by migration edits, child changes, and the Git configuration replacement. The 22,680 last-access differences are informational because copying and reading files can update access times. SACL probes on both roots and representative files were denied due to absent `SeSecurityPrivilege`; no inaccessible SACL is claimed to have been compared.

### Operational reference gate

The active source/configuration surfaces have **zero old-root or old SniperToken parent references**. The copied Git worktree registrations and Desktop shortcut target/working directory/icon resolve to WalletIntel; there are no copied Git remotes. The remaining active venv executables and rebuilt launchers have zero old-root hits.

The full byte scan included case-insensitive slash variants, escaped JSON paths, and UTF-16 in both byte orders. Its 3,884 canonical filename hits were all classified as non-operational: 2,556 preserved dependency bytecode caches, 90 other Python caches, 1,150 Rust generated artifacts, 18 quarantined wrappers, 51 historical browser logs, five historical runtime logs, nine labeled historical documents, four archived workflow payloads, and this migration report. **Unclassified or active operational hits: zero.** Filename-only evidence records contain no secret values.

### Sole post-audit source addition

Only after the acceptance gate passed, `ARCHIVED_SOURCE.md` was added to the legacy source root. It identifies WalletIntel under AlphaIntel as canonical and warns that existing Z-Code sessions remain attached to the old path; new work must start from the canonical project.

The post-marker check passed: the source gained exactly one 592-byte file and now has 20,177 regular files. All 20,176 pre-existing SHA-256 hashes remain valid; no pre-existing content/type/length, attributes, readable ACLs, alternate streams, creation times, or modification times changed. There were no removals or other additions. Only the parent root modification time changed automatically. Valid source hashes were reused as authorized; only the new marker was hashed. Its SHA-256 is `362679a6ebbbc85eb7a131e382db3ffb02f70c587767cb7148b87f60328fbec0`.

This report refresh is the only canonical-project write made by the final forensic task. The legacy-only marker is an explicit post-audit addition, not a missing canonical project file. No folder was deleted or renamed, and no network/VPS/deploy/push/server/pipeline/scraping/trading action was run.

### Complete machine-readable evidence

The evidence directory is `C:\Users\ROG\AppData\Local\Temp\walletintel-forensic-20261001-233744-beb85af7`. It is outside both project trees. The complete manifests and every classified path/metadata/reference record are available here:

- [All source files and directories](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/source.jsonl) and [all canonical files and directories](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/canonical.jsonl).
- [Every modified/added/removed/relocated path with hashes and justification](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/classified_diffs.jsonl).
- [Every readable ACL/attribute/modification-time/empty-state difference](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/classified_metadata_diffs.jsonl) and [supplemental creation/access/modification timestamp differences](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/classified_timestamp_diffs.jsonl).
- [Every retained old-root hit and classification](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/classified_old_root_hits.jsonl).
- [Post-marker source inventory](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/source_post_marker.jsonl), [source-preservation result](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/post_marker_summary.json), and [pre-existing creation-time result](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/post_marker_timestamp_summary.json).
- [Evidence checksums](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/evidence_checksums.json) and [final report/marker completion ledger](C:/Users/ROG/AppData/Local/Temp/walletintel-forensic-20261001-233744-beb85af7/audit_completion.json).