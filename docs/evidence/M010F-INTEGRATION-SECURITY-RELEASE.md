# M010F — Integrated Acceptance, Independent Challenge Preparation and Release Boundary

**Milestone:** M010 — IRENE AI Security Adviser and Shared Security Tasks (Work Package F of 6, final)
**Parent PID:** `docs/pids/M010F-INTEGRATION-SECURITY-RELEASE.md`
**Campaign PID:** `docs/pids/M010-IRENE-MASTER-PID.md`
**Implementation branch:** `wo/M010F-integration-security-release`
**Base:** `37c2b93` (`wo/M010-irene-ai-first-campaign`, the M010E merge onto the integration branch — the tip after Work Packages A-E were all independently reviewed and merged by the Delivery Controller)
**Isolation:** built entirely in the assigned worktree
(`/srv/openclaw/worktrees/wo/M010F-integration-security-release` on host
`dell-debian`) and a disposable Docker Compose stack (`--project-name
m010f`, `POSTGRES_HOST_PORT=25632`, `WEB_HOST_PORT=28600`) — the
canonical bare clone `/srv/infosecurs`, the Delivery Controller's own
integration worktree `/tmp/m010-integration`, and every other running
stack on the host (`infosecurs-relocation`, `m008ewi1design`,
`auditpr97`, etc.) were never touched. A second, temporary restore-target
project (`m010fr`) was created and fully torn down (`docker compose -p
m010fr down -v`) during the backup/restore proof in §4.

## 0. Non-negotiable scope boundary — confirmed held

This package does **not** itself run the "fresh independent Auditor"
dispatch the governing PID's §3 describes (a separate, later, genuinely
fresh agent pointed only at the canonical repo and PIDs) — that remains a
distinct, future dispatch. This package also does not merge into
`wo/M010-irene-ai-first-campaign` or `main`, does not deploy anywhere, and
does not touch any persistent Customer Zero instance — confirmed: no
`docker exec`/`docker compose` command anywhere in this dispatch targeted
`infosecurs-relocation` (the persistent Customer Zero stack) or any volume
belonging to it; only the disposable `m010f`/`m010fr` projects' own named
volumes were created, read or removed. M009B Increments 3-4 (bulk
orchestration, claim ledger) were independently re-verified absent from
the codebase (§2 below) and are not touched or implemented here.

## 1. Integration completion (PID §1) — what was actually checked, and how

### 1.1 Fresh Django/PostgreSQL setup

`docker compose --project-name m010f up -d` against a brand-new, empty
Postgres 16.6 volume; `web`'s own startup command (`migrate --noinput &&
runserver`) applied all 67 migrations across every app, M010's four
(`entitlements.0005`/`0006`, `security_tasks.0001_initial`,
`foundations_journey.0001_initial`, `irene.0001_initial`) included, with
no error. `makemigrations --check --dry-run` immediately afterward:
`No changes detected`.

### 1.2 Migration reverse/roll-forward

Every M010-introduced migration was reversed, then re-applied, against
the real running Postgres:

```
python manage.py migrate irene zero                                    # OK
python manage.py migrate foundations_journey zero                      # OK
python manage.py migrate security_tasks zero                           # OK
python manage.py migrate entitlements 0004_foundations_real_destination # OK (unapplies 0006, then 0005)
python manage.py migrate                                               # OK - re-applies 0005, 0006, security_tasks.0001,
                                                                         #      foundations_journey.0001, irene.0001, in that order
```

`showmigrations` before/after round-trip confirmed identical final state.
No other app's migrations were touched (M008/M009 migrations were never
part of this round-trip). See §2 of the governing PID's release section
and `M010F-RELEASE-OPERATIONS-DRAFT.md` (draft) §2 for why this round-trip
proves the rollout is expand/contract-safe.

### 1.3 ProductArea seeds — exact count and content re-verified directly

Queried the live `entitlements.ProductArea` table on the fresh stack:
**18 rows** — the pre-existing 16 (`home`, `foundations`,
`customer_assurance`, `security`, `security_state`, `baseline`, `assets`,
`risks`, `evidence`, `remediation`, `policies`, `company`, `profile`,
`governance`, `workplace`, `activity`) plus exactly the two M010A seeded
(`tasks`, `irene`), matching `entitlements/migrations/
0005_seed_tasks_and_irene_product_areas.py`'s own docstring claim
("INSERTS exactly two new rows... touches nothing else") exactly. Diffed
`entitlements/migrations/0005_seed_tasks_and_irene_product_areas.py` and
`0006_irene_real_destination.py` against `main` directly (not merely
cited from an earlier package's evidence) — both are additive-only, with
an explicit `unseed_*` reverse function identified by `code`, never a
blanket delete.

### 1.4 M008 Stage 4 and M009 code genuinely untouched — re-derived directly

`git diff $(git merge-base HEAD origin/main) HEAD -- questionnaire/
security_baseline/ policy/` (the M009 ingestion app, the M008 Stage-4
baseline app, and the M008D policy app): **zero file changes** in any of
the three. The only files this whole M010 campaign touched outside its
own three new apps (`security_tasks`, `foundations_journey`, `irene`) are
the expected, additive integration points:

- `entitlements/capabilities.py` — three new `ROUTE_NAMESPACE_TO_CAPABILITY`
  dict entries (`security_tasks`→`tasks`, `foundations_journey`→`security`,
  `irene`→`irene`), nothing removed or altered.
- `entitlements/migrations/0005_*.py`/`0006_*.py` — additive seed rows (§1.3).
- `organisations/reset_service.py` — the M008A-established reset manifest
  extended with M010's three new tenant-owned model classes (read
  directly: each addition only adds entries to `EXPECTED_DELETE_DIRECT_FK_
  MODELS`/`reset_customer_zero_organisation`, nothing pre-existing
  altered).
- `organisations/templates/organisations/detail.html` +
  `organisations/views.py` — the Home template/view gains one new
  `irene` context variable and a conditionally-rendered modal include;
  the rest of the view's own pre-existing behaviour (confirmed by reading
  the full diff) is untouched.
- `entitlements/tests/*` — new/extended tests only, confirmed by reading
  the diff: `test_navigation.py`, `test_root_conftest_reseed_includes_
  0005.py` (new file), `test_seed_data.py` (extended, old assertions kept).

No `security_baseline`, `questionnaire`, `policy`, `risk_register`,
`key_assets`, `evidence`, `remediation`, `governance`, `workplace`,
`activity`, or `identity` file was touched by any M010 package. M008
Stage 4 (the 12-control structured baseline question flow) and M009
(questionnaire ingestion/readiness) run on exactly the same code M010
found them in.

### 1.5 Feature flag OFF behaviour

Re-ran `irene/tests/test_http_ui.py::TestAutoOpenPreference::
test_manual_app_works_with_irene_disabled` directly against this stack:
PASS — Home returns 200 with no `irene-modal` markup when
`IRENE_ENABLED=False`, and the manual Tasks sidebar page remains fully
reachable (200). `IRENE_ADVISER_MODE_ENABLED` already defaults `false`
in every environment (§6/`config/settings.py`) — there is no "ship it on
then disable" step; it has never been enabled for anything but a test.
`IRENE_TASK_TOOLS_ENABLED`/`IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED`
OFF behaviour is directly proven by `irene/tests/test_tools.py` and
`irene/tests/test_customer_assurance_tools.py::test_disabled_flag_denies_
via_call_tool_dispatch` respectively (re-run as part of §5's full suite
run below).

### 1.6 Backup/restore

Full backup/restore cycle run against this exact stack (`scripts/
backup.sh`/`scripts/restore.sh`, M006 PID §14 tooling, unmodified) — see
§4 below for the full transcript and result.

### 1.7 M009B state — re-verified absent, independently

Searched the live working tree directly for every concrete artefact
`docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md`
describes for Increments 3/4: no `questionnaire/bulk_orchestration.py`
file exists; no `QuestionnaireBulkResponseAttempt` model; no
`claim_next_eligible_question`/`CLAIM_TTL` symbol anywhere in `.py` code
(only in that Work Order's own planning prose). `git branch -a` shows
only `wo/M009B-increment1-readiness-csv` and `wo/M009B-increment2-m005-
prepare-persist` branches/closures — no increment-3/4 branch exists.
**M009B Increments 3-4 remain genuinely not started.** This evidence
document and the draft handoff materials in `M010F-RELEASE-OPERATIONS-DRAFT.md`
make no claim that they are.

## 2. Acceptance matrix and customer scenarios (PID §2/§4) — real traceability

See `docs/evidence/M010-EVIDENCE-INDEX.md` for the consolidated,
file:line-cited traceability table across all of M010A-F. Summary: every
F01-F12 row and all 8 customer scenarios already have real, executable
positive AND negative/adversarial fixtures built by the owning A-E
package (not invented fresh here) — this package's own job was to
re-run them for real against a fresh stack (§5) and to close the two
genuine coverage gaps found in the process (§6).

## 3. Independent verification plan (PID §3)

Out of scope for this Implementer dispatch by design — see the governing
PID's own division of labour and this dispatch's brief §"What 'Gunnar'
does vs. what you do". Nothing in this document should be read as that
Auditor pass; `docs/evidence/M010-EVIDENCE-INDEX.md`'s traceability table
is this package's preparation FOR that later, separate, genuinely fresh
dispatch, not a substitute for it.

## 4. Backup/restore — full transcript and result

Ran against the live `m010f` stack (`COMPOSE_PROJECT_NAME=m010f bash
scripts/backup.sh /tmp/m010f-backup-test`):

```
Infosecurs backup starting: 20261018T192613Z
Source Git SHA: 37c2b93b8784f423ecbdcdb7b889f7b63a1434fc
Stopping web service (quiescing writes)...
Dumping database 'infosecurs' (logical dump via pg_dump)...
Archiving evidence volume...
Archiving questionnaire-storage volume...
Restarting web service...
Backup complete.
```

Manifest (`manifest-20261018T192613Z.json`) recorded SHA-256 checksums
for the DB dump and both archives.

Restored into a genuinely fresh, separate project (`scripts/restore.sh
/tmp/m010f-backup-test m010fr /tmp/m010f-restore.env`, distinct ports
25633/28601, brand-new named volumes):

```
Verifying archive checksums against manifest before restoring... OK
Bringing up fresh disposable stack (project: m010fr)...
Restoring logical DB dump into fresh database 'infosecurs'...
Un-tarring evidence archive into fresh evidence volume...
Un-tarring questionnaire-storage archive into fresh questionnaire volume...
Bringing up web and applying migrations (proves schema compatibility)...
Operations to perform:
  Apply all migrations: ...
Running migrations:
  No migrations to apply.
Restore complete. Stack is running under project 'm010fr'.
```

Verification against the restored stack: `GET /healthz/` → `200`;
`entitlements.ProductArea.objects.count()` → `18`, including `tasks` and
`irene` — confirming the M010 seed rows survive a genuine backup/restore
cycle, not merely the live stack. Torn down immediately after
(`docker compose -p m010fr down -v`) — all four `m010fr_*` volumes
removed, `m010fr_default` network removed. The live `m010f` stack and its
`.env` were restored to their pre-backup state automatically by
`restore.sh`'s own documented `.env` swap/restore behaviour — confirmed:
`grep HOST_PORT .env` after teardown showed the original `m010f` ports
unchanged.

**One operational note for the draft runbook, not a defect**: `scripts/
backup.sh`/`restore.sh` resolve the Compose project by `docker compose
ps`/`docker compose run` without an explicit `-p` flag, so they require
either running from a shell where `COMPOSE_PROJECT_NAME` is exported to
match the stack's actual `--project-name`, or being invoked from a
directory whose Compose default project name already matches. This
dispatch's own first `backup.sh` invocation (without that export) failed
closed with a clear `'db' service is not running` error rather than
silently acting on the wrong stack — re-run correctly with
`COMPOSE_PROJECT_NAME=m010f` exported, which succeeded. Worth a one-line
callout in the operator runbook (included in the draft, §1 preamble).

## 5. Full regression evidence — exact commands and results

All four runs below were executed against the SAME stack used throughout
this dispatch, container had `playwright install --with-deps chromium`
run inside it first (per this dispatch's own binding security rule — the
Dockerfile never bakes Chromium in).

### 5.1 `ci/unit` — exact file list from `.github/workflows/ci.yml`, post-fix

```
docker compose --project-name m010f exec -T web pytest -q <exact ci/unit file list>
```

Result: **811 passed, 1 warning (benign zipfile duplicate-name warning
from a deliberately hostile XLSX test fixture), 335.03s.** Matches the
architect-supplied running baseline exactly (811 — see M010E's own
evidence doc §7.4 baseline arithmetic).

### 5.2 `ci/integration` — exact file list from `.github/workflows/ci.yml`

```
docker compose --project-name m010f exec -T web pytest -q <exact ci/integration file list>
```

**First attempt — self-inflicted contamination, disclosed and corrected
(not a product defect):** while this run was in flight, this Implementer
separately started a second, concurrent `pytest -q entitlements/tests/`
invocation against the SAME shared `test_infosecurs` reused database
(§6.3 below has the full story). Result: **1 failed, 1291 passed, 7
skipped, 1 xfailed, 14 errors, 1283.11s (0:21:23)** — one
`entitlements/tests/test_metrics.py` posture assertion failed in the
concurrent run (separate, see §6.3), and 14 browser/narrow-viewport tests
in `core/tests/`/`organisations/tests/test_narrow_viewport_regression.py`
either failed (`Locator.bounding_box: Timeout 30000ms exceeded` on
`#shell-sidebar`) or errored (`Database test_infosecurs couldn't be
flushed` — a `TransactionTestCase`-style flush colliding with the OTHER
process's own concurrent write/truncate activity against the same
database). **Re-ran all 15 affected tests again, in complete isolation
(nothing else running against the stack): 19 passed, 121.10s, 0
failures, 0 errors** (`core/tests/test_wi6_home_foundations_browser_
acceptance.py core/tests/test_badge_narrow_viewport_regression.py
core/tests/test_responsive_text_regression.py organisations/tests/
test_narrow_viewport_regression.py`) — conclusively confirming this was
contention/contamination from running two `pytest` processes
concurrently against one shared database, never a real regression. A
full third end-to-end re-run of the entire `ci/integration` list was not
repeated (time budget; the isolated re-run directly reproduces and
clears every single anomaly the first run produced, and no OTHER test
outside those 15 showed any symptom of contamination). **Net result:
every `ci/integration` test that actually ran, ran correctly; the only
failures were an artefact of this Implementer's own test-running
discipline, not of the code under test.**

### 5.3 `makemigrations --check --dry-run`

`No changes detected` (§1.1).

### 5.4 Security/dependency scans

- `gitleaks detect --source . --config .gitleaks.toml --no-git -v` (run on
  the host directly, not inside the container — gitleaks is a filesystem
  scanner): `no leaks found`, ~7.41MB scanned.
- `pip-audit -r requirements.txt` (pinned `pip-audit==2.10.1`, matching
  `.github/workflows/security.yml`'s own pin, installed into a throwaway
  venv inside the container): `No known vulnerabilities found`.
- `security/sast` (CodeQL) and `security/container` (Trivy, application +
  ClamAV image) are GitHub-Actions-only jobs (`.github/workflows/
  security.yml`) that cannot be run standalone against a local stack in
  the same way — confirmed the workflow file itself exists, is correctly
  pinned (explicit digest/version pins throughout, not floating tags),
  and already covers exactly the four security checks the governing PID
  §5 names (`security/secrets`, `security/dependencies`, `security/sast`,
  `security/container`) plus CodeQL. **This answers the brief's open
  question directly: CodeQL/security scanning workflows already exist in
  this repository (`.github/workflows/security.yml`) — this is not a gap
  requiring a separate gate.** Whether they have actually been GREEN on
  the real GitHub Actions runners for this exact branch's HEAD is a fact
  only GitHub's own check-run API can state (push-trigger semantics: both
  workflows trigger on `push: branches: [main]` and on `pull_request` —
  so they will not have run automatically against this feature branch's
  intermediate commits; they run once a PR is opened against `main`).

## 6. Genuine findings during verification (fixed, not worked around)

### 6.1 `foundations_journey/tests/test_parity_golden_set.py` never wired into CI

The single most important proof for F01/F03/F04 (57-case manual-vs-IRENE
golden-set parity, M010B's own words: "the single most important result
in this package") has never run in `.github/workflows/ci.yml`, across the
entire branch history, despite M010B's own evidence document explicitly
flagging it as a pending CI-wiring decision and a LATER dedicated commit
(`cc32c39`, "Wire security_tasks/foundations_journey/irene tests into
CI") resolving the equivalent gap for every other new test file —
`test_parity_golden_set.py` was simply missed by that commit and never
picked up by any subsequent package's own `ci.yml` update (M010D/M010E
each only added their OWN new files). Fixed: added to `ci/unit` (the file
needs no `transaction=True`/Chromium fixture — confirmed by direct read —
exactly where M010B's own evidence doc proposed it should go). Re-run
standalone post-fix: **59 passed**. See commit `ecfcadb`.

### 6.2 New IRENE-owned form pages not covered by the mechanical accessibility regression net

`organisations/tests/test_form_labels.py` (the repo's stdlib-only "every
form control has a label" CI check, M006 PID §9/§22) swept every
pre-M010 form page but neither `security_tasks:create` nor the IRENE
modal's own Ask-tab form (rendered as part of Home). Direct template read
confirmed BOTH were already correctly labelled by their own Implementers
(`security_tasks/templates/security_tasks/form.html` lines 17-31,
`irene/templates/irene/_modal.html` lines 91-93) — this is a coverage
gap in the regression net, not a markup defect, but meant a future
regression on either page would never be caught by CI. Fixed: two new
test methods added. Re-run standalone post-fix: **13 passed** (11
original + 2 new). See commit `ecfcadb`.

Both fixes are narrow, additive, and do not touch any A-E package's own
design decisions — per this dispatch's own explicit instruction not to
re-implement or second-guess already-reviewed work.

### 6.3 This Implementer's own process mistake: concurrent `pytest` invocations against one shared database (disclosed, corrected, no code defect)

While the `ci/integration` run in §5.2 was in flight, this Implementer
separately started `entitlements/tests/` (a regression check mirroring
M010A's own established "run `entitlements/tests/` separately - not in
either curated CI list" practice) as a SECOND, concurrent `pytest`
invocation against the same running container and the same reused
`test_infosecurs` database. `entitlements/tests/test_root_conftest_
reseed_includes_0005.py` performs a real, committing `TRUNCATE
entitlements_productarea CASCADE` under `transaction=True` as part of its
own (pre-existing, not-M010F-authored) proof technique; running that at
the same moment as another process's own fixtures/queries against
overlapping tables produced: one failed assertion in `entitlements/
tests/test_metrics.py::TestPosture::test_all_missing_answers_treated_
identically_to_unknown` (`available_points` read back as `0` instead of
`38` — consistent with `FoundationRequirement` rows being transiently
absent mid-TRUNCATE-CASCADE from the organisations's own concurrent read)
and the 14 `ci/integration` anomalies in §5.2. **Both re-ran clean in
isolation** (§5.2's 19/19; `entitlements/tests/` alone: **305 passed,
192.02s**, vs. 304 passed/1 failed when run concurrently). This was this
Implementer's own test-running discipline error — never run two `pytest`
invocations against the same shared reused database concurrently, even
in a disposable stack with nothing externally at risk — disclosed here
in full rather than silently re-run and forgotten, per this campaign's
own established culture of distinguishing a genuine finding from a
methodology mistake.

## 7. Honest disclosures — what remains aspirational or undone

- **No OS-level cron/leader-election wiring exists for the review
  scheduler** — disclosed by M010D's own evidence document already;
  re-confirmed directly here (§3 of `M010F-RELEASE-OPERATIONS-DRAFT.md`, draft).
  A concrete, idempotency-grounded deployment recommendation is drafted
  but not yet Architect-accepted.
- **No accessibility tooling equivalent to axe-core exists in this repo**
  — the established "axe or equivalent" per the governing PID §5 is the
  repo's own stdlib `core/tests/html_a11y.py` form-label checker, a
  genuinely narrower mechanical check (labelled form controls only — not
  colour contrast, ARIA role correctness beyond what's hand-coded, focus
  order beyond the dedicated keyboard-walk Playwright tests, or screen-
  reader announcement correctness). The existing keyboard/focus-trap
  Playwright tests (`core/tests/test_wi6_keyboard_accessibility_browser_
  acceptance.py`, extended by M010C for the modal's own Escape/focus-trap
  behaviour) cover a different, complementary slice. A genuine axe-core
  (or equivalent real accessibility-engine) pass against the IRENE-owned
  pages specifically has NOT been built in this dispatch — adding a new
  JS dependency/tool to the project is a bigger decision than this
  dispatch's narrow-fix mandate covers, and is flagged here rather than
  silently claimed done.
- **`M010F-RELEASE-OPERATIONS-DRAFT.md` is a draft** — explicitly not finalised
  into the canonical `docs/runbooks/`/`PID.md`/`docs/ROADMAP.md` tree; per
  the governing PID §7, that finalisation is Gunnar's own job, after the
  separate Independent Audit.
- **The real "fresh independent Auditor" pass (PID §3) has not happened**
  — nothing in this package should be read as that verdict.
- Production deployment, real customer data, DPIA/hosting/trademark
  clearance remain untouched and unaddressed here, exactly as the
  governing PID requires.

## 8. STOP-condition self-check (`docs/architecture/M010-SECURITY-THREAT-MODEL.md` §8)

None triggered during this dispatch: no cross-tenant leak (every query run
during this dispatch was either read-only shell inspection against the
disposable stack's own synthetic seed data, or the standard test suites'
own existing tenant-isolation assertions); no protected action invoked
without an independent server grant; no secret printed to any tool/log
(the two absolute rules against `docker inspect .Config.Env`/`env | grep`
were held throughout — every env-var check in this dispatch was indirect,
via `grep` for a literal key NAME in `.env`/`docker-compose.yml`, never a
value dump); no prompt-content instruction overriding app policy; no
unexpected destructive mutation (two near-misses, both this
Implementer's own process discipline errors rather than anything
touching real data or any other stack: (1) running `scripts/backup.sh`
while a `pytest` run was mid-flight inside the same container, which
stopped/restarted `web` and killed that run with SIGKILL — cost a wasted
test run, not data loss or a wrong result; (2) running a second,
concurrent `pytest` invocation against the same shared reused test
database as a first, in-flight run — produced 15 transient
contamination-induced anomalies, all re-verified clean in isolation, see
§6.3. Both cost time, not correctness, and both are disclosed in full
rather than silently re-run and forgotten); no canonical form validation
disabled; no
unbounded model-call loop (zero `IRENE_ADVISER_MODE_ENABLED=true` calls
were ever made — this dispatch made no live AI-gateway call at all); no
invented control assertions.

## 9. Teardown

`docker compose --project-name m010f down -v` run at the end of this
dispatch (see final command log) — all `m010f_*` volumes and the
`m010f_default` network removed; `m010fr` was already torn down in §4.
No other host stack (`infosecurs-relocation`, `m008ewi1design`,
`auditpr97`, etc.) was ever started, stopped, or touched.
