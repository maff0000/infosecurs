# M010 — Preflight (WO-M010-GUNNAR-ONE-PUSH.md §1)

**Status:** GREEN. Proceeding directly to Work Package A per Central Architecture's explicit instruction (no further approval gate required for this step).
**Integration branch:** `wo/M010-irene-ai-first-campaign`, cut from canonical `main` @ `4b4a2a10ac566c22786d29c282fa6c4f1520f07b` (the M010 docs-incorporation merge, PR #111).

## 1. Canonical main and M009B boundaries

- Canonical `main` reconfirmed at `4b4a2a1` immediately before cutting the integration branch.
- No M009B Increment 3/4 branch exists anywhere, local or remote (`git branch -a` grepped explicitly) — confirmed zero code-level conflict exists to reconcile. M009B Increments 1–2 are merged and closed (PRs #107, #109); Increments 3–4 remain explicitly deferred per Central Architecture's own instruction, not implemented, not touched by this campaign.

## 2. Inventory of current M008 / entitlements / scheduling implementations

Every symbol the architecture pack names was independently confirmed to exist, with the exact signature/name expected — not assumed from the pack's own description:

- `security_baseline.catalogue`: `CATALOGUE_KEYS`, `CATALOGUE_VERSION` ("2026-10-baseline-v2").
- `security_baseline.structured_catalogue`: `STRUCTURED_OPTIONS`, `FOUNDATIONS_QUESTION_METHODOLOGY_VERSION` ("2026-10-structured-v1"), `resolve_option`.
- `security_baseline.stage4`: `offered_options(control_key, organisation)`, `QUESTION_COPY`, `explainer_for`, `stage4_progress`, `progress_copy`.
- `security_baseline.forms`: `StructuredAnswerForm`.
- `security_baseline.services`: `record_structured_baseline_answer`.
- `security_baseline.views`/`urls`: `foundations_start`, `foundations_question` (both `@login_required @require_capability()`), routes `security_baseline:foundations_start`/`security_baseline:foundations_question`.
- `entitlements.metrics`: `get_security_foundations_completion`, `SecurityFoundationsCompletion`, `RequirementState`, `get_foundations_requirement_states`.
- `entitlements.{models,capabilities,decorators,tiers,navigation}` all present with the expected module boundaries from prior M009B work.
- Exactly **16** existing `ProductArea` rows confirmed in `entitlements/migrations/0002_seed_product_areas.py` (home, foundations, customer_assurance, security, security_state, baseline, assets, risks, evidence, remediation, policies, company, profile, governance, workplace, activity) — matching M010A PID's own stated count exactly. None altered by this preflight.
- **No existing scheduler/cron/celery infrastructure** found anywhere in the repository or `docker-compose.yml`. This matches M010D's own design: the deliverable is a plain, one-shot Django management command (the existing pattern already used by `run_questionnaire_ai_eval`, `run_policy_ai_eval`, `run_ai_eval`, `create_customer_zero`), invocable by whatever host-level scheduler a future deployment provides — no daemon/worker process is built by this campaign.
- Two-tenant adversarial fixtures (`org_a`, `org_b`, `user_a`, `user_b`, `member_a`, `member_b`, `client_a`, `client_b`) confirmed present in `organisations/tests/conftest.py`, reusable directly by every M010 package's test suite exactly as the architecture pack assumes.

**No discrepancy found between the architecture pack's assumptions and the real, current codebase.**

## 3. Integration branch and disposable test infrastructure

- `wo/M010-irene-ai-first-campaign` created from `origin/main` @ `4b4a2a1`, in its own isolated worktree (`/tmp/m010-integration` on the build host), never touching the shared canonical clone or the persistent `/srv/infosecurs` deployment.
- Disposable Docker Compose stack (`-p m010integration`, unique ports `POSTGRES_HOST_PORT=19730`/`WEB_HOST_PORT=19731`), fresh migration (`No migrations to apply` — confirms canonical main's migration state is clean before any M010 code).

## 4. Baseline regression counts (pre-M010, for later before/after comparison)

Both real CI jobs run against this exact base commit, fresh `--create-db` test databases:

- **`ci/unit` + `entitlements/tests/`** (not in either curated CI list, run separately as established practice): **854 passed, 0 failed.**
- **`ci/integration`**: **1199 passed, 7 skipped, 1 xfailed, 0 failed.**
- `gitleaks detect --source=. -v`: **no leaks found** (193 commits).

These counts are the pre-M010 baseline; any work-package regression check compares against these, not an assumed "all green" with no number attached.

## 5. Preflight evidence and disposition

GREEN. No blocking discrepancy, no M009B conflict, no missing dependency. Proceeding directly to Work Package A (M010A — Shared Security Task Spine) per Central Architecture's explicit "start now, no further approval required" instruction.
