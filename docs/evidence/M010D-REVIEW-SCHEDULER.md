# M010D — Deterministic Security Review Scheduler and Proactive Tasking

**Milestone:** M010 — IRENE AI Security Adviser and Shared Security Tasks (Work Package D)
**Parent PID:** `docs/pids/M010D-REVIEW-RULES-SCHEDULER.md`
**Binding architecture:** `docs/architecture/M010-DATA-WORKFLOW-CONTRACTS.md` §4/§5, `docs/architecture/M010-MASTER-ARCHITECTURE.md` §6/§7
**Implementation branch:** `wo/M010D-review-rules-scheduler`
**Base:** `cc32c39` (`wo/M010-irene-ai-first-campaign`)
**Isolation:** built entirely in a throwaway worktree (`/tmp/m010d-impl` on the build host) and a disposable Docker Compose stack (`-p m010d`, `POSTGRES_HOST_PORT=25432`, `WEB_HOST_PORT=28100`) — the shared canonical clone (`/srv/openclaw/worktrees/wo/M009A-work-order`) and the persistent `/srv/infosecurs` deployment were never touched.

## 0. Non-negotiable scope boundary — confirmed held

This package makes **zero** model/AI gateway calls anywhere (M010-MASTER-ARCHITECTURE.md §6 "no independent LLM scheduler judgement", §8 "Do not make the Task List depend on a model call"). `ai_platform.gateway.LiteLLMGateway._send` — the one real network boundary in this codebase — is patched and asserted never-called across representative multi-rule scheduler runs, the management command, and the briefing-counts helper (`security_tasks/tests/test_review_scheduler.py::test_run_for_organisation_makes_zero_ai_gateway_calls`, `test_run_security_reviews_command.py::TestRunSecurityReviewsCommand::test_command_makes_no_ai_gateway_call`, `test_review_briefing.py::TestGetReviewBriefingCounts::test_makes_no_ai_gateway_call`).

## 1. Inventory — re-verified directly, before writing any code

Per the PID's own §1 instruction ("inventory live domain fields and services before code"), every field below was read directly from the real model source in this worktree, not assumed from any prior summary:

| Rule kind | Status | Source field | Reason |
|---|---|---|---|
| `policy_review` | **ENABLED** | `policy.models.PolicyVersion.next_review_date` (`DateField`, nullable) | Genuine, real review-date field. |
| `remediation_followup` | **ENABLED** | `remediation.models.RemediationAction.target_date` (`DateField`, nullable) | Genuine, real deadline field. |
| `evidence_review` | **ENABLED** | `evidence.models.EvidenceItem.valid_until` (`DateField`, nullable) | Genuine, real expiry field. |
| `risk_review` | **DISABLED** | — | `risk_register.models.Risk` has **no** review-date-shaped field at all — only `confirmed_at`/`dismissed_at`/`created_at`/`updated_at` (all `DateTimeField`s recording when something already happened, none a future due date). No cadence (e.g. "N months after `confirmed_at`") is invented — the PID never authorised one. |
| `supplier_review` | **DISABLED** | — | No supplier/vendor-management Django app exists anywhere in this repository (confirmed directly — `ls -d */` lists no `supplier*` app directory). PID §1's own condition ("only if supplier module exists and offers a canonical date") is not met. |
| Foundations re-confirmation | **NOT REGISTERED AT ALL** (not merely disabled) | — | `security_baseline.models` has no field representing a future "re-confirm this control by" date (only `created_at`/`updated_at`/`recorded_at`, all recording the past); `entitlements.models` has no date field at all. There is no `TaskKind` member for this either — nothing to point even a disabled rule at. |

This package ships exactly **three** real, working review rules, and explicitly disables/omits the rest — not from running out of time, but because no genuine source date exists for them. The inventory the Delivery Controller supplied matched this re-verification exactly; no correction was needed.

See `security_tasks/review_rules.py`'s module docstring and `REGISTERED_RULES` dict for the same table expressed in code, with `disabled_reason` strings asserted word-for-word by `security_tasks/tests/test_review_rules.py::TestRuleRegistry`.

## 2. What was built

### 2.1 Rule registry (`security_tasks/review_rules.py`)

Pure candidate computation — **no** write, no `SecurityTask` creation, no cross-tenant query anywhere in this file. `ReviewCandidate` (frozen dataclass): `rule_id`, `rule_version`, `organisation_id`, `task_kind`, `source_kind`, `source_object_id`, `due_at` (UTC-aware), `due_occurrence` (the source `DateField`'s own ISO date string), `window`, `title`, `owner_user_id`.

- `rule_policy_review` — only `PolicyVersion.status == APPROVED` with `next_review_date` set (a `draft` or `superseded` version is excluded — the required "superseded-policy-version" scenario). Owner always `None` — see §5.1.
- `rule_remediation_followup` — only `RemediationAction.status in ACTIVE_STATUSES` (`open`/`in_progress`) with `target_date` set (a `done`/`accepted` action is excluded — the required "already-completed-source" scenario). Owner = `assigned_to_id`.
- `rule_evidence_review` — only `EvidenceItem.status == STATUS_ACTIVE` with `valid_until` set (`superseded`/`withdrawn` excluded). Owner always `None` — see §5.1.
- `due_at_from_local_date` — converts a date-only field to a UTC-aware instant via `zoneinfo`-based midnight-in-`BUSINESS_TIMEZONE` conversion, never naive arithmetic. `warning_window_for` buckets a candidate into `overdue`/`due_7d`/`due_30d`/`future` by comparing two UTC-aware datetimes directly (DST-transition-safe by construction — see §4).
- `evaluate_organisation(organisation, *, now=None)` — the one combined entrypoint; runs every `enabled` rule, each already filtered to the one `organisation` passed in.

### 2.2 Emission + reconciliation (`security_tasks/review_scheduler.py`)

The **only** module that writes anything, and every write goes through the existing, already-tested `security_tasks.services.create_task`/`transition_task` — never a new write path.

- **Occurrence key** (PID §2, verbatim): `f"{rule_id}:{source_object_id}:{due_occurrence}"`. `idempotency_key` is derived deterministically from it (`"rules_engine:" + occurrence_key`) — a repeated scheduler run for the same occurrence presents the identical key, which is exactly "same logical request, run again."
- **Idempotent create**: `_create_for_candidate` calls `create_task` with the candidate's own `owner_user_id` as `assignee_id`; a `ForeignAssigneeError` (owner no longer a current member) is caught and the call is retried with `assignee_id=None` — reusing `create_task`'s own existing live-membership check, never a duplicated query.
- **Changed-due-date reconciliation** (architecture doc §4/§5's explicit three-option menu — this package implements the third, "close superseded task"): if a still-`open` `rules_engine` task exists for the same `(organisation, task_kind, source_object_id)` under a **different** `occurrence_key`, it is transitioned to `cancelled` with `closed_reason=SUPERSEDED_BY_NEW_OCCURRENCE` (never deleted), then the new occurrence's task is created. Both steps run inside one `transaction.atomic()` block.
- **Deliberately NOT implemented** (recorded here, not silently added): no sweep-cancel of an open task whose source became otherwise ineligible for a reason *other than* a due-date change on the same object (e.g. a human independently marks a `RemediationAction` `done` while its `remediation_followup` task is still open). The architecture doc's reconciliation menu is scoped to "source review date changed" — extending it to "source became inactive for any reason" is a product-policy question this PID does not clearly authorise, so such a task is left exactly as it is; a person closes it through the ordinary Tasks page. Proven by `test_review_scheduler.py::TestAlreadyCompletedAndSupersededSourcesAreSkipped::test_superseded_policy_version_yields_no_new_task_and_old_open_task_is_left_untouched`.

Two small, backward-compatible extensions to the **existing** `security_tasks.services` functions (not a new write path — exposing already-modelled columns through the existing calls):
- `create_task(..., source_version="")` — sets the already-modelled `SecurityTask.source_version` column and records it in the `created` event's metadata, carrying `"{rule_id}:v{rule_version}"` (architecture doc §5: "store trigger rule id/version in task events"). Every existing caller is unaffected (default `""`, unchanged behaviour).
- `transition_task(..., closed_reason=None)` — sets the already-modelled `SecurityTask.closed_reason` column when transitioning into a closed status. Before this package, no service path set this column to any real value at all (it was write-only-blank; only the reopen branch cleared it). Every existing caller is unaffected (default `None`).

### 2.3 Management command (`security_tasks/management/commands/run_security_reviews.py`)

```
python manage.py run_security_reviews
python manage.py run_security_reviews --organisation=<uuid>
```

Mirrors `risk_register.management.commands.run_ai_eval`/`policy.management.commands.run_policy_ai_eval`'s established `Command`/`add_arguments`/`handle` structure, with **no** AI gateway construction anywhere (unlike those two, which exist specifically to call one). Iterates `Organisation.objects.order_by("pk")` one at a time; a genuine exception evaluating one organisation is caught, logged (by UUID only — see §5.3), and the loop continues to the next organisation. Prints per-organisation and total counters only (`created`/`unchanged`/`superseded_and_recreated`/`candidate_errors`) — never a task title or any source content.

No OS-level cron/daemon is wired up — per the architecture doc, that is a later deployment concern. This command is safe to invoke by hand, by cron, or concurrently with itself, any number of times.

### 2.4 Briefing surface (`security_tasks/services.get_review_briefing_counts` + Tasks page)

**Chosen surface: the `security_tasks` Tasks page** (`security_tasks/templates/security_tasks/list.html`), not the `irene`/`foundations_journey` Continue tab. Reasoning: the Tasks page is the canonical home of the task ledger's own derived counts, needs no extra plumbing through IRENE's separate modal-context assembly, and keeps this explicitly zero-AI surface structurally decoupled from the one tab that *does* make model calls — there is no shared code path for a future change to IRENE's Ask tab to accidentally pull this computation into.

`get_review_briefing_counts(organisation)` calls `get_task_list` three times (`due_filter="overdue"`, `due_filter="due_soon"` with `due_within_days=7`, and again with `due_within_days=30`) and keeps only `total_count` from each — **never a new, parallel ORM query path**. `get_task_list` gained one new, backward-compatible optional parameter, `due_within_days` (default unchanged at `DUE_SOON_WINDOW_DAYS=7`), generalising its existing fixed 7-day "due soon" window so the same filter logic serves both the 7-day and 30-day counts.

Rendered via the existing `.metric-card-row`/`.metric-card` shared classes (`infosecurs-ui-design` doctrine followed: plain number + text, no gauge/chart/icon, matching Home's own existing metric cards exactly — zero new CSS added).

## 3. Non-negotiable constraints — how each is held

- **Never fabricate a due date**: every rule function filters `..._isnull=False` before ever building a candidate; `_candidate_from_date` additionally returns `None` for a falsy date as a second, explicit guard. Proven: `test_review_rules.py`'s `test_no_date_at_all_is_skipped*` (×3 rules) and `test_review_scheduler.py::test_no_date_at_all_creates_no_task_no_fabrication`.
- **UTC canonical storage / DST correctness**: see §4.
- **Tenant-scoped, no cross-tenant aggregation**: every rule function takes one `organisation` and filters by it explicitly; `evaluate_organisation`/`run_for_organisation` never accept more than one. Proven: `test_review_rules.py`'s five `test_never_queries_another_organisations_*` cases, `test_review_scheduler.py::TestOrganisationScoping`, `test_review_briefing.py::test_organisation_scoping_never_counts_another_organisations_tasks`, and the management command's own per-organisation log-line isolation (`test_run_security_reviews_command.py::test_one_organisations_rule_failure_does_not_block_the_next_organisation` asserts the OTHER organisation's id never appears in a failure line).
- **Exactly one task+event per genuine occurrence, under concurrency**: see §4.
- **A `done` task never mutates `PolicyVersion`/`RemediationAction`/`EvidenceItem`**: this package's two new modules never import those three models for a write (`review_rules.py` reads them read-only inside each rule function; `review_scheduler.py` never imports them at all). Proven directly: `test_review_scheduler.py::TestCompletionNeverMutatesSourceModels`.

## 4. Concurrency and DST — results stated plainly

All of the following **PASSED** (not "should work" — real execution, shown in full in §7):

- **Two overlapping scheduler workers, same organisation, same brand-new occurrence** → exactly one `SecurityTask` row, exactly one `created` `SecurityTaskEvent` (`test_review_scheduler_concurrency.py::test_two_overlapping_runs_for_the_same_organisation_produce_exactly_one_task_and_event`, real threads + `transaction=True`, same technique as `test_concurrency.py`).
- **Two overlapping scheduler workers racing the same reconciliation** (due date just changed, same stale open task) → exactly one worker wins the supersede (`select_for_update` + `expected_version`), the other gets `ConcurrentModificationError` and defers without creating a duplicate new-occurrence task (`test_two_overlapping_reconciliation_runs_supersede_exactly_once`).
- **Simulated crash between the DB write and task-creation completing** — proven **by construction**, not by racing a real process kill: `create_task` wraps both the `SecurityTask` insert and its `created` `SecurityTaskEvent` insert inside **one** `transaction.atomic()` block (`security_tasks/services.py` lines ~339–372), so there is no instant where one is durably committed and the other is not. `test_review_scheduler_concurrency.py::TestNoPartialStateWindowOnFailure` forces a real exception between the two inserts (monkeypatching `SecurityTaskEvent.objects.create`) and confirms the result is a clean, total rollback — zero rows of either kind, never an orphaned task.
- **Spring-forward / autumn-back / UTC-midnight**: `test_review_rules.py::TestDueAtConversion` constructs real UK 2026 transition dates (spring forward Sunday 29 March, autumn back Sunday 25 October — independently confirmed against the real last-Sunday-of-month rule, not assumed) and asserts the exact resulting UTC instant on the day before/of/after each transition, cross-checked against a direct `zoneinfo` computation before the test was written:

  | Local date | UTC instant | Offset |
  |---|---|---|
  | 2026-01-15 (winter) | `2026-01-15T00:00:00Z` | +0 |
  | 2026-07-15 (summer) | `2026-07-14T23:00:00Z` | +1 |
  | 2026-03-28 (day before spring-forward) | `2026-03-28T00:00:00Z` | +0 |
  | 2026-03-29 (spring-forward day itself — midnight is still before the 01:00 changeover) | `2026-03-29T00:00:00Z` | +0 |
  | 2026-03-30 (day after) | `2026-03-29T23:00:00Z` | +1 |
  | 2026-10-24 (day before autumn-back) | `2026-10-23T23:00:00Z` | +1 |
  | 2026-10-25 (autumn-back day itself — midnight is still before the 02:00 BST changeover) | `2026-10-24T23:00:00Z` | +1 |
  | 2026-10-26 (day after) | `2026-10-26T00:00:00Z` | +0 |

  `TestWarningWindowBucketing::test_window_bucketing_is_stable_across_a_dst_transition` additionally proves the 30-day warning-window boundary stays exact (not off-by-one-hour) when the `[now, due_at]` interval itself crosses the spring-forward transition, because the comparison is always between two UTC-aware `datetime`s, never a naive calendar-day subtraction. `test_utc_midnight_boundary_is_handled_without_off_by_one` proves `due_at == now` is "due soon", not "overdue" (overdue requires genuinely *past*, strict `<`).

## 5. Honest disclosures / design decisions the PID left ambiguous

### 5.1 Owner assignment — deliberately `None` for two of the three rules

Architecture doc §5: "Task owner assigned from existing source owner only if authorised member; otherwise unassigned queue." Only `RemediationAction.assigned_to` genuinely means "the person already working this." `PolicyVersion.policy_authoriser` is a `governance.OrganisationPerson` record — not necessarily a logged-in `AUTH_USER_MODEL` account with current organisation membership — and `EvidenceItem.recorded_by` records who historically *uploaded* the item, not who is responsible for renewing it. Mapping either to a task owner would be a guess the PID never authorised. Applying the exact same "do not invent" discipline the PID mandates for due dates, `policy_review` and `evidence_review` candidates always carry `owner_user_id=None` (unassigned queue); only `remediation_followup` attempts a candidate owner, with live-membership re-validation and fallback (§2.2, proven by `test_review_scheduler.py::TestOwnerAssignmentFallsBackToUnassignedForRemovedMember`).

### 5.2 Disclosed, unapproved placeholders

- **Warning-window numbers** (30/7 days + overdue): used as the working default per the architecture doc's own licence ("configurable defaults requiring product approval at implementation, not a statement that every domain currently has a due date"). **No product approval has been recorded for this package** — same disclosed-placeholder discipline Work Package C already used for its own AI-budget placeholders.
- **Business timezone** (`Europe/London`): `organisations.models.Organisation` has no timezone field at all (checked directly). The architecture doc names `Europe/London` as the candidate default "if explicitly confirmed" — that confirmation has not happened. Used here as a single, global working default, disclosed exactly like the warning-window numbers, not claimed as product-approved.

### 5.3 Logging/metric discipline

Every log line in `run_security_reviews` and every `logger.info`/`logger.exception` call in `review_scheduler.py` names an organisation by UUID only, and reports counts only — never a task title, a source object's content, or a second organisation's data on the same line. Proven: `test_run_security_reviews_command.py::test_one_organisations_rule_failure_does_not_block_the_next_organisation` asserts the failing organisation's own id appears, and the OTHER organisation's id never appears in the stderr stream.

### 5.4 Reconciliation scope (repeated from §2.2 for visibility)

The scheduler implements the architecture doc's "close superseded task" option for a **changed due date** on the same source object. It does **not** additionally sweep-cancel an open task whose source became ineligible for an unrelated reason. This is a scope decision, not an oversight — see §2.2's full reasoning.

## 6. Migration

**No migration was needed.** `SecurityTask.source_version` and `SecurityTask.closed_reason` already existed as columns from Work Package A's `0001_initial` migration; this package only adds service-layer parameters that set them, never a schema change. Confirmed directly: `python manage.py makemigrations --check --dry-run` → `No changes detected` (§7.5).

## 7. Verification — full results

### 7.1 New test suite, in isolation

```
pytest -v security_tasks/tests/test_review_rules.py security_tasks/tests/test_review_scheduler.py \
            security_tasks/tests/test_review_briefing.py security_tasks/tests/test_run_security_reviews_command.py
53 passed in 7.77s

pytest -v --create-db security_tasks/tests/test_review_scheduler_concurrency.py
3 passed in 8.30s
```

All 56 new tests passed, including every required-evaluation scenario:

| Required scenario (PID §6) | Test | Result |
|---|---|---|
| Due yesterday / today / 7d / 30d / beyond | `TestWarningWindowBucketing` (6 cases) | PASS |
| No date at all | `test_no_date_at_all_is_skipped*` (×3 rules) + `test_no_date_at_all_creates_no_task_no_fabrication` | PASS |
| Already-completed source | `test_already_completed_source_is_skipped`, `test_accepted_source_is_skipped`, `test_done_remediation_action_yields_no_task` | PASS |
| Superseded policy version | `test_superseded_policy_version_is_skipped`, `test_superseded_policy_version_yields_no_new_task_and_old_open_task_is_left_untouched` | PASS |
| Removed tenant member as owner | `test_removed_tenant_member_as_owner_falls_back_to_unassigned` | PASS |
| Manually closed then reopened source | `test_manually_closed_then_reopened_source_is_not_resurrected_or_duplicated` | PASS |
| Changed due date | `test_open_task_is_superseded_and_a_new_occurrence_is_created` | PASS |
| Genuine recurrence (second due cycle) | `test_completed_first_occurrence_does_not_block_a_later_second_occurrence` | PASS |
| DST spring-forward / autumn-back | `TestDueAtConversion` (×4 transition-date cases) | PASS |
| UTC midnight boundary | `test_utc_midnight_boundary_is_handled_without_off_by_one` | PASS |
| Overlapping concurrent workers | `TestOverlappingConcurrentSchedulerWorkers` (×2) | PASS |
| Simulated crash between DB write and task creation | `TestNoPartialStateWindowOnFailure` | PASS (proven by construction) |
| Correct organisation scoping throughout | `TestOrganisationScoping` + 6 cross-tenant cases elsewhere | PASS |
| No fabricated date ever | Entailed by every "no date" case above | PASS |
| No model/AI call anywhere | 3 dedicated zero-AI-gateway tests | PASS |
| No security-control state silently upgraded | `TestCompletionNeverMutatesSourceModels` | PASS |

### 7.2 Regression — `ci/unit` curated list (updated, includes the 4 new files), fresh container

```
pytest -q <58 files from the updated ci/unit job>
783 passed, 1 warning in 334.20s (0:05:34)
```

730 baseline + 53 new = 783. The 1 warning is the pre-existing, unrelated M009A duplicate-zip-entry `UserWarning` — present in the baseline too. **Zero regressions.**

### 7.3 Regression — `ci/integration` curated list (updated, includes the 1 new file + the 2 tests added to the existing `test_http_ui.py`), fresh `--create-db`

```
pytest -q --create-db <77 files/dirs from the updated ci/integration job>
1278 passed, 7 skipped, 1 xfailed in 1235.66s (0:20:35)
```

1273 (baseline) + 2 (new tests added to the already-wired `security_tasks/tests/test_http_ui.py`) + 3 (new `test_review_scheduler_concurrency.py`) = 1278. 7 skipped / 1 xfailed, identical to the stated baseline. **Zero regressions.**

A first attempt at this exact command, run in a container where `playwright install --with-deps chromium` had not been (re-)executed (an ephemeral-container bookkeeping mistake on this package's own part — Chromium is never baked into the image per this codebase's own documented convention, and a fresh `docker compose run --rm` container starts with no browser installed), produced 52 failures, every one of them a browser-dependent test (`*_browser_acceptance.py`, `*_narrow_viewport_regression.py`). Re-run in a container where the install step ran first in the same session produced the clean 1278-passed result above. Disclosed here rather than omitted — not a real regression, a verification-setup mistake, caught and corrected before this package was reported done.

### 7.4 Separately re-confirmed baselines (before any new file was added to the curated lists)

```
pytest -q <54 pre-existing ci/unit files, unmodified list>
730 passed, 1 warning in 311.24s (0:05:11)

pytest -q --create-db <76 pre-existing ci/integration files, unmodified list>
1275 passed, 7 skipped, 1 xfailed in 1237.69s (0:20:37)
```

(1275 = 1273 baseline + the 2 new tests already living inside the pre-existing `test_http_ui.py` file, which this list already included before this package touched it.) Confirms the stated 730/1273 baseline exactly, and confirms this package's edits to `security_tasks/services.py`, `views.py` and `list.html` introduced **zero** regressions on top of it.

### 7.5 Fresh-migration proof

```
python manage.py migrate --noinput
# ... all pre-existing migrations apply cleanly; no new security_tasks migration exists or is needed
python manage.py makemigrations --check --dry-run
No changes detected
```

### 7.6 Security/dependency scans

```
gitleaks detect --source=. -v
199 commits scanned, no leaks found

pip-audit -r requirements.txt
No known vulnerabilities found
```

## 8. CI wiring

Added to `.github/workflows/ci.yml`:
- `ci/unit`: `security_tasks/tests/test_review_rules.py`, `test_review_scheduler.py`, `test_review_briefing.py`, `test_run_security_reviews_command.py` — ordinary, non-threaded, DB-backed tests, matching exactly where `test_services.py`/`test_completion_independence.py` already sit.
- `ci/integration`: `security_tasks/tests/test_review_scheduler_concurrency.py` — real-thread, `transaction=True` concurrency tests, matching exactly where `test_concurrency.py` already sits.
- The 2 new tests added directly to the already-wired `security_tasks/tests/test_http_ui.py` needed no new CI line — that file was already in the `ci/integration` list.

## 9. STOP-condition self-check (M010D PID §7)

| STOP condition | Status |
|---|---|
| Duplicate task/event for the same occurrence | Not found — proven under real concurrency (§4), idempotent re-run (§7.1), and manual-close-then-reopen (§7.1) |
| Cross-tenant tasks | Not found — every rule/scheduler/briefing function takes exactly one organisation; 8+ dedicated cross-tenant tests all green |
| Fabricated source dates | Not found — every "no date" path returns/creates nothing; proven at both the rule and scheduler layer |
| Accidental auto-approval | Not found — `review_scheduler.py` never imports `PolicyVersion`/`RemediationAction`/`EvidenceItem` for a write; `TestCompletionNeverMutatesSourceModels` proves it directly |
| Deleting historical task trace | Not found — the "changed due date" reconciliation path transitions the old task to `cancelled` (preserved, queryable) — it is never deleted; proven in `test_open_task_is_superseded_and_a_new_occurrence_is_created` |

**No STOP condition was triggered during this work package.** One genuine verification-setup mistake (a missing Chromium install in one ephemeral container, §7.3) was found, diagnosed, and corrected within this same package — disclosed rather than hidden, per this campaign's own evidence discipline. No code defect resulted from it.

## 10. Teardown

```
docker compose -p m010d down -v
git -C /srv/openclaw/worktrees/wo/M009A-work-order worktree remove /tmp/m010d-impl
```
