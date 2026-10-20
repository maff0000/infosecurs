# WO — Deployment-Boundary Remediation (Persistent Beta Release Architecture)

**Status: PROPOSED. Architect Acceptance required before any implementation. No structural change, persistent-stack conversion, migration, image replacement, or configuration change on the live `infosecurs-relocation` stack is authorised by this document or its acceptance.**

**Trigger:** `docs/evidence/INCIDENT-2026-10-19-DEPLOYMENT-BOUNDARY-EXPOSURE.md` (PR #115, merged) — the full timeline, backup, and impact assessment live there, not here.

## 0. Governance — parent authority, amendment chain, scope

**Parent authority document:** `docs/delivery/M005-M006-HOST-RELOCATION-GATE.md`, closed via `docs/evidence/M005-M006-HOST-RELOCATION-GATE.md` (accepted M005 SHA `dee18ef214bf892a41f2d52f2e33650e479e69cc`). That gate established the still-current **Durable placement rule**:

> `INFOSECURS DEVELOPMENT HOST = dell-debian`
> `INFOSECURS PROJECT_ROOT = /srv/infosecurs`

At the time, that rule correctly fixed where Infosecurs lived after moving off `trinity`. It did not anticipate, and does not address, a **second** question this WO exists to answer: whether the same `PROJECT_ROOT` path may *simultaneously* serve as an ongoing, long-lived development git working tree *and* a persistent application container's live source. The 2026-10-19 incident is the proof that it must not. This WO is therefore an **amendment to that rule**, not a retrospectively-invented new architecture: it narrows "PROJECT_ROOT" to mean the deployment's build context only, and introduces a *separate*, explicitly-named development clone as a new, additional placement rule alongside it.

**Governing PID authority:** `PID.md` §6.1 ("Deployment boundary (persistent runtime)", added by the accepted `docs/architecture/DEPLOYMENT-BOUNDARY-PID-AMENDMENT.md`, PR #116) states the architecture decision this WO implements, verbatim. `PID.md` §11 states the mandatory delivery doctrine this WO follows: **NO PID → NO WORK ORDER → NO IMPLEMENTATION** — §6.1 is that PID; this is that Work Order. This WO implements an already-authorised principle; it does not introduce a new one.

**Exact base SHA this WO is written against:** `main` @ `26842539848681cf6f035aa3c22c56786bd42d91` (post-merge of PR #116, the accepted deployment-boundary PID amendment; the persistent stack itself remains at `ad996bfa4527623d095862199b46db6e0ea94fd0`, per the incident record).

**Bounded implementation scope** (once accepted): a new, documented release mechanism for the *existing* `infosecurs-relocation` deployment only — image build, migration execution, container swap, rollback. Nothing in M010, M009B Increments 3–4, or any other product feature is in scope.

**Explicit exclusions:**
- No change to any product/application code.
- No change to the *identity* of the `postgres`/`evidence`/`questionnaire` named volumes — never recreated, renamed, or re-pointed. This does **not** mean their contents are frozen: an authorised, independently-assessed schema migration (§2) necessarily modifies database contents by design. What is excluded is any change to *which* volume the deployment attaches to, or any out-of-band content modification outside the explicit migration step.
- No M010 deployment, no live Adviser Mode, no Customer Zero reset, no password rotation — all separately governed.
- No change to the Trinity LiteLLM gateway relationship established by the relocation gate.
- Architect Acceptance of this WO authorises exactly two things: writing the implementation PID, and building/rehearsing the release mechanism in a **disposable** stack (§3.1–3.4). It does **not** authorise touching the persistent `infosecurs-relocation` stack in any way — that requires a separate, explicit cutover authorisation (§3.5), granted only after the disposable rehearsal (§3.1–3.3) and its independent audit (§3.4) both pass.

**Tests, audit and acceptance criteria:** defined per requirement in §1 below; the overall acceptance sequence is §3.1–3.3 (disposable rehearsal: negative test, disaster-recovery/compatibility proof) → §3.4 (independent audit of the rehearsal) → §3.5 (cutover authorisation decision) → the actual, authorised cutover → §3.6 (post-cutover verification). Central Architecture issues both the design acceptance of this document and, separately, the cutover authorisation — the same two-gate pattern already used for M010's implementation vs. merge.

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
See §3.2 — this is executed as part of the mandatory disposable rehearsal, not asserted.

### 1.10 Disaster-recovery and database compatibility verification
See §3.3.

### 1.11 Independent audit before adoption
See §3 — a fresh reviewer with no memory of this WO's own design/implementation discussion verifies the rehearsal evidence before any cutover authorisation is requested.

## 2. Cutover safety — release-state and schema-compatibility matrix (C2)

A release moves through four states. Each row states whether that transition is safe, what controls writes, and what recovery is available if it fails.

| # | State transition | Writes during this state | Failure in this state → recovery |
|---|---|---|---|
| 1 | **Build**: new image built from a named SHA, in a separate build step, no effect on the running container yet. | Unaffected — old container still serving. | Build failure: discard the new image, no live impact, nothing to roll back. |
| 2 | **Migration plan check**: `migrate --plan` run against the *live* database using the *new* image, read-only, before anything is applied. | Unaffected — read-only plan, old container still serving. | Plan shows unexpected/destructive operations: **STOP here.** Do not proceed to apply. Return the plan to Central Architecture for review — this is exactly the gate that would have caught the 2026-10-19 incident's schema/code mismatch *before* any code swap, had it existed. |
| 3 | **Apply migrations**: `migrate --noinput` run once, explicitly, against the live database, *before* the container is swapped. | **Old code is still serving reads/writes during this step** — see "write quiescence" below for exactly when that is, and is not, safe. | **Migration fails partway, correction of a prior overclaim:** PostgreSQL wraps *each individual migration* in its own transaction, so *that one* migration's partial effects roll back on failure. It does **not** automatically roll back any *earlier* migration in the same release that already committed successfully — a multi-migration release can fail partway through and leave the database in a state that is neither the old schema nor the new one. Recovery from that state is a manual, migration-specific decision (write and apply a forward-fixing migration, or a reviewed reverse migration for exactly the migrations that did apply), never an assumed single automatic rollback. **Do not swap the container if this step did not complete and verify cleanly**, and do not assume a clean state to resume from without checking `showmigrations` against what is actually in the database. |
| 4 | **Container swap**: stop the old container, start the new image against the now-migrated database. | A short window (seconds, not the current multi-hour exposure) where the service is down; this is the "atomic" boundary — nothing serves the new code until this single step. | Smoke test (§3.6) fails after swap: **roll back the container only** (swap back to the previous image) — this is safe **only for a release independently demonstrated expand-only** per the discipline below; it is explicitly **not** a safe recovery for any release that has not had that compatibility demonstrated, or that is a known contract change — that distinction is made and recorded *before* the release is authorised, never discovered after a failed smoke test. |

**Migration default for this WO's own initial deployment-boundary repair**: zero database migrations. This WO's purpose is to secure the deployment topology, not to upgrade the product — the first release built under this mechanism should be a pure topology change (image build, bind-mount removal, server swap) against the schema exactly as it stands today, with nothing in §2's migration rows exercised for real until a genuinely separate, later release actually needs one.

**Expand/contract discipline, corrected**: "additive" is not a synonym for "automatically backward-compatible." A new nullable column or a new table that nothing yet reads is genuinely safe for old code to run alongside unmodified. A new `NOT NULL` column with no default, a new unique constraint over existing data, a renamed or dropped column, or any FK/constraint change that could reject a write the old code still issues, is **not** safe merely because it is schema-additive in the sense of "nothing was deleted" — old code can still fail against it. Every migration-bearing release (not merely every "contract" release) must state, for each migration, whether old-code reads and old-code writes are demonstrated compatible with the new schema — demonstrated by the §3.3 disaster-recovery/compatibility rehearsal running the *actual* old code against the *actual* new schema, not by appeal to "this codebase's migrations are usually additive." A release is *expand-only* only once that demonstration has actually been run for every migration in it; otherwise it is treated as a *contract* release regardless of what the migration file itself technically does, and requires its own, separately reviewed rollback plan before the release is authorised.

**Write quiescence — explicit criteria**: old code may keep serving reads/writes through step 3 *only* for a release whose every migration has passed the compatibility demonstration above. For any release containing even one migration that has not passed it, or that is a known contract change, writes must be quiesced (the persistent `web` service stopped, mirroring §1.6's own release-step discipline and the existing `scripts/backup.sh` convention of stopping `web` to quiesce writes) before that migration applies, and only resumed after the full cutover (step 4) completes and the §3.6 smoke test passes. This is a release-classification decision made and recorded before the release runs, never improvised mid-release.

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
