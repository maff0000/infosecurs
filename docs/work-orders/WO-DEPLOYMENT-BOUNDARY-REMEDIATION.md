# WO — Deployment-Boundary Remediation (Persistent Beta Release Architecture)

**Status: PROPOSED. Architect Acceptance required before any implementation. No structural change, persistent-stack conversion, migration, image replacement, or configuration change on the live `infosecurs-relocation` stack is authorised by this document or its acceptance.**

**Trigger:** `docs/evidence/INCIDENT-2026-10-19-DEPLOYMENT-BOUNDARY-EXPOSURE.md` (PR #115, merged) — the full timeline, backup, and impact assessment live there, not here.

## 0. Governance — parent authority, amendment chain, scope

**Parent authority document:** `docs/delivery/M005-M006-HOST-RELOCATION-GATE.md`, closed via `docs/evidence/M005-M006-HOST-RELOCATION-GATE.md` (accepted M005 SHA `dee18ef214bf892a41f2d52f2e33650e479e69cc`). That gate established the still-current **Durable placement rule**:

> `INFOSECURS DEVELOPMENT HOST = dell-debian`
> `INFOSECURS PROJECT_ROOT = /srv/infosecurs`

At the time, that rule correctly fixed where Infosecurs lived after moving off `trinity`. It did not anticipate, and does not address, a **second** question this WO exists to answer: whether the same `PROJECT_ROOT` path may *simultaneously* serve as an ongoing, long-lived development git working tree *and* a persistent application container's live source. The 2026-10-19 incident is the proof that it must not. This WO is therefore an **amendment to that rule**, not a retrospectively-invented new architecture: it narrows "PROJECT_ROOT" to mean the deployment's build context only, and introduces a *separate*, explicitly-named development clone as a new, additional placement rule alongside it.

**Also anchored to:** `PID.md` §6 ("Architecture"), which already states the principle this WO exists to make true in practice — *"Immutable production artifact by exact Git SHA"* — and §11 ("Repository and GitHub doctrine" — GitHub, not a live filesystem path, is project truth). This WO implements an already-authorised principle; it does not introduce a new one.

**Exact base SHA this WO is written against:** `main` @ `fbaf2ddc55a63d2fbba0ccd083f9a14892d581d8` (post-incident-record merge, pre-M010-deployment-anywhere; the persistent stack itself remains at `ad996bfa4527623d095862199b46db6e0ea94fd0`, per the incident record).

**Bounded implementation scope** (once accepted): a new, documented release mechanism for the *existing* `infosecurs-relocation` deployment only — image build, migration execution, container swap, rollback. Nothing in M010, M009B Increments 3–4, or any other product feature is in scope.

**Explicit exclusions:**
- No change to any product/application code.
- No change to the `postgres`/`evidence`/`questionnaire` named volumes or their contents.
- No M010 deployment, no live Adviser Mode, no Customer Zero reset, no password rotation — all separately governed.
- No change to the Trinity LiteLLM gateway relationship established by the relocation gate.
- No implementation of this WO's design until a separate, explicit cutover authorisation (§3) is granted, after §2's rehearsal gate passes.

**Tests, audit and acceptance criteria:** defined per requirement in §1 below; the overall acceptance sequence is §2 (rehearsal, disposable) → independent audit of the rehearsal → §3 (cutover authorisation decision) → the actual, authorised cutover → §2.9-equivalent post-cutover verification. Central Architecture issues both the design acceptance of this document and, separately, the cutover authorisation — the same two-gate pattern already used for M010's implementation vs. merge.

## 1. Mandatory requirements (from Central Architecture's Decision 3, verbatim scope)

### 1.1 Immutable exact-SHA application images
The persistent `web` image is built explicitly, once, from a named, recorded commit SHA — never built implicitly as a side effect of `docker compose up` noticing a stale image, never silently rebuilt by any routine operator command. Each release records its exact source SHA in a durable, queryable place (an image label and a release manifest), not only in operator memory.

### 1.2 No writable source-code bind mount into a persistent application container
Remove `volumes: - .:/app` (or equivalent) from the persistent deployment's service definition. The running container's code comes only from what was `COPY`'d into the image at build time. A bind mount remains legitimate for genuinely disposable, developer-only stacks (as used throughout the M010 review process) — the line this WO draws is: *disposable* stacks may bind-mount; the one *persistent*, Customer-Zero-facing stack must not.

### 1.3 Development Git clone separate from runtime
No development, review, or CI git clone/worktree may ever occupy the filesystem path any persistent service's deployment configuration references as a source or build context. `/srv/infosecurs` is deprecated for the dual role described in §0. The Delivery Controller's own ongoing git/worktree work has already moved to `/srv/openclaw/gunnar-dev/infosecurs` as an immediate, already-effective interim mitigation (not itself the structural fix this WO designs).

### 1.4 No Django development autoreloader in the persistent runtime
The persistent deployment must not invoke `manage.py runserver` at all — its `StatReloader` is precisely the mechanism that turned an unrelated filesystem change into a live behavioural change with no deploy command issued.

### 1.5 An appropriate application server instead of `runserver`
A real WSGI/ASGI server (gunicorn or uvicorn, consistent with this codebase's own existing conventions), for the persistent deployment only.

### 1.6 Explicit, independently checked database migration execution during an authorised release
`manage.py migrate` becomes a distinct, deliberate release step — run once, under operator control, as part of a named release, with its plan (`migrate --plan`) checked and recorded *before* it is applied — never bundled into the container's own startup command, where it reruns on every restart for any reason.

### 1.7 Existing PostgreSQL, evidence and questionnaire volumes preserved
No part of this WO's implementation may recreate, rename, or re-point `infosecurs-relocation_infosecurs_postgres_data`, `_infosecurs_evidence_data`, or `_infosecurs_questionnaire_data`. The new mechanism attaches to them exactly as they already exist.

### 1.8 Atomic or otherwise controlled release and rollback procedures
See §2's compatibility matrix for the exact sequencing and failure handling this requirement resolves to.

### 1.9 Negative test proving Git operations in the developer clone cannot alter the running application
See §2.4 — this is executed as part of the mandatory rehearsal, not asserted.

### 1.10 Disaster-recovery and database compatibility verification
See §2.5.

### 1.11 Independent audit before adoption
See §3 — a fresh reviewer with no memory of this WO's own design/implementation discussion verifies the rehearsal evidence before any cutover authorisation is requested.

## 2. Cutover safety — release-state and schema-compatibility matrix (C2)

A release moves through four states. Each row states whether that transition is safe, what controls writes, and what recovery is available if it fails.

| # | State transition | Writes during this state | Failure in this state → recovery |
|---|---|---|---|
| 1 | **Build**: new image built from a named SHA, in a separate build step, no effect on the running container yet. | Unaffected — old container still serving. | Build failure: discard the new image, no live impact, nothing to roll back. |
| 2 | **Migration plan check**: `migrate --plan` run against the *live* database using the *new* image, read-only, before anything is applied. | Unaffected — read-only plan, old container still serving. | Plan shows unexpected/destructive operations: **STOP here.** Do not proceed to apply. Return the plan to Central Architecture for review — this is exactly the gate that would have caught the 2026-10-19 incident's schema/code mismatch *before* any code swap, had it existed. |
| 3 | **Apply migrations**: `migrate --noinput` run once, explicitly, against the live database, *before* the container is swapped. New columns/tables are additive (expand) relative to the still-running old code, which must not reference them yet — this requirement constrains what the application code itself may do in the same release (see "expand/contract discipline" below), it is not satisfied by this release mechanism alone. | **Old code is still serving reads/writes during this step.** Migrations in this codebase's own established pattern (confirmed throughout the M010 campaign's own migration set) are additive/backward-compatible by convention — no column is dropped or renamed in the same release that also removes the code using it. | Migration fails partway: Django wraps each migration in a transaction where the database supports it (PostgreSQL does); a failed migration rolls back to the pre-migration schema automatically. Re-run only after root-causing the failure. **Do not swap the container if this step did not complete and verify cleanly.** |
| 4 | **Container swap**: stop the old container, start the new image against the now-migrated database. | A short window (seconds, not the current multi-hour exposure) where the service is down; this is the "atomic" boundary — nothing serves the new code until this single step, and nothing can serve a partially-migrated-but-old-code combination because step 3 already completed first. | Smoke test (§2.6) fails after swap: **roll back the container only** (swap back to the previous image) — this is safe *only if* the migrations applied in step 3 are themselves backward-compatible with the old code, which is why step 3 happens before step 4 and why the expand/contract discipline below is load-bearing, not optional. If the new migrations are *not* safely compatible with the old code (a genuine contract/breaking change), rolling back the container is **not** a safe recovery — this is flagged to Central Architecture before the release, never discovered after. |

**Expand/contract discipline** (closes "how writes are controlled during cutover"): every release in this mechanism is either *expand-only* (additive migrations, old code unaffected, safe to roll back the container alone) or is explicitly flagged as a *contract* release (removes/renames something old code depends on) requiring its own, separately reviewed rollback plan before the release is authorised — never discovered as a surprise at step 4. This mirrors the exact finding M010F's own evidence already recorded about this codebase's migrations.

**Writes during cutover**: Beta-scale traffic does not require a maintenance-mode flag for the few-second container-swap window (step 4); it does require that migrations never apply concurrently with a reload of old code that doesn't expect them — which this four-step ordering guarantees structurally (reads/writes continue against old code through step 3; nothing touches new code until step 4, by which point the schema already matches).

## 3. Negative proof — rehearsal before cutover, verification after (C3)

**No persistent migration, image replacement, or configuration change is authorised by Architect Acceptance of this document.** Acceptance authorises exactly: writing the implementation PID and prototyping in a disposable stack. A second, separate authorisation gates the actual persistent cutover.

### 3.1 Disposable-stack rehearsal (mandatory, before any persistent cutover)
Build the full release mechanism (§1.1–§1.8) against a disposable stack that mirrors `infosecurs-relocation`'s shape (same volume names pattern, same image base, a synthetic database seeded to resemble its migration state) — never the real persistent stack or its real data.

### 3.2 The negative test itself (§1.9), executed on the rehearsal stack
Perform an ordinary git operation (merge, checkout, branch switch) in the *separated* developer clone, and prove — by direct observation of the rehearsal stack's served code/behaviour — that nothing changes. This is the direct, falsifiable antidote to the exact failure mode in the incident record.

### 3.3 Disaster-recovery and compatibility verification (§1.10), on the rehearsal stack
A fresh-install-from-zero migration run; a full backup/restore cycle using the existing, unmodified `scripts/backup.sh`/`scripts/restore.sh`; an explicit, written statement of which prior code/schema pairs the new mechanism can and cannot roll back to safely (feeding directly from §2's matrix).

### 3.4 Independent audit of the rehearsal (§1.11)
A fresh reviewer, with no memory of this WO's design or implementation discussions, independently verifies 3.1–3.3 against the real, built rehearsal artifact — not against this document's claims about it. Only after that audit returns GREEN does the Delivery Controller request cutover authorisation from Central Architecture.

### 3.5 Cutover authorisation (separate decision, not implied by design acceptance)
A distinct, explicit decision from Central Architecture, naming the exact SHA to deploy, after 3.1–3.4 are GREEN. Only this decision authorises touching the persistent `infosecurs-relocation` stack.

### 3.6 Bounded post-cutover verification (once actually authorised and executed)
The same smoke-test shape already proven during the 2026-10-19 incident recovery: health endpoint, login page, manual Foundations routes, no migration warnings, no unplanned writes, no M010 (or any out-of-scope) feature exposed — run against the real persistent stack immediately after the real cutover, with authority to roll back per §2's matrix if any gate fails.

## 4. Deliverable shape (once accepted)

A bounded implementation PID, built and reviewed the same way every M010 work package was: isolated worktree, independent review before merge of the rehearsal mechanism's own code, and the §3.4 independent audit of the rehearsal artifact before any cutover authorisation is even requested.
