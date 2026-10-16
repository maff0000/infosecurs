# M009B Increment 2 — M005 Prepare/Persist Extraction

**Milestone:** M009B — Foundations Readiness + CSV + Bulk Orchestration (Increment 2 of 4)
**Parent PID:** `docs/pids/M009-AMENDMENT-2026-10-13-CSV-ASSURANCE-READINESS.md` §6.1b
**Work Order:** `docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md` §3
**Implementation branch:** `wo/M009B-increment2-m005-prepare-persist`
**Base:** `32b37e96f28ff49840143a84742a3d1583f95fde` (canonical `main`, post Increment-1 closure merge, PR #108)
**Status:** Implementer dispatch complete. Pure, behaviour-preserving extract-method refactor of `questionnaire/services.py` only. No functional change intended or observed anywhere.

## Scope (WO §3.1)

Exactly the extract-method refactor specified in the amendment §6.1b, nothing more:

1. New frozen dataclass `PreparedQuestionnaireResponse` (fields, in order: `organisation`, `question`, `interpretation`, `interpretation_record`, `outcome`, `outcome_warnings`, `grounding_snapshot`, `draft`, `drafting_record`, `actor`).
2. New function `prepare_questionnaire_response(organisation, question, *, actor, interpretation_gateway=None, drafting_gateway=None) -> PreparedQuestionnaireResponse` — the literal interpret → ground → derive-outcome → draft portion of the old `generate_questionnaire_response`, in the same order, nothing added or removed. **Not** wrapped in `@transaction.atomic`.
3. `_persist_response` renamed to `persist_prepared_response(prepared: PreparedQuestionnaireResponse) -> QuestionnaireResponse` — identical body, identical `@transaction.atomic` decorator; every former keyword argument reference becomes `prepared.<field>`.
4. `generate_questionnaire_response` becomes the two-line composition (`prepare_questionnaire_response(...)` then `persist_prepared_response(...)`), with its exact original public signature and its docstring copied onto itself **byte-identical** (independently verified by AST comparison — see below).
5. A short new docstring added to each of the three new/renamed symbols; `generate_questionnaire_response`'s own docstring untouched.

`prepare_questionnaire_response` does **not** take a `liveness_check` parameter — that is Increment 3's own, later, separately-disclosed addition, deliberately excluded here per WO §3.1.

## The most behaviour-sensitive detail

The `record_event(..., ActivityEvent.EVENT_QUESTION_INTERPRETED, ...)` call moved into `prepare_questionnaire_response`, **outside** any atomic block — exactly as it fired in the pre-refactor `generate_questionnaire_response` (a plain, non-atomic `record_event` call made immediately after the interpretation call succeeds, before drafting runs). Because `prepare_questionnaire_response` itself carries no `@transaction.atomic` decorator, this event still fires as soon as interpretation succeeds and still survives a later drafting failure, unrolled-back — byte-for-byte the same semantics as before the extraction, not merely "still fires somewhere."

## Exact diff — `questionnaire/services.py`

```
 2 files changed, 232 insertions(+), 82 deletions(-)
 questionnaire/services.py            | 200 +++++++++++++++++++++--------------
 questionnaire/tests/test_services.py | 114 ++++++++++++++++++++
```

Summary of the `services.py` diff:
- Imports: added `import dataclasses` and `from typing import Any` (needed only because a dataclass requires an annotation on every field, unlike the old function's unannotated keyword parameters — no other import changed).
- `_persist_response` deleted as a free function; its exact body reappears, unchanged, as `persist_prepared_response(prepared)`, with every reference to a former parameter rewritten to `prepared.<name>` (mechanical substitution only — no internal local variable renamed, no statement reordered, no call changed. `_initial_current_answer_text`/`_hash_grounding_snapshot` called exactly as before).
- The pipeline body of the old `generate_questionnaire_response` (gateway defaults → interpretation request/call → `EVENT_QUESTION_INTERPRETED` → grounding/outcome → drafting request/call) reappears unchanged, as the new `prepare_questionnaire_response`, ending in a `PreparedQuestionnaireResponse(...)` construction from the same local variables already in scope (no renaming, no recomputation).
- `generate_questionnaire_response` keeps its exact signature and verbatim docstring; its body is now exactly:
  ```python
  prepared = prepare_questionnaire_response(
      organisation, question, actor=actor,
      interpretation_gateway=interpretation_gateway, drafting_gateway=drafting_gateway,
  )
  return persist_prepared_response(prepared)
  ```
- One inline comment inside the moved pipeline code was updated from "NOT wrapped in `_persist_response`'s atomic block below" to "NOT wrapped in `persist_prepared_response`'s atomic block" — a factual correction made necessary by the rename (the old comment would otherwise point at a function name that no longer exists and a position ("below") that is no longer true), not a behaviour or logic change.

**Independently verified, not just asserted:**
- `generate_questionnaire_response`'s docstring: AST-extracted from both the pre-refactor (`origin/main` @ `32b37e9`) and post-refactor file — **byte-identical** (1173/1173 chars, `IDENTICAL: True`).
- `generate_questionnaire_response`'s signature (`ast.dump(node.args)`): **identical** AST between pre- and post-refactor.
- `git status --porcelain` on the working tree: only `questionnaire/services.py` and `questionnaire/tests/test_services.py` modified — zero other files touched, zero new files.

## Disclosed, deliberately-untouched stale references (out of scope)

Two comments elsewhere in the codebase still name the retired `_persist_response` identifier. Both are explicitly out of scope and were left untouched:
- `questionnaire/services.py` line ~176, inside `_initial_current_answer_text`'s own docstring ("see `_persist_response` below") — `_initial_current_answer_text` is on the WO's explicit do-not-touch list ("No changes to … `_initial_current_answer_text` … in any way"), so this docstring is left exactly as it was, even though the reference is now slightly stale (the renamed function is no longer literally "below" in the same function).
- `questionnaire/eval/harness.py` line ~317, a comment inside `_run_case` ("inside `questionnaire.services._persist_response`") — `harness.py` is not `questionnaire/services.py` and is not a test file, so it is outside this increment's permitted file scope regardless of content.

Neither is a live code reference (both are prose inside docstrings/comments); both are flagged here rather than silently left unexplained, per the project's own evidence-disclosure convention (see `docs/evidence/M009B-INCREMENT-1-READINESS-CSV-INGESTION.md`'s own precedent for this kind of disclosure).

## New test (WO §3.7) — `questionnaire/tests/test_services.py`

One new, narrow differential-equivalence test,
`test_prepare_then_persist_matches_generate_questionnaire_response_directly`:
calls `prepare_questionnaire_response(...)` then `persist_prepared_response(...)` separately (deterministic fake gateways, same organisation/question/actor), and separately calls `generate_questionnaire_response(...)` directly with identical inputs reusing the **same** question. Every concrete `QuestionnaireResponse` field is compared **explicitly, one at a time** (iterating `QuestionnaireResponse._meta.get_fields()`, not a blanket `==`), excluding only the fields that are inherently per-call/per-row identity and therefore expected to differ by construction: `id` (primary key), `created_at`/`updated_at` (auto timestamps), and the two `AIInvocationRecord` FKs (`interpretation_invocation_record`, `drafting_invocation_record` — each separate pipeline run creates its own fresh pair of AI-invocation rows, exactly as two separate question/response rows would). The test additionally asserts these excluded identity fields really do differ (sanity: the two rows are genuinely independent, not accidentally reused), and that the two `AIInvocationRecord` rows' own `task_type` content (not identity) still matches. No other new test, no new fixture, nothing else in the file changed except one import line gaining the two new symbols.

Result: **PASSED** (confirmed both in isolation and as part of the full 20-test `test_services.py` run).

## Golden-corpus before/after proof (WO §3.8, mandatory verification #1)

Ran `python manage.py run_questionnaire_ai_eval --gateway=fake` against:
- **Before**: a clean `git worktree add` checkout of `origin/main` @ `32b37e9` (pre-refactor), own disposable Docker Compose stack, own disposable Postgres.
- **After**: the refactored branch, in this dispatch's own disposable stack.

Both runs: **14/14 cases, `overall_verdict: "green"`**, identical `token_totals` (interpretation: 896/448, drafting: 896/448).

Programmatic comparison (`json.load` both reports, pop `generated_at` from each, compare the remaining dicts):
```
before generated_at: 2026-10-16T16:49:15.644650+00:00
after  generated_at: 2026-10-16T16:49:23.369604+00:00
case_count before/after: 14 14
IDENTICAL (excluding generated_at): True
```
Every field of every one of the 14 cases — `objective_checks`, `heuristic_flags`, `actual_outcome`, `actual_interpretation`, `raw_generated_answer`, `resolved_model`, token counts, `human_judgement_properties_pending_review` — is byte-identical before and after. The only difference between the two JSON reports in their entirety is the wall-clock `generated_at` timestamp, which is expected to differ between any two runs and is not a behavioural property.

## Full test-run evidence (mandatory verification #2–#4)

All runs below are against the refactored code, **CI-faithful** (`DJANGO_ENV=test`, matching `.github/workflows/ci.yml`'s env exactly; a guaranteed-fresh test database via `--create-db`, matching CI's always-fresh ephemeral Postgres service container — see the disclosed note below on why `--create-db` was used for the final, reported numbers).

**M005-adjacent test files** (grep across `questionnaire/tests/` and the whole repo for `generate_questionnaire_response`/`accept_questionnaire_response`/`edit_questionnaire_response_text`/`_initial_current_answer_text` — no other app's tests reference any of these):
```
questionnaire/tests/test_services.py ............... PASSED (20/20, incl. the new differential-equivalence test)
questionnaire/tests/test_review_workflow.py ......... PASSED (14/14)
questionnaire/tests/test_activity_events.py ......... PASSED (4/4)
= 39 passed in 41.40s
```

**M005 eval test files** (`test_eval_golden_corpus.py`, `test_eval_harness.py`, `test_eval_command.py` — all three are already in the real `ci/integration` curated list, confirmed by reading `.github/workflows/ci.yml` directly, so no separate ad-hoc invocation was needed per WO §3.12/item 4's instruction):
```
55 passed in 14.13s
```

**`ci/unit` curated list** (read directly from `.github/workflows/ci.yml`, run verbatim, fresh database):
```
552 passed in 166.69s (0:02:46)
EXIT_CODE=0
```

**`ci/integration` curated list** (read directly from `.github/workflows/ci.yml`, run verbatim, fresh database):
```
1199 passed, 7 skipped, 1 xfailed, 0 failed in 1112.14s (0:18:32)
EXIT_CODE=0
```

**Disclosed, investigated, and resolved false alarm:** an earlier rerun of the `ci/integration` list, executed with pytest-django's default `--reuse-db` (reusing the SAME test database across two separate back-to-back invocations of the full curated list, purely as a local convenience to get a second number quickly), showed 5 failures, all confined to `identity/tests/test_federated_login.py` / `identity/tests/test_unsafe_linking.py` (`User.objects.count()` assertions expecting 1 row, finding 2). None of the 5 failing tests touch `questionnaire`, `generate_questionnaire_response`, or any file this increment changed. Investigated before accepting any result: (1) reran the two identity test files alone with a forced fresh database (`--create-db`) — all 11 tests passed; (2) reran the entire curated `ci/integration` list once more with a forced fresh database — **1199 passed, 7 skipped, 1 xfailed, 0 failed**, matching Increment 1's own previously-recorded `1199/7/1` baseline exactly. Conclusion: the 5 failures were a `--reuse-db` cross-invocation database-state artifact of running the same large combined list twice against one retained local test database — real CI (`.github/workflows/ci.yml`) always provisions a brand-new ephemeral Postgres service container per job run and would never reuse state this way, so this was never a defect in the refactor, the test suite, or `identity/`. The number reported above as authoritative is the fresh-database run.

## `makemigrations --check` (mandatory verification #5)

```
$ python manage.py makemigrations --check --dry-run
No changes detected
```
No schema/model change — this increment is pure code structure, as required.

## `gitleaks` / `pip-audit` (mandatory verification #6)

```
$ gitleaks detect --source=. -v
190 commits scanned.
scanned ~6.87 MB in 1.45s
no leaks found
```
```
$ pip-audit -r requirements.txt   (run inside the project's own Python 3.12.14 container — the host's
                                    default venv is Python 3.11 and cannot resolve this repo's
                                    Django 6.1.1 pin at all, so pip-audit was run where the real
                                    resolvable environment lives, not the host's unrelated Python)
No known vulnerabilities found
```

## Customer Zero / real-browser verification (WO §3.11, mandatory verification #7)

Real, authenticated, real-Chromium Playwright session against this dispatch's own disposable stack (Customer Zero bootstrapped via `python manage.py create_customer_zero`, never against the persistent `/srv/infosecurs` deployment, never a reset):
1. Logged in as the real `customerzero` user via the real `/accounts/login/` form (local-dev-account disclosure path).
2. Submitted one real question ("M009B Increment 2 browser verification: do all privileged accounts use MFA?") through the real `questionnaire:analyse` POST form at `/organisations/<id>/questionnaire/`.
3. Server logs confirm the real request chain: `POST .../questionnaire/analyse/` → `302` → `GET .../questionnaire/responses/<uuid>/` → `200`, no errors.
4. The rendered `response_detail` page shows the question text verbatim, a `CONFIRM` outcome badge, and the fixed, application-owned safe-wording sentence ("Not yet confirmed. The current security record does not contain enough confirmed information…") rather than the raw drafted fixture text — proving `persist_prepared_response`'s call into `_initial_current_answer_text` (M006 I2 containment) still fires correctly through the real view → `generate_questionnaire_response` → `prepare_questionnaire_response` + `persist_prepared_response` composition. Screenshot retained at evidence-gathering time (`/tmp/m009b_i2_response_detail.png` on the disposable host path, not committed to the repo).

**Disclosed, deliberate, scoped engineering choice:** this dispatch has no real Trinity AI-gateway credential (by design — same standing discipline the eval harness's own `run_questionnaire_ai_eval.py` states for `--gateway=live`). The real view calls `generate_questionnaire_response` with no gateway override, so it uses the real `ai_platform.gateway.LiteLLMGateway` HTTP client. To exercise that *real* HTTP code path (not bypass it with a `Fake*Gateway` substitution, which would skip the view's actual default-gateway construction entirely) without a real credential, a small, disposable, local-only OpenAI-chat-completions-compatible HTTP fixture server (`fake_ai_gateway.py`, stdlib `http.server`, not committed anywhere, not part of any image) was started on the same disposable Docker Compose network, and `AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY_FILE` in this dispatch's own `.env` (gitignored, never committed, never containing a real secret) were pointed at it for this one verification run. It returns one fixed, valid JSON payload satisfying both `QuestionnaireInterpretation.from_response_dict` and `QuestionnaireDraft.from_response_dict`'s required fields. This never touches `ai_platform` orchestration code, `questionnaire/services.py`, or any protected module — it is a test-only network fixture, identical in spirit to an HTTP-level mock any external-dependency browser test would need, torn down with the rest of this dispatch's disposable stack.

## Explicitly out of scope — confirmed NOT touched (WO §3.9)

- `_persist_response`'s/`generate_questionnaire_response`'s existing logic, field set, ordering, or event behaviour: **not changed** — golden corpus byte-identical before/after is the proof; the rename-plus-field-access substitution is the only transformation `persist_prepared_response`'s body received.
- Golden-corpus or existing-test diff of any kind, including cosmetic: **none** — see byte-identical comparison above; every existing M005-adjacent test file passed unmodified (zero assertion changes).
- "Improving" the extracted functions' naming/structure beyond the minimum: **not done** — field order in `PreparedQuestionnaireResponse` matches the amendment's own list exactly; no additional helper methods, no reordering, no renamed local variables.
- `liveness_check` parameter: **not added** — confirmed by reading the final `prepare_questionnaire_response` signature; that is Increment 3's own later, separately-disclosed change.
- `accept_questionnaire_response`, `edit_questionnaire_response_text`, `CONFIRM_APPLICATION_SAFE_ANSWER_TEXT`, `SUPPORTED_APPLICATION_SAFE_ANSWER_TEXT`, `_initial_current_answer_text`, `_hash_grounding_snapshot`, any import (other than the two additions needed for the dataclass itself): **not changed** — confirmed by direct diff read; the two stale-comment disclosures above are prose only, not logic.
- `questionnaire.catalogue`, `questionnaire.grounding`, `questionnaire.outcome`: **not touched** — no file in those modules appears in the diff.
- Database migrations/model fields: **none** — `makemigrations --check --dry-run` confirms.
- Any existing golden-corpus fixture or expected output: **not touched** — `questionnaire/eval/golden_corpus.py` is untouched in the diff; the before/after run used the identical, unmodified corpus file both times.
- Any file other than `questionnaire/services.py` getting application-code changes: **none** — only `questionnaire/tests/test_services.py` (a test file, the explicit exception) was also touched.

## Remaining governance steps

- PR opened against `main` (this increment's Implementer is explicitly authorised to open it — see dispatch instructions — but **not** to merge it).
- Independent Audit (fresh, re-deriving the golden-corpus-byte-identical proof from scratch per WO §3.8) — not yet performed; required before Architect Acceptance.
- Architect Acceptance and merge — not yet performed.
- Increment 3 remains explicitly not dispatched, pending the above sequence (WO §1's hard sequencing rule).
