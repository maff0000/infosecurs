# IRENE Release, Rollback and Scheduler Operations — DRAFT

**Status: DRAFT, operator-facing additions proposed by the M010F dispatch
(`docs/pids/M010F-INTEGRATION-SECURITY-RELEASE.md` §6/§7).** Not yet
finalised — per that PID, Gunnar finalises operator-facing runbook/PID/
ROADMAP text after the separate, fresh Independent Audit (§3) this
document does not replace. Everything below was directly verified against
a real disposable stack (project `m010f`) during this dispatch; nothing
here is aspirational. See `docs/evidence/M010F-INTEGRATION-SECURITY-RELEASE.md`
for the full evidence write-up this runbook draft is extracted from.

This extends `docs/runbooks/BETA-OPERATIONS.md` (M006 PID §13, general
Compose operations) and `docs/runbooks/BACKUP-RESTORE.md` (M006 PID §14,
backup/restore) with the three things M010 (IRENE) adds: feature flags,
the deterministic review scheduler, and metrics/log hygiene.

---

## 1. Feature flags — what each one gates, and the safe-OFF story

Four independent `optional_env()`-backed booleans, defined in
`config/settings.py` (lines ~47-90), none `DJANGO_ENV`-gated (unlike the
dev-only `CUSTOMER_ZERO_RESET_ENABLED`) — safe to flip in any environment
including production, and the ordinary docker-compose `.env`/env-var
mechanism, no redeploy needed beyond a container restart to pick up the
new value.

| Flag | Default | What it gates | Confirmed OFF behaviour |
|---|---|---|---|
| `IRENE_ENABLED` | `true` | The modal shell itself (Continue/Tasks/Activity/Ask tabs, auto-open). No AI call of its own. | `organisations/tests/test_http_ui.py::TestAutoOpenPreference::test_manual_app_works_with_irene_disabled` (set `settings.IRENE_ENABLED = False`): Home returns 200 with no `irene-modal` markup; `security_tasks:list` (manual Tasks page) remains 200. Re-run during this dispatch: PASS. |
| `IRENE_TASK_TOOLS_ENABLED` | `true` | The two model-callable write tools (`propose_task`/`confirm_task_creation`) — both go through the ordinary `security_tasks.services.create_task` path, no AI dependency. | `irene/tools.py` lines 616-638: dispatch-time flag check, same `PermissionDenied`-style fail-closed shape as every other tool gate. Manual "New task" form is a completely separate code path (`security_tasks.views.task_create`) and is never touched by this flag. |
| `IRENE_ADVISER_MODE_ENABLED` | **`false`** | The ONLY flag that gates a real AI-gateway call (`ai_platform.gateway.LiteLLMGateway.ask_adviser`). Must stay `false` in every real environment until numeric budgets and a vendor security assessment are separately approved (no such approval exists — `config/settings.py`'s own comment, M010C evidence §4). | Ask tab deterministically shows "free-form explanations are temporarily unavailable" (`irene/templates/irene/_modal.html` line 70) and the rest of the modal (Continue/Tasks/Activity) is unaffected. |
| `IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED` | `true` | The read-only M009 Customer Assurance status tool/page (Monthly/PRO tier only) — re-reads existing, already tier/readiness-gated state; no AI dependency. | `irene/tests/test_customer_assurance_tools.py::test_disabled_flag_denies_via_call_tool_dispatch`. |

**Operator rollback recipe (any single flag, any time):** set the env var
to `false` in `.env` (Compose) or the real deployment's equivalent secret/
config store, then `docker compose restart web` (or redeploy, depending on
environment) — no migration, no data loss, no code rollback required. All
four flags are read once at Django process start via `optional_env()`, not
cached elsewhere.

**Confirmed independently during this dispatch:** fresh `migrate --noinput`
against an empty Postgres (project `m010f`) applies every M010 migration
cleanly regardless of flag state (flags are a runtime/application-layer
concern, never a migration guard) — see §3 below.

## 2. App-level rollback — reverting M010's own migrations

If an application rollback to a pre-M010 code version is ever required
(not merely flags OFF), M010 introduced exactly these migrations, and
**all were proven to reverse and re-apply cleanly** against a real
Postgres during this dispatch (command transcript in
`docs/evidence/M010F-INTEGRATION-SECURITY-RELEASE.md` §3):

```bash
python manage.py migrate irene zero
python manage.py migrate foundations_journey zero
python manage.py migrate security_tasks zero
python manage.py migrate entitlements 0004_foundations_real_destination
```

Reversing `entitlements.0005_seed_tasks_and_irene_product_areas` removes
exactly the two rows it added (`tasks`, `irene`), by `code`, never a
blanket delete — the pre-existing 16 `ProductArea` rows (M007/M008) are
untouched either direction. Re-applying (`python manage.py migrate`) is
equally clean and idempotent.

**This is an expand/contract-safe rollout, not a risky downgrade**: every
M010 migration is purely additive (new apps/tables, two new seed rows) —
no existing M007/M008/M009 column, table or constraint is altered, so an
OLDER application binary that has never heard of `security_tasks`/
`foundations_journey`/`irene` continues to run correctly against a
database that HAS those tables present but unused. The one migration that
touches a pre-existing app (`entitlements`) only inserts two additive rows
a pre-M010 binary's `ROUTE_NAMESPACE_TO_CAPABILITY` mapping never looks
up. No documented case requires a destructive/irreversible schema change,
so no separate expand/contract rollout plan beyond "roll the app binary
back; leave the M010 migrations applied" is needed.

## 3. Deterministic review scheduler — deployment and concurrency

`python manage.py run_security_reviews [--organisation=<uuid>]`
(`security_tasks/management/commands/run_security_reviews.py`) makes
**zero AI/model calls** and is genuinely idempotent — proven by
`security_tasks/tests/test_review_scheduler_concurrency.py` (two real,
concurrent threads calling `run_for_organisation` for the SAME
organisation produce exactly one task+event per due occurrence, never a
duplicate) and `security_tasks/tests/test_run_security_reviews_command.py`
(repeated sequential invocation is a no-op the second time).

**No OS-level cron/daemon/leader-election mechanism is wired up by any
M010 package** — this was explicitly disclosed as a later deployment
concern by M010D's own evidence document
(`docs/evidence/M010D-REVIEW-SCHEDULER.md` line 65) and remains true at
M010F integration time; re-confirmed directly here, not merely cited.

**Recommended deployment, specified concretely (this dispatch's own
proposal, pending Gunnar/Central Architecture sign-off — not yet
binding):**

- Run `manage.py run_security_reviews` on a **single designated host**
  (whichever host already runs other scheduled maintenance for this
  deployment) via a standard `cron`/systemd-timer entry, e.g. daily at a
  fixed off-peak UTC time: `0 2 * * * cd /app && python manage.py
  run_security_reviews >> /var/log/infosecurs/security_reviews.log 2>&1`.
- **No distributed lock or leader-election service is required for
  correctness** — the command's own idempotency (the DB-level unique
  `occurrence_key` constraint on `SecurityTask`, not an application-level
  lock — see `docs/architecture/M010-DATA-WORKFLOW-CONTRACTS.md` line 73
  "task uniqueness required even if lock fails") already makes a second,
  overlapping, or retried run produce zero duplicates, proven by the
  concurrency test above. A lock is therefore an efficiency optimisation
  (avoid doing redundant read-only candidate evaluation work twice), never
  a correctness requirement.
- **Bounded worker concurrency**: the command itself has no internal
  worker pool — it iterates organisations strictly sequentially, one at a
  time, inside its own `handle()` loop (`security_tasks/management/
  commands/run_security_reviews.py`), each wrapped in its own isolated
  transaction boundary via `review_scheduler.run_for_organisation`. A
  single cron invocation is therefore inherently bounded to concurrency=1
  by construction; running it from more than one host/cron entry
  simultaneously is safe (proven idempotent) but wasteful, not unsafe.
- **Failure monitoring**: the command prints one `WARNING`-styled stderr
  line per organisation that raises (naming the organisation by UUID and
  exception type ONLY — never its name or any task/source content) and
  continues to the next organisation (M010D PID §5 "one tenant failure
  must not prevent processing subsequent tenants" — re-confirmed by direct
  code read, not merely cited). An operator wiring this cron job into any
  log-based alerting should match on that `WARNING` string and on a
  non-zero `organisations_failed` count in the final summary line.
- **No title/content leakage in logs**: every line the command prints
  (per-organisation progress line and the final summary) carries only the
  organisation UUID and integer counts (`candidates`, `created`,
  `unchanged`, `superseded_and_recreated`, `reconciliation_conflicts`,
  `candidate_errors`) — confirmed by direct read of the command's
  `self.stdout.write`/`self.stderr.write` calls; no task title, source
  object content, or any other organisation's data ever appears on the
  same line as another organisation's identifier.

## 4. What is explicitly NOT covered by this draft

- Real customer data, hosting/DPIA/processor gates, and brand/trademark
  clearance for "IRENE" — all separately gated per the governing PID §6,
  unaffected by anything in this document.
- The genuinely fresh, independent Auditor pass required by PID §3 — this
  document is Implementer-side preparation for that audit, not a
  substitute for it.
- Finalising this draft into the canonical `docs/runbooks/` tree — left to
  Gunnar per the governing PID's own division of labour (§7 "final
  handoff required from Gunnar"); this file's own status line says so
  explicitly to avoid it being mistaken for an already-accepted runbook.
