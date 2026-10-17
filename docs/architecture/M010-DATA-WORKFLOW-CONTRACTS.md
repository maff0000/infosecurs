# M010 — Data, Domain Services, Lifecycle and Concurrency Contracts

**Status:** Binding model and service design for implementation. **Canonical store:** Existing PostgreSQL (Django migrations). **Constraint:** adapt names for existing schema conflicts only with evidence; no duplicated Foundations answer/state. The first build package owns Task models; later packages add assistant/checkpoint metadata. Cross-tenant correctness takes precedence over convenient ORM joins.

## 1. Data models and constraints

### `SecurityTask` — organisation-shared work item

- `id` UUID primary key; `organisation` FK indexed not nullable; `task_kind` governed enum (`foundation_confirm`, `foundation_remediate`, `risk_review`, `remediation_followup`, `policy_review`, `evidence_review`, `supplier_review` when domain is present, `assurance_followup`, `manual_other`). Unknown future kinds are rejected until registered.
- `title` short bounded plain text, `summary` bounded non-sensitive optional text; task group code (Foundations, Risks/Actions, Policies, Evidence/Assurance, Other) derived from registered kind; `priority` (normal/high/urgent) and `priority_reason` from deterministic rules or authorised human choice; no LLM-set unvalidated urgency.
- `status` enum `open`, `in_progress`, `awaiting_external`, `blocked`, `awaiting_review`, `done`, `cancelled` with explicit transition rules; `status_reason` reason enum; `version` integer for optimistic writes.
- `assigned_to` optional FK to current user, validated membership in same org on assignment; `created_by` nullable actor; `source_origin` enum `human`, `irene`, `rules_engine`, `existing_domain`; `source_kind` enum and `source_object_id` UUID/approved identifier; `source_version` optional; `occurrence_key` immutable, opaque deterministic key for generated tasks.
- `due_at` UTC aware datetime nullable; `review_window_start_at` UTC optional; `source_timezone` IANA name if recurrence derives from local date, else null; `completed_at` UTC nullable; `created_at`, `updated_at` UTC; `completion_evidence_ref` optional typed source locator; `closed_reason` enum. Task completion never updates the security domain object by implication.
- `source_key` unique per `(organisation, source_origin, task_kind, occurrence_key)` where `occurrence_key` non-null. `manual_other` idempotency uses a separate user-supplied idempotency token, not a hardcoded global title dedupe. Define correct partial unique constraint in PostgreSQL with Django condition; test races.
- `visibility` normal tenant-member sharing subject to task capability; do not put private conversation prose into shared summary. Task private notes (if required) are a separate, expressly scoped model; initial MVP need not implement them.
- `source_locator` registered `(app, model, key)` plus verified relation; never a model-provided arbitrary table name. If source is deleted/hidden, show "Source unavailable" without revealing other tenants. Cross-tenant link denied before persistence.

### `SecurityTaskDependency`

`organisation`, `predecessor_task`, `successor_task`, optional `relation_type` (`blocks`), timestamps. DB unique pair; reject self-reference, cross-org joins, duplicate edges and cycles in service inside transaction. Prevent forward completion if blocking predecessor remains unresolved unless authorised human override with recorded reason; domain completion NEVER bypasses authoritative readiness checks.

### `SecurityTaskEvent`

Append-preserving event with organisation, task, actor type/user, action enum, previous/new status, revision, source, event time UTC, request/idempotency ID and small allowlisted metadata. Record in same transaction as task update. Avoid snapshotting secret descriptions and provider-generated prose.

### `JourneyCheckpoint`

Unique `(organisation, user, journey_code)`. Fields `stage_code`, `current_question_key` nullable, `pending_task_id` nullable, `checkpoint_state` (`new`, `active`, `waiting`, `paused`, `journey_complete`), `methodology_version`, `last_domain_revision`, `last_interaction_at`, `version`, user preference (`resume_modal`, `auto_open`) in appropriate profile/preferences model. Canonical stored answers trump an old checkpoint. A checkpoint is not a company-level completion score.

### `AssistantConversation` and `AssistantMessage`

Tenant FK **and** owner-user FK; title/intent, `state` (`active`, `archived`), model/skill versions and timestamps. Message ordered by monotonic sequence, role allowlist, content bounded, classification, source reference list, provider-call ID if used, retention marker. Ownership/visibility policy: private to owner except explicit, authorised shared work artefacts (tasks); no default ability for another org member to read conversation history. No cross-tenant vector index. Enforce bounded conversation length, pagination and expiration policy. Do not store raw gateway secrets/system prompt in DB.

### `AssistantAction` (if needed for verification)

Immutable, organisation+actor scoped record of candidate action, tool name/version, authorised context fingerprint (nonsecret), requested parameters **redacted**, decision/confirmation state, canonical target ID, result category, trace ID. All actual changes still recorded by domain activity events; AssistantAction is trace, not a second task ledger. Consider reuse of existing activity framework instead of duplicate table where viable.

### `SecurityReviewRuleState`

Optional when source entities lack stable review fingerprints: organisation, rule id/version, source id, last evaluated UTC, last occurrence key, last issued task, next eligible due date. Prefer stateless derivation plus `SecurityTask` unique occurrence key; don't create this table unless evidence shows it necessary.

## 2. Exact state transitions

- `open → in_progress | awaiting_external | blocked | awaiting_review | cancelled | done` per validated transition; `in_progress → blocked | awaiting_external | awaiting_review | done | cancelled`; `awaiting_* → in_progress | blocked | done | cancelled`; `blocked → open | in_progress | cancelled`; `done → open` only explicit reopen reason (changed underlying source/scheduled new occurrence should **normally create next occurrence**, not reopen old); `cancelled → open` only authorised restore if policy permits.
- Completion requires a task-level reason and, where the task is tied to an external security fact, confirmation that canonical work actually happened. Permit a human to close a mere "ask IT for information" administrative task after contacting IT, but this **must not** mark the MFA control verified. If task represents an actual overdue policy review, completion must link to policy's own approved review operation, not a checkbox.
- Pending actions shown by IRENE are proposals, not committed writes. On tool success, use DB row revision and returned canonical ID to update checkpoint. On failure, show no success confirmation; retry with idempotency token.

## 3. Services (suggested canonical contracts)

```python
get_task_list(context, *, group=None, status=None, cursor=None) -> TaskPage
get_task_detail(context, task_id) -> TaskDetail
create_task(context, *, kind, source_locator, title, due_at=None, assignee_id=None,
            idempotency_key, confirmation_token=None) -> SecurityTask
transition_task(context, *, task_id, expected_version, next_status, reason,
                idempotency_key, completion_source=None) -> SecurityTask
assign_task(context, *, task_id, expected_version, assignee_id) -> SecurityTask
link_task_dependency(context, *, predecessor_id, successor_id) -> SecurityTaskDependency
get_journey_checkpoint(context, journey_code) -> JourneyState
update_checkpoint(context, *, journey_code, expected_version, transition) -> JourneyState
get_foundations_question(context, question_key) -> StructuredQuestion
submit_foundations_option(context, *, question_key, option_code, confirmation=False,
                          expected_catalogue_version, idempotency_key) -> AnswerReceipt
get_registered_route(context, *, route_key, object_locator=None) -> SafeInternalURL
```

`context` is constructed server-side and contains authenticated user/verified organisation; **no model may choose or replace it**. Treat names as proposed code design, preserving existing function names where already implemented. For `submit_foundations_option`, construct and validate existing `StructuredAnswerForm` using the current `offered_options` and invoke `record_structured_baseline_answer`; do not make direct answer/model writes. Keep semantic parity with `security_baseline.views.foundations_question` including the JML confirmation. The result includes canonical answer, `option_code`, methodology version, review state and updated deterministic explainer.

## 4. Transactions, exactly-once effects and retries

- Task create: validate actor/membership, source existence+same-org, allowed task kind, quota/dedupe; `transaction.atomic` create-or-return using unique idempotency; append event once; return consistent result. Catch `IntegrityError` and re-fetch under same tenant; never generate new occurrence key on retry.
- Task transition: `select_for_update` task by `(pk, organisation)`; validate version/state/permissions, dependency graph, completion criteria; update, append event once. Concurrent updates: one wins; other receives conflict/reload, never silent overwrite.
- Scheduled review: per-tenant batch in stable order, transaction-scoped advisory lock or unique occurrence-key race control; task uniqueness required even if lock fails. Scheduler restart safe; provider failure irrelevant. Never emit duplicate notification for same task+trigger stage; channel preferences apply.
- Answer submit: validate current catalogue/option under active org; transaction/save service; retry with same token returns prior receipt. Do not enforce artificial auto-answering because question selected in the modal; only a real user action is authoritative. If catalogue version changed since render, require refresh before save, not guessed mapping.
- Checkpoint: update after answer receipt, never before; CAS/version or row lock ensures two browser tabs cannot regress the journey to stale question. Manual answer can supersede checkpoint; recompute safe next state when resuming.
- A scheduled review can find a task that's already completed. It should not reopen it on every run. Create a new occurrence if a new due cycle is genuinely due; use source/due/window fingerprints and occurrence-key uniqueness.

## 5. Review scheduling/time arithmetic

Canonical timestamps UTC; business dates interpreted in organisation-configured IANA timezone or configured Europe/London default if explicitly confirmed. DST fold/gap rules must be tested, not guessed. Rules compute `due_at` from existing canonical source review dates, never arbitrary values invented by IRENE. Starter warning windows 30 days, 7 days and overdue are **configurable defaults requiring product approval at implementation**, not a statement that every domain currently has a due date. Suppress trigger if no credible source date. Task owner assigned from existing source owner only if authorised member; otherwise unassigned queue. For rule versions/future policy changes, store trigger rule id/version in task events.

## 6. Event provenance, deletion and migrations

Use additive migrations, indexes on `(organisation,status,due_at)` and per-user checkpoint/conversation keys, PostgreSQL FK protections, consistent `on_delete` behaviours reviewed for retention. Do not delete security-task audit history on normal cancellation. Define account/tenant deletion and data retention/export consistent with privacy programme; unapproved auto-delete of history is forbidden. Classify objects for backups/restore, seed minimal deterministic fixtures, prove fresh-install migrations and full rollback/feature-disable behaviour. No migrations on protected security-baseline canonical answer schema unless separately approved.

## 7. Test contracts

Concurrency: duplicate scheduler runs, two submits of same answer, simultaneous task transitions, two users editing same checkpoint, membership revoked between request and commit, and forced `IntegrityError` retries. Task graph: no cross-org links, cycles/self-reference rejected. Real browser: manual vs IRENE path writes the same answer and yields identical `AnswerSelectionDetail`, derived state and risk/policy effects. Repeated reads mutate nothing. Scheduler idempotent across DST and midnight. Audit event once per committed transition, no sensitive payload. All generated links resolve only to permitted registered routes.
