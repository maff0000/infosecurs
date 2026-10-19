# M010 — Consolidated Evidence Index (Work Packages A-F)

**Compiled by:** M010F dispatch (`docs/pids/M010F-INTEGRATION-SECURITY-RELEASE.md` §1 "durable evidence index"). **Status:** real, re-verified traceability — every test file:line below was either re-run directly during M010F (§ marked "re-run") or read directly in the real file to confirm it exists and does what its owning package's own evidence document claims (§ marked "read-confirmed"). This index does not replace the Independent Audit required by the governing PID §3/§7 — it is the Implementer-side evidence that audit will re-derive from and check against.

## 1. Per-package evidence documents

| Package | Evidence document | What it covers |
|---|---|---|
| Preflight | `docs/evidence/M010-PREFLIGHT.md` | Baseline test counts before any M010 code; no M009B conflict |
| M010A | `docs/evidence/M010A-TASK-SPINE.md` | `SecurityTask`/dependency/event models, Tasks page, concurrency, two-tenant matrix |
| M010B | `docs/evidence/M010B-FOUNDATIONS-PARITY.md` | `foundations_journey` guided Stage-4 adapter, 57-case manual-vs-guided golden-set parity, checkpoints |
| M010C | `docs/evidence/M010C-IRENE-WORKSPACE-TOOLS.md` | IRENE modal, conversation model, skills, bounded tool registry, adversarial red-team corpus |
| M010D | `docs/evidence/M010D-REVIEW-SCHEDULER.md` | Deterministic review-rule scheduler, reconciliation, concurrency/DST |
| M010E | `docs/evidence/M010E-ASSURANCE-ENTITLEMENTS.md` | Capability matrix, M009 Customer Assurance read-only adapter, tier gating |
| M010F | `docs/evidence/M010F-INTEGRATION-SECURITY-RELEASE.md` | This package: integration re-proof, backup/restore, full regression, two fixed gaps |
| Traceability plan | `docs/evidence/M010-TRACEABILITY-AND-ACCEPTANCE-PLAN.md` | The test-plan (not evidence) this index fulfils |

## 2. Requirement traceability — real file:line citations

Positive assertion = the owning package's test proves the feature works for an authorised actor. Negative/adversarial assertion = the owning package's test proves the attack/misuse is rejected. Both columns are existing, executable pytest functions re-run or read-confirmed during M010F — none were invented fresh for this index.

| Req | Owner | Positive assertion (file:function) | Negative/adversarial assertion (file:function) |
|---|---|---|---|
| F01 Home→IRENE auto-open | M010C | `irene/tests/test_http_ui.py::TestAutoOpenPreference::test_post_updates_preference` | `irene/tests/test_http_ui.py::test_unentitled_tier_denied_closed_not_handed_a_link` (fail-closed, not a silent redirect) |
| F03 Six-stage/12-question guidance, manual-vs-IRENE parity | M010B | `foundations_journey/tests/test_parity_golden_set.py::TestManualVsGuidedParity::test_identical_canonical_effects_on_separate_organisations` (57 parametrized cases, re-run this package: 59 passed) | `foundations_journey/tests/test_forgery_and_edge_cases.py` (stale/forged/unoffered `option_code`, both service-layer and HTTP-level, writes nothing) |
| F04 Distinct stage/12/18 progress | M010B | `foundations_journey/tests/test_checkpoint.py::test_checkpoint_reaches_journey_complete_after_all_twelve` | `foundations_journey/tests/test_parity_golden_set.py` 18-item completion-invariance assertions (never counts `UNKNOWN` as confirmed) |
| F05 Tasks shared/assignment/dependencies/cycles | M010A | `security_tasks/tests/test_dependencies.py` (link/cycle rejection); `security_tasks/tests/test_services.py` (CRUD/assign) | `security_tasks/tests/test_tenant_isolation.py` (cross-org task/assignee/dependency rejected) |
| F05/F06 Concurrency, multi-tab | M010A/B | `security_tasks/tests/test_concurrency.py::test_two_simultaneous_creators_of_the_same_occurrence_produce_exactly_one_row`; `foundations_journey/tests/test_concurrency.py::test_two_simultaneous_submits_of_the_same_answer_leave_exactly_one_row` | `security_tasks/tests/test_concurrency.py::test_two_concurrent_writers_with_stale_version_one_wins_one_conflicts`; `foundations_journey/tests/test_concurrency.py::test_two_concurrent_pause_attempts_with_the_same_expected_version_one_wins` |
| F06 Checkpoint resume, per-user privacy | M010B | `foundations_journey/tests/test_task_handoff.py`; `foundations_journey/tests/test_checkpoint.py` | `foundations_journey/tests/test_forgery_and_edge_cases.py` (cross-tenant/removed-member cannot retrieve history) |
| F07 Scheduler due/overdue/recurrence, no duplicates, no fabricated dates, no model call | M010D | `security_tasks/tests/test_review_rules.py`; `security_tasks/tests/test_review_scheduler.py` | `security_tasks/tests/test_review_scheduler_concurrency.py` (concurrent run, exactly one task); `security_tasks/tests/test_review_scheduler.py::test_manually_closed_then_reopened_source_is_not_resurrected_or_duplicated` |
| F08 Skills versioning, tool allowlist, approved route resolution | M010C | `irene/tests/test_skills.py`; `irene/tests/test_tools.py` | `irene/tests/test_adversarial.py` (poisoned skill/unknown tool/invalid route denied) |
| F09 Approved task proposal/confirmation, forbidden approval actions | M010A/C | `irene/tests/test_orchestration.py` (`propose_task`/`confirm_task_creation` via canonical `create_task` path) | `irene/tests/test_adversarial.py` (no policy approval/risk acceptance/silent answer change via any tool) |
| F08/F09 Prompt-injection / tool-call red-team | M010C | — | `irene/tests/test_adversarial.py` full corpus (M010C evidence §5 "Adversarial red-team corpus — full results") |
| F10 Cost/latency/timeout/quota, safe outage, no leakage, shutdown flag | M010C | `irene/tests/test_zero_ai_calls.py` (deterministic paths make zero gateway calls); `ai_platform` provider-budget placeholders disclosed in M010C evidence §4 | `organisations/tests/test_ai_outage_resilience.py`; `irene/tests/test_http_ui.py::TestAutoOpenPreference::test_manual_app_works_with_irene_disabled` (shutdown flag) |
| F11 Tier/access matrix | M010E | `irene/tests/test_capability_matrix.py::test_covers_every_registered_tool`, `::test_new_customer_assurance_tool_reports_monthly_tier` | `irene/tests/test_capability_matrix.py::test_unknown_capability_code_reports_none_rather_than_raising`; `irene/tests/test_customer_assurance_tools.py::test_disabled_flag_denies_via_call_tool_dispatch` |
| F12 M009 handoff without readiness bypass | M010E | `irene/tests/test_customer_assurance_tools.py::test_monthly_ready_gets_real_status`, `::test_pro_ready_gets_real_status`, `::test_100_percent_ready_unlocks_real_status` | `irene/tests/test_customer_assurance_tools.py::test_99_percent_ready_is_blockers_only`, `::test_foundational_gets_blockers_only_never_imports`, `::test_denies_after_membership_revoked_mid_call`, `::test_tier_downgrade_mid_tool_call_to_paused_fails_closed` |

## 3. Customer scenarios (PID §4) — owning fixture

| # | Scenario | Owning fixture(s) |
|---|---|---|
| 1 | New user, 12 controls incl. Not sure, manual route still works | `foundations_journey/tests/test_parity_golden_set.py` full run + `irene/tests/test_http_ui.py::test_manual_app_works_with_irene_disabled` |
| 2 | Pause at Q7, create task, sign out/in, resume exact stage; shared task visible, private chat not; revocation removes access | `foundations_journey/tests/test_checkpoint.py` + `foundations_journey/tests/test_task_handoff.py` + `security_tasks/tests/test_tenant_isolation.py` + `irene/tests/test_customer_assurance_tools.py::test_denies_after_membership_revoked_mid_call` |
| 3 | N/A conditional checks; forged hidden option rejected, no mutation | `foundations_journey/tests/test_forgery_and_edge_cases.py` |
| 4 | Manual answer change reflected next IRENE load; downstream state canonical | `foundations_journey/tests/test_parity_golden_set.py` re-answer tests |
| 5 | Scheduler runs twice concurrently + DST; exactly one task; human-done ≠ control-implemented | `security_tasks/tests/test_review_scheduler_concurrency.py`; `security_tasks/tests/test_completion_independence.py` |
| 6 | Hard AI question uses approved skill/bounded projection; no A/B crossover; provider timeout → journey continues | `irene/tests/test_adversarial.py`; `irene/tests/test_orchestration.py`; `organisations/tests/test_ai_outage_resilience.py` |
| 7 | 100% Foundations + higher tier → M009 upload link; 99%/lower tier → existing blocker | `irene/tests/test_customer_assurance_tools.py` (§2 table F12 row) |
| 8 | Tenant export/deletion/privacy, backup/restore respects retention | `organisations/tests/test_m009a_reset_reconciliation.py` + M010F §4 backup/restore proof (production-specifics separately gated per PID §4 item 8) |

## 4. M009B Increments 3-4 — independently re-confirmed absent

Re-verified directly during M010F (not cited from an earlier finding):
no `questionnaire/bulk_orchestration.py`, no `QuestionnaireBulkResponseAttempt`
model, no `claim_next_eligible_question`/`CLAIM_TTL` symbol anywhere in
`.py` code; only `wo/M009B-increment1-readiness-csv` and
`wo/M009B-increment2-m005-prepare-persist` branches exist. **Not part of
this campaign's deliverable; not implemented, not started.**

## 5. CI wiring status (as of this index)

`.github/workflows/ci.yml` `ci/unit` and `ci/integration` jobs now cover
every M010A-E test file, including `foundations_journey/tests/
test_parity_golden_set.py` (fixed by M010F — see
`M010F-INTEGRATION-SECURITY-RELEASE.md` §6.1). `.github/workflows/
security.yml` already provides `security/secrets` (gitleaks),
`security/dependencies` (pip-audit), `security/sast` (CodeQL),
`security/container` (Trivy, app + ClamAV images) — all pre-existing, not
a gap introduced or left by M010.
