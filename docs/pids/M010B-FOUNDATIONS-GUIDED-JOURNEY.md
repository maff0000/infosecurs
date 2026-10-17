# M010B PID — Reuse Existing Structured Foundations, Checkpoint and Navigation

**Priority:** After M010A service spine. **Goal:** IRENE can lead and resume the existing Foundations process without inventing questions, answer choices, scoring or security facts. **Relevant actual code:** `security_baseline.{catalogue,structured_catalogue,stage4,forms,services,views}`; `entitlements.metrics`; M008 profiles/risk/policy.

## 1. Source-of-truth contract

12 Stage-4 controls from `CATALOGUE_KEYS`; options with stable `option_code` from `offered_options` against current org; displayed text from `QUESTION_COPY`; deterministic after-answer explainer `explainer_for`; M008 structured `AnswerSelectionDetail` and `BaselineAnswer` written through `record_structured_baseline_answer`; 18 FoundationRequirement overall completion from `get_security_foundations_completion`. No new question table, no alternative free-text baseline answer, no second risk scenario engine.

## 2. Guided-answer UI and endpoints

Introduce a server-owned `StructuredQuestionViewModel` with `question_key`, approved question/why, current offered option code+label list, saved option, exact special checkbox requirement, stage index, question index 1–12, reviewed/confirmation counters, overall 18-item completion, deterministic explainer and registered manual link. Build through existing services and permission checks. Render one card in IRENE; use semantic radio controls. For JML N/A, require both current people-count fact and explicit confirmation in the same POST; remote-access N/A requires confirmed `has_remote_or_offsite_access == no`; endpoint BYOD conditional options follow existing `offered_options` logic; no model-selected option.

Provide `submit_foundations_option` application endpoint taking only specific `question_key`, `option_code`, per-control confirmation if relevant, catalogue version and CSRF/session; server reconstructs `StructuredAnswerForm`, revalidates current options, calls `record_structured_baseline_answer` on success, then returns receipt and recommended next question from actual saved state. Reuse the same canonical writing path as manual view; refactor into a shared validated service only if true code parity is necessary and tests show it, not duplicated handler logic. Do not move raw prose into M002/M004 prompts.

## 3. Stages 1–3, 5–6

Build navigational adapters for existing structured `OrganisationProfile`/workplace/governance forms, existing risk/remediation page services, policy preview/review routes. Do not implement a new forms system to mimic them. Where existing in-modal field widgets can reuse the exact Django forms/service, do so; otherwise a deeply linked guided step is acceptable, preserving full-page manual behavior. Do not pretend M008C's formerly proposed flow is automatically implemented for each stage—preflight inventory actual route coverage and close gaps only within existing contracted forms.

## 4. Checkpoint design

`JourneyCheckpoint` unique org+user+journey, stage/key, state, version and last activity; save only after successful operation; read and reconcile with real domain answer on resume; preserve manual edits; do not store PII or raw answer prose in checkpoints. If question deprecated/catalogue version changes, show clear re-review rather than guessing which option is equivalent. A second user in same organisation shares saved canonical answers but has independent navigation checkpoint. No checkpoint may access or resume an unauthorised tenant.

## 5. Task handoff

Selecting UNKNOWN or declining a question can offer a pre-scoped Task Service action to confirm facts; PARTIAL/NO can offer deterministic remediation next steps with relevant control source. Creation is explicit, deduped, and records canonical question key, status and reason. No automatic task closure merely because a user selected YES; closure criteria depend on actual source state and authorised workflow. A task can deep link to that exact Stage-4 question or relevant manual page via registered route.

## 6. Required evaluation

Golden set for all **12** controls and all offered option codes: compare manual `foundations_question` submission and IRENE card submission on separate identical fixture organisations; check `BaselineAnswer`, `AnswerSelectionDetail` provenance/version, activity/risk/policy side effects, stage progress, 18-item completion and responses. Include duplicate code mappings (different PARTIAL semantics), re-answer of an old selection, N/A forged/disallowed, stale profile state, UNKNOWN, incomplete/complete, unauthenticated, wrong tier, cross tenant, concurrent multi-tab, no JS/provider. No model calls for entire deterministic flow. Run existing M008 regression suite unmodified; browser journey through login/modal/full page/resume.

## 7. Exit / STOP

Evidence `docs/evidence/M010B-FOUNDATIONS-PARITY.md`: per-control/option canonical parity matrix, stage route inventory, checkpoint tests, no-LLM traces. STOP for changed option identity, scoring, canonical write side effects, prompt injection via Foundation answers, stage/completion confusion, or unexpected allowance of NOT_APPLICABLE.
