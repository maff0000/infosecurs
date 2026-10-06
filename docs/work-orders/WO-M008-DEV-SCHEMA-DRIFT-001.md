# WO-M008-DEV-SCHEMA-DRIFT-001 — Dev Schema Drift Recovery

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Applicable Amendment:** `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md`
**Exact base SHA:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Scope

Dev schema diagnosis, safe canonical-migration application against the existing `infosecurs-relocation` development stack, verification, and prevention evidence. **Nothing else.** No manual schema editing, no database recreation, no Customer Zero reset, no evidence deletion, no DARWIN interaction, no M009 work.

## Pre-mutation Implementer gate

Before applying ANY migration, the Implementer must capture:

1. `git status --short`
2. `git rev-parse HEAD`
3. `git rev-parse origin/main`
4. Running Compose/container identities (the `infosecurs-relocation` stack specifically)
5. DARWIN container identities (to prove, both before and after, that they are untouched)
6. `python manage.py showmigrations` (against the live dev stack)
7. `python manage.py migrate --plan`
8. `python manage.py makemigrations --check --dry-run`
9. The database's own migration-table state (`django_migrations`)
10. Direct schema introspection of `organisations_organisationprofile` for whether `sector`, `people_with_system_access_count`, and `has_remote_or_offsite_access` exist
11. Whether the `security_baseline_answerselectiondetail` table exists
12. The current `policy_policyversion.generation_source` column's schema/migration state

**Do not assume `organisations/0004` is the only missing migration.** Determine the complete, canonical, pending-migration set.

**If `makemigrations --check` proposes any new source migration: STOP and return to the Architect.**
**If migration history is inconsistent, faked, divergent, or otherwise abnormal: STOP** — do not proceed to backup or recovery.

## Backup before migration

Use the existing governed backup process (`docs/runbooks/BACKUP-RESTORE.md`) against the canonical dev stack. Capture a database backup before any mutation. Do not delete or overwrite any prior backup. Preserve the evidence volume. Record checksum/manifest per the existing runbook's own convention. **Prove the backup succeeded before proceeding to the recovery action.**

## Recovery action

**If and only if** the preflight gate shows ordinary unapplied canonical migrations with a consistent migration graph:

Apply the canonical migration graph using Django:

```
python manage.py migrate --noinput
```

against the existing `infosecurs-relocation` development stack. **No direct SQL. No `--fake`. No database recreation. No Customer Zero reset. No evidence deletion. Do not touch DARWIN.**

## Post-migration verification

Immediately prove:

1. `showmigrations` has no unapplied migrations;
2. `migrate --plan` reports no operations;
3. `makemigrations --check --dry-run` clean;
4. `OrganisationProfile`'s real schema now contains the M008 fields;
5. `AnswerSelectionDetail`'s table exists, if its canonical migration was pending;
6. the policy `generation_source` migration state is current;
7. Customer Zero's organisation UUID still exists, unchanged;
8. Customer Zero's user/password hash is unchanged;
9. Customer Zero's membership remains intact;
10. Customer Zero's governance-role assignments remain intact;
11. existing evidence records/files remain intact.

## Real browser acceptance

Do not stop at `/healthz/`. Use genuine Chromium against `http://192.168.11.10:8884/`. Prove at minimum, with real page loads, no database/schema errors anywhere:

```
login
  → organisation Home
  → Foundations workspace
  → Stage 1
  → Stage 2
  → Stage 3
  → Stage 4
  → Risks & Actions
  → Security Policy
```

Also prove the dev reset screen itself renders (reaching the confirmation page) — but **do not actually perform a reset of the current Customer Zero state during this incident**, unless separately, explicitly required by something this verification uncovers. The health endpoint must also remain `200` throughout.

## Root-cause evidence

Create `docs/evidence/M008-DEV-SCHEMA-DRIFT-INCIDENT.md`, recording the actual evidence gathered, not assumptions. The expected root cause to verify (not to assume without checking):

- the development Compose stack bind-mounts the repository (`.:/app`);
- the `web` service's own startup command runs `manage.py migrate` only at container start;
- the canonical repository was fast-forwarded to a new M008 SHA while the existing `web` container remained running;
- Django's dev autoreloader picked up the new Python model code immediately, without a container restart;
- the persistent PostgreSQL schema remained at its pre-M008 shape, since no migration ran;
- `/healthz/` checks database connectivity only (not schema correctness against the running application code), so this mismatch was not caught by it.

**If the gathered evidence disproves this narrative, STOP and return to the Architect rather than forcing it into the report.**

## Prevention

This incident also exposes an operational acceptance defect: a `/healthz/` 200 was treated as sufficient proof of a usable application after a schema-bearing release, when it is not. Update the appropriate dev/reconciliation runbook (most likely `docs/runbooks/BETA-OPERATIONS.md`, or a new small runbook if none fits) so that after canonical main is advanced on the persistent dev host, the Delivery Controller must prove:

- the source SHA now running;
- migration status (`showmigrations`/`migrate --plan`);
- canonical migrations applied where required;
- `migrate --plan` empty afterward;
- `makemigrations --check` clean;
- a real, authenticated application-page smoke test — not `/healthz/` alone.

At minimum that smoke test must hit: Home, the Foundations workspace, and one model-backed guided page. **A successful `/healthz/` alone must never again be treated as proof that the application is usable after a schema-bearing release.**

**Do not invent an automatic production-migration mechanism under this incident.** A documentation/runbook correction is sufficient unless investigation actually proves code or tooling changes are required — if it does, STOP and return to the Architect rather than building that mechanism under this Work Order.

## Independent audit

A fresh Auditor — independent of the Implementer's own work on this incident — must independently verify:

- the exact root cause;
- migration-history consistency;
- the backup's existence (and its checksum/manifest);
- that no manual SQL or `--fake` migration was used anywhere;
- that all canonical migrations are applied;
- that pre-existing Customer Zero tenant data was preserved throughout;
- that the real-browser surfaces named above genuinely work, with real evidence;
- that DARWIN was untouched throughout;
- that no unauthorised product source change was made;
- that the prevention/runbook documentation change is correct and complete.

## PR and Architect stop

The recovery PR may contain only: this Amendment, this Work Order, the incident evidence document, and the authorised runbook/documentation prevention change — **unless** a new source defect is discovered during this recovery and separately authorised by the Architect.

After the independent audit is GREEN and all required CI checks are green on the PR's head:

**STOP. DO NOT MERGE.**

Return to the Project Architect with:

1. the exact pending migrations found before repair;
2. the backup evidence;
3. the exact migration command and its result;
4. before/after migration state;
5. Customer Zero preservation evidence;
6. the browser results;
7. the root-cause verdict;
8. the prevention change;
9. the independent Auditor's verdict;
10. the PR/head SHA and check conclusions.

**Only Architect Acceptance authorises merge/incident closure.**
