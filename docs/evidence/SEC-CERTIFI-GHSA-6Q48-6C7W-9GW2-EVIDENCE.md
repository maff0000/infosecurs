# Security Maintenance Evidence — certifi GHSA-6q48-6c7w-9gw2

**WO:** `docs/work-orders/WO-SEC-CERTIFI-GHSA-6Q48-6C7W-9GW2.md`
**Base:** `main` @ `49ca43a9416c2c3426ea3b9b270cd80b30f086bd`

## 1. Trigger

`security/dependencies` failed on the post-merge check for `main` @ `49ca43a9...` (a documentation-only commit unrelated to this finding):

```
Found 1 known vulnerability in 1 package
Name    Version   ID                  Fix Versions
certifi 2026.7.22 GHSA-6q48-6c7w-9gw2 2026.10.19
```

`certifi` is a transitive dependency (via `requests`, pulled in by `django-allauth[socialaccount]`'s OAuth2 machinery — see `requirements.in`'s own comment on that extra) — not declared directly in either `.in` file, matching the precedent `pyjwt` remediation in `docs/delivery/BUILD-REPRODUCIBILITY.md`.

## 2. Correction

`pip-compile --generate-hashes --upgrade-package certifi` run against both `requirements.in` and `requirements-dev.in`, inside a container built from the exact currently-accepted Python digest (`python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`) — the same mechanism and container convention `docs/delivery/BUILD-REPRODUCIBILITY.md` already establishes.

**Exact diff — 3 lines changed in each file, nothing else moved:**

```diff
-certifi==2026.7.22 \
-    --hash=sha256:62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775 \
-    --hash=sha256:741e2c3b351ddf169a738da9f2c048608ff7f2c5cc02f1ebc6b118bb090d5d55
+certifi==2026.10.19 \
+    --hash=sha256:035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae \
+    --hash=sha256:42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b
     # via requests
```

Identical in both `requirements.txt` and `requirements-dev.txt`. No other package version or hash moved — confirmed by `git diff --stat` (6 insertions/6 deletions total, 3 per file).

## 3. Validation

- `pip-audit -r requirements.txt` / `-r requirements-dev.txt` (same pinned-digest container): `certifi` no longer listed as vulnerable.
- Real hash-verified install: `pip install --require-hashes -r requirements-dev.txt` into a clean venv succeeded; installed `certifi` confirmed `2026.10.19` via `importlib.metadata.version`.
- Full `ci/unit` suite (exact curated file list from `.github/workflows/ci.yml`), disposable stack (`certifisecfix`, ports 19990/19991): **870 passed, 0 skipped** in that disposable run. The real GitHub Actions `ci/unit` job for this same exact head reports **867 passed, 3 skipped** (870 collected, same total) - independently confirmed by re-reading that job's own log. The 3 skips are `questionnaire/tests/test_m009a_scanner.py::TestRealClamdBackend` (`test_ping`, `test_legitimate_xlsx_is_clean`, `test_eicar_test_file_is_detected`), which require a real reachable ClamAV daemon: the `ci/unit` GitHub Actions job deliberately runs only a `postgres` service (no `clamav`), so these three correctly skip there, while this dispatch's own disposable stack runs the full Compose stack including `clamav` and so exercised them for real. Both numbers are internally correct for their own environment; this is a known, intentional service-composition difference between the two jobs, not a regression or a discrepancy to resolve.
- Full `ci/integration` suite, same stack: **1292 passed, 7 skipped, 1 xfailed**, exact match to the known baseline, zero regression.
- `manage.py check`: no issues. `manage.py makemigrations --check --dry-run`: no changes detected.
- Disposable stack fully torn down (`docker compose -p certifisecfix down -v`) after use.

## 4. Separate, out-of-scope finding — disclosed, not actioned

The same `pip-audit -r requirements.txt` run (post-certifi-fix, against the real current dependency graph) additionally reports **8 known CVEs in `pillow==12.3.0`** (transitive, via `reportlab`): CVE-2026-112895, CVE-2026-112400, CVE-2026-112397, CVE-2026-112896, CVE-2026-112897, CVE-2026-112395, CVE-2026-112404, CVE-2026-112899, all fixed in `13.0.0`. **`pillow==12.3.0` was already the exact pin on canonical `main` @ `49ca43a9...` before this WO's own change** (confirmed directly: `git show 49ca43a9...:requirements.txt` shows the identical pin) — this WO's `--upgrade-package certifi` flag did not touch it. Per this WO's explicit "no unrelated package upgrades" restriction, `pillow` is **not** upgraded here. Reported separately to Central Architecture as its own, distinct finding requiring its own decision.

## 5. Persistent Beta exposure assessment — read-only, no compromise inferred

Checked directly, read-only, no writes/restarts/exec-env-dumps: `docker exec infosecurs-relocation-web-1 python -c "import importlib.metadata; print(importlib.metadata.version('certifi'))"` → **`2026.7.22`** — the persistent Beta's running container image does contain the affected version.

**TLS-client exposure implication, stated at the level actually verified**: `certifi` supplies the root CA bundle `requests`/`urllib3` use for TLS certificate validation on every outbound HTTPS call this application makes (notably the LiteLLM gateway calls referenced in `docs/delivery/M005-M006-HOST-RELOCATION-GATE.md`). The advisory's exact vulnerability mechanism is identified only as `GHSA-6q48-6c7w-9gw2`, fixed in `2026.10.19` — no further characterisation of the specific defect was independently obtained beyond what `pip-audit`'s own advisory lookup reports, and no evidence of actual exploitation or compromise was sought or found. This is an exposure-presence finding, not a compromise finding.

This exposure is **not remediated by this PR** — fixing it requires the persistent Beta's running image to actually change, which is explicitly out of scope here (no persistent Beta change authorised) and gated separately under the PID-DBR-001 deployment-boundary cutover process once that reaches its own authorised cutover.
