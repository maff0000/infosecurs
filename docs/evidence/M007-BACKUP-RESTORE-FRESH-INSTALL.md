# M007-WI6 — Backup/Restore Regression & Fresh-Clone/Fresh-Volume Proof

**Authorising commit (final merged M007 source, WI1-WI6 regression/browser
work landed):** `0bd53674279e71918701367279dcc0241f5a7937` (`main`)
**Scope:** M007-WI6 — full regression / release / fresh independent audit
(PROOF work item). Both proofs below were run directly by the PL against
real disposable Docker Compose stacks on dell-debian, never against the
canonical `/srv/infosecurs` checkout's own running state, and never
against `infosecurs-relocation` or any other stack already running on the
host.

---

## Part 1 — Backup/restore regression (PID's own established contract)

**Method:** `docs/runbooks/BACKUP-RESTORE.md`'s existing, unmodified
procedure (`scripts/backup.sh` / `scripts/restore.sh`) — no new backup
architecture invented, per this WI's own "do not invent a new backup
architecture" constraint. Source project `m007wi6bkpsrc` (ports
`19902`/`19801`), restore-target project `m007wi6restore1` (ports
`19903`/`19802`) — both disposable, both torn down (`down -v`) after use.

### Setup
- `python manage.py seed_backup_restore_fixture` — the established M006
  synthetic-organisation fixture (a real uploaded evidence file, an
  approved `PolicyVersion` that superseded an earlier approved one, an
  accepted `QuestionnaireResponse` that superseded an earlier accepted
  one).
- Additionally, for this M007-era proof specifically: two real
  `BaselineAnswer` rows added to that same organisation
  (`mfa_user_accounts=yes`, `patching=partial`), so
  `entitlements.metrics.get_foundational_security_posture` has real,
  non-trivial state to compare pre/post restore.

### Source-side state recorded before backup
```
ProductArea count: 16
FoundationRequirement count: 18
Foundations ProductArea destination_view_name: organisations:foundations
SOURCE posture percentage: 14
Evidence file SHA-256: 29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3
```

### Backup
`scripts/backup.sh backups/wi6-backup` — real output:
```
Infosecurs backup starting: 20260928T172747Z
Source Git SHA: 0bd53674279e71918701367279dcc0241f5a7937
Stopping web service (quiescing writes)...
Dumping database 'infosecurs' (logical dump via pg_dump)...
Archiving evidence volume...
Restarting web service...
Backup complete.
```
`Source Git SHA` in the manifest correctly matches the exact canonical
`main` SHA this proof ran against.

### Restore
`scripts/restore.sh backups/wi6-backup m007wi6restore1 .env.bkprestore` —
real output (relevant excerpt):
```
Bringing up web and applying migrations (proves schema compatibility)...
Operations to perform:
  Apply all migrations: account, activity, admin, ai_platform, auth,
  contenttypes, entitlements, evidence, governance, key_assets,
  organisations, policy, questionnaire, remediation, risk_register,
  security_baseline, sessions, sites, socialaccount, workplace
Running migrations:
  No migrations to apply.
Restore complete.
```
"No migrations to apply" on the restored stack — the schema-compatibility
proof the runbook's own doctrine requires.

### Restored-side verification, every check in the runbook's table
| Check | Result |
|---|---|
| App starts | `web` container `Up`, migrate reported clean |
| Migrations/schema compatible | "No migrations to apply" (above) |
| Representative organisation/domain records restored | `Organisation` row present, exact same id/name |
| M007 governed rows restored | `ProductArea` count **16** (matches source exactly), `FoundationRequirement` count **18** (matches source exactly), Foundations `destination_view_name` still `organisations:foundations` |
| Baseline answers restored | Both `BaselineAnswer` rows present, identical values |
| Metric methodology reproducible post-restore | `get_foundational_security_posture` on the restored copy: **14%** — byte-identical to the source-side 14% computed before backup |
| Evidence bytes/checksum identical | Restored file's own SHA-256: `29c1b4fc01831a1fc5b69e66d9df82f3b0ac79549866fe7a68d2eb63e2eac8b3` — **identical** to the source-side hash recorded above, compared directly (not merely re-hashed alone) |
| Policy history intact | `[(1, 'superseded'), (2, 'approved')]` — both versions present, correct statuses |
| Accepted questionnaire history intact | `['superseded', 'accepted']` — both responses present, correct statuses |
| Health 200 | `curl http://localhost:19802/healthz/` → `200` |

**Result: GREEN.** M007's own governed product/methodology tables
(`ProductArea`, `FoundationRequirement`) restore correctly alongside every
pre-existing M006 domain table the runbook's contract already covered, and
the Foundational Security Posture metric recomputes identically from the
restored rows — proving the "derived, never stored" methodology doctrine
survives a real backup/restore cycle, not just a live database.

Both stacks torn down (`down -v`), `backups/wi6-backup` deleted, the
canonical `/srv/infosecurs` checkout's own `.env` restored to its
pre-existing content afterward (backed up before use, restored after) —
`git status --short` on the canonical checkout confirmed clean (only the
pre-existing, expected untracked `docker-compose.override.yml`) once this
proof finished.

---

## Part 2 — Fresh clone / fresh volume proof

**Method:** a genuinely independent `git clone` of
`https://github.com/maff0000/infosecurs.git` into `/tmp/infosecurs-fresh-
clone` — a separate object store entirely, not a `git worktree` of the
existing checkout — confirmed `git rev-parse HEAD` ==
`0bd53674279e71918701367279dcc0241f5a7937` immediately after cloning.
Fresh disposable Docker Compose project `m007freshclone` (ports
`19904`/`19803`), fresh named volumes created by Compose itself (never
reused from any other project).

### Build + migrate from zero
`docker compose -p m007freshclone up -d` — the container's own startup log
confirmed every migration applying in order from an empty database,
including all four `entitlements` migrations:
```
Applying entitlements.0001_initial... OK
Applying entitlements.0002_seed_product_areas... OK
Applying entitlements.0003_seed_foundation_requirements... OK
Applying entitlements.0004_foundations_real_destination... OK
```

### Confirmed intended seed state
```
ProductArea rows: 16
FoundationRequirement rows: 18
Foundations destination: organisations:foundations
Home destination: organisations:detail
health status: 200
```
Exactly the intended fresh-install state — no reliance on any pre-existing
developer database anywhere.

### Representative tests run against this fresh clone
`pytest entitlements/tests/ organisations/tests/
core/tests/test_application_shell.py core/tests/test_route_matrix.py`:
**536 passed, 1 failed** on the first pass — the one failure was
`organisations/tests/test_narrow_viewport_regression.py::
test_organisations_list_has_no_horizontal_overflow_at_375px`, with the
exact, expected error: `BrowserType.launch: Executable doesn't exist at
/root/.cache/ms-playwright/...` — because this fresh container had never
had `playwright install --with-deps chromium` run against it yet (per
`docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`'s own documented,
runtime-only, per-container procedure). This is not a regression; it is
direct, live proof that Chromium genuinely is NOT baked into the image —
exactly the property WI6's browser-capability work was built to guarantee.
Running `docker compose -p m007freshclone exec web playwright install
--with-deps chromium` (the documented procedure) and re-running that one
test: **1 passed**. Final result: **537/537** of the representative tests
run pass on a genuinely fresh clone + fresh volumes once the documented
runtime capability step is followed.

Stack torn down (`down -v`), temporary clone directory removed.

---

## Conclusion

Both proofs: **GREEN**. No hidden reliance on the existing developer
database or any pre-existing Docker state anywhere in the M007 product.
Backup/restore correctly round-trips M007's own governed methodology
tables and reproduces the Foundational Security Posture metric
identically; a completely fresh clone, fresh volumes, and a from-zero
migration produce exactly the intended seed state and pass the
representative test subset once the documented, genuinely-runtime-only
browser capability step is followed.
