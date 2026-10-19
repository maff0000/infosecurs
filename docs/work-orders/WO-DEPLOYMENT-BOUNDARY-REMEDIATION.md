# WO — Deployment-Boundary Remediation (Persistent Beta Release Architecture)

**Status: PROPOSED. Architect Acceptance required before any implementation. No structural change or persistent-stack conversion is authorised by this document.**

**Trigger:** 2026-10-19 incident — a routine `git merge --ff-only origin/main` in `/srv/infosecurs`, run as ordinary development reconciliation, was live-reflected into the persistent `infosecurs-relocation` web container because that directory is both the development git working tree and the container's bind-mounted source (`volumes: - .:/app`), running `manage.py runserver` with its autoreloader active. The container picked up unmigrated M010 code against its old schema for ~7 hours before detection. See the separate incident record (not this document) for the full timeline, backup, and impact assessment.

## 1. Root cause this WO addresses

A single filesystem directory served two incompatible roles simultaneously: (a) a live, mutable development git clone, and (b) the literal, live source of a running persistent service, auto-reloaded on every file change. Any git operation in that directory — not only a deliberate deploy — was capable of changing production-adjacent behaviour. The database migration step only runs once, at container start, so code and schema can silently diverge the moment the bind-mounted source changes after that.

## 2. Mandatory requirements (from Central Architecture's Decision 3)

### 2.1 Immutable exact-SHA application images
The persistent `web` image must be built explicitly, once, from a named, recorded commit SHA — never built implicitly as a side effect of `docker compose up` noticing a stale image, and never silently rebuilt by any routine operator command. Each release records the exact SHA it was built from in a durable, queryable place (an image label and a release manifest), not only in operator memory.

### 2.2 No writable source-code bind mount into a persistent application container
Remove `volumes: - .:/app` (or the equivalent) from the persistent deployment's service definition entirely. The running container's code comes only from what was `COPY`'d into the image at build time. A bind mount of this kind remains legitimate for genuinely disposable, developer-only stacks (as used throughout the M010 campaign's own review process) — the distinction this WO draws is strictly: a *disposable* stack may bind-mount; the one *persistent*, long-lived, Customer-Zero-facing stack must not.

### 2.3 Development Git clone separate from runtime
No development, review, or CI git clone/worktree may ever occupy the same filesystem path that any persistent service's deployment configuration references as a source or build context. `/srv/infosecurs` itself is deprecated for this dual role; `gunnar`'s own ongoing git/worktree work already moved to a separate clone (`/srv/openclaw/gunnar-dev/infosecurs`) as an immediate, already-effective interim mitigation — this WO's job is to make that separation structural/enforced, not just a personal habit.

### 2.4 No Django development autoreloader in the persistent runtime
The persistent deployment must not invoke `manage.py runserver` at all. `runserver`'s `StatReloader` is precisely the mechanism that turned a filesystem change into a live behavioural change without anyone issuing a deploy command.

### 2.5 An appropriate application server instead of `runserver`
Adopt a real WSGI/ASGI server (e.g. gunicorn or uvicorn, consistent with whatever this codebase's own `requirements.txt`/deployment conventions already support) for the persistent deployment. `runserver`'s own startup banner already states it is not for this use ("This is a development server... Use a production WSGI or ASGI server instead") — this WO closes that gap for the first time for this stack.

### 2.6 Explicit, independently checked database migration execution during an authorised release
`manage.py migrate` must become a distinct, deliberate release step — run once, under operator control, as part of a named release, with its plan (`migrate --plan`) checked and recorded *before* it is applied — never bundled into the container's own startup command where it silently reruns (as a no-op, usually, but not safely guaranteed to always be a no-op) every time the container restarts for any reason.

### 2.7 Existing PostgreSQL, evidence and questionnaire volumes preserved
None of this WO's implementation may recreate, rename, or re-point any of the three existing named volumes (`infosecurs-relocation_infosecurs_postgres_data`, `_infosecurs_evidence_data`, `_infosecurs_questionnaire_data`). The new release mechanism must attach to them exactly as they already exist.

### 2.8 Atomic or otherwise controlled release and rollback procedures
A release is: build the new image at a named SHA → check the migration plan → apply migrations (if any) → swap the running container to the new image → smoke-test → only then consider the release complete. A rollback is: the same procedure in reverse (swap container back to the previous image SHA), with a documented, pre-checked position on which code/schema combinations are safe to roll back to without a reverse migration (mirroring the compatibility-matching discipline already proven during this incident's own recovery).

### 2.9 Negative test proving Git operations in the developer clone cannot alter the running application
Before this WO is considered implemented (not merely designed), its own acceptance evidence must include a real, executed test: perform an ordinary git operation (merge, checkout, branch switch) in the separated developer clone, and prove — by direct observation of the persistent container's served code/behaviour — that nothing changes. This is the direct, falsifiable antidote to the exact failure mode this WO exists to close.

### 2.10 Disaster-recovery and database compatibility verification
The new release mechanism must be proven, not merely asserted, against: a fresh-install-from-zero migration run; a full backup/restore cycle using the existing governed `scripts/backup.sh`/`scripts/restore.sh` tooling (unmodified); and an explicit statement of which prior code/schema pairs the new mechanism can and cannot roll back to safely.

### 2.11 Independent audit before adoption
A fresh independent reviewer (no memory of this WO's own design/implementation discussions) must verify the above — especially 2.9's negative test and 2.2's actual removal of the bind mount — against the real, built artifact before this WO's implementation is treated as adopted for the persistent stack.

## 3. Explicitly out of scope for this WO

- Any change to the persistent stack before Architect Acceptance of this document.
- M010 deployment of any kind onto the persistent Beta.
- Any password/credential change (separately governed — see the incident's own Decision 4 thread).
- A separate isolated M010 evaluation environment (separately authorised, must not reuse the persistent Beta's database, volumes, or live source bind — tracked independently of this WO).

## 4. Deliverable shape (once accepted)

A bounded implementation PID, built and reviewed the same way every M010 work package was: isolated worktree, independent review before merge, and — per 2.11 above — a fresh independent audit of the finished artifact (not just this design) before the persistent stack is ever switched over.

## 5. Acceptance

Architect Acceptance of this Work Order authorises writing the implementation PID and beginning design-level prototyping in a disposable stack only. It does **not** authorise touching `/srv/infosecurs`, rebuilding `infosecurs-relocation-web`, or any migration/configuration change on the persistent stack — a second, separate authorisation gates the actual cutover, after 2.9–2.11 are satisfied.
