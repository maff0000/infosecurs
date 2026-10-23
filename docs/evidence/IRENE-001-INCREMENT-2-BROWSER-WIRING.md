# IRENE-001 — Increment 2: Browser-Wiring Closure

**Status: IMPLEMENTED, PL-REVIEWED, INDEPENDENTLY AUDITED GREEN.**
This document covers the specific integration gap Central Architecture
identified before authorising the real-model test — closes item 3
("Final integration reconciliation") of Central Architecture's
2026-10-23 CONDITIONAL GO memo. It supersedes nothing in
`docs/evidence/IRENE-001-INCREMENT-2-STAGE3-PILOT.md`; it closes the one
item that document's §4 left open regarding browser reachability.

## 1. The gap, as Central Architecture stated it

Increment 2 (core) built a real `SectionDefinition` for Stage 3, a
concurrency-safe guarded save path, and a typed Explain-this context —
all independently audited GREEN — but none of it was reachable from any
real URL. Central Architecture's repository inspection confirmed this and
required it closed, stating six numbered requirements before any
real-model test or demonstration could proceed (quoted in full in the
memo; summarised): (1) present/answer Stage 3 questions inside the
existing IRENE modal; (2) enforce capability + tenant membership on every
real request; (3) save only through the audited guarded adapter;
(4) route Explain-this through a versioned adviser request and the real
gateway; (5) leave existing Foundations journeys and other IRENE
functionality unchanged; (6) keep the fallback functional when Adviser
Mode is off or unavailable. "No new platform architecture is authorised
or required."

## 2. What was built

One FORGE Engineer dispatch (worktree
`/srv/openclaw/worktrees/wo/IRENE-001-increment2-browserwiring` on
dell-debian, branch of the same name, based on
`wo/IRENE-001-pilot`@`ca0c1a2`), reviewed directly by the PL and committed
as `b0df453`, merged into `wo/IRENE-001-pilot` as `abdd667`:

- **New, additive orchestration entry point**
  (`irene/question_engine/stage3_orchestration.py`,
  `ask_irene_stage3_explain()`) — shares zero code path with
  `irene/orchestration.py`'s existing `ask_irene()`. Mirrors its exact
  disabled → rate-limit → no-skill → gateway-failure → fallback sequence
  via the same public contracts/gateway/fallback helper, but with its own
  independent (read-only) rate-limit query and its own copy of the
  response-registry filter — never importing a private helper from
  `ask_irene`'s module, never writing to
  `AssistantConversation`/`AssistantMessage`. Builds its request purely
  from the typed `Stage3QuestionExplanationContext` — never a raw
  `OrganisationProfile` row, never free text (requirement 4).
- **Three new, additive views** (`irene/views.py`:
  `stage3_panel`/`stage3_save`/`stage3_explain`), each independently
  calling `check_stage3_access` (Increment 2 core's existing composed
  tenant+capability gate) as its literal first action before any other
  code path (requirement 2). `stage3_save` calls only
  `organisations.services.save_stage3_fields` (requirement 3), handling
  `StaleCanonicalStateError`/`CanonicalValidationError` as real,
  non-500, user-visible redirects. `stage3_explain` calls
  `resolve_stage3_explanation()` then the new orchestration entry point.
  Both refuse the Key Assets (3.7, `delegated_workflow`) question
  server-side — it is never reachable through either endpoint, by design
  (Amendment D3: link out to the real `key_assets:list` route, never a
  duplicate inline editor).
- **A 5th, additive IRENE modal tab** ("Stage 3"), present only for a
  session passing the composed gate — zero changes to the four
  pre-existing tabs. `static/irene/js/modal.js` needed zero changes: its
  tab-switching logic was already fully generic over
  `[data-irene-tab]`/`[data-irene-panel]`.
- Two new templates (`irene/templates/irene/_stage3_questions.html`,
  shared fragment; `irene/templates/irene/stage3_panel.html`, a
  standalone destination reusing the same fragment) and two new test
  files (`irene/tests/test_stage3_orchestration.py`,
  `irene/tests/test_stage3_browser_wiring.py`).
- **Zero changes**: `irene/orchestration.py`,
  `irene/question_engine/{contract,registry,presenter,explain}.py`,
  `organisations/services.py`, `organisations/views.py`'s existing
  Stage 3 view, `organisations/templates/organisations/stage3_technology_data.html`,
  `static/irene/js/modal.js`. **Zero new migrations.**

## 3. Independent audit — GREEN

A fresh Auditor, with its own isolated clone and disposable Docker stack
on dell-debian, re-derived all ten audit items from its own evidence —
not from the implementing Engineer's report:

1. Real-browser (Playwright) verification: Stage 3 tab renders, shows the
   real registered questions, all four pre-existing tabs still work, the
   existing focus-trap/Escape acceptance test still passes unmodified
   with the new tab present.
2. Real HTTP (real login, real cookie jar, real CSRF — not just the test
   client): non-member → 404 on all three new views; member below
   required tier → 403 on all three.
3. Real save round-trip confirmed via direct DB query; a genuine
   concurrent-writer race against a stale `expected_state_token` produced
   a real 302 (never 500) and the DB row was confirmed to still hold the
   concurrent writer's value, not the rejected submission.
4. Confirmed, by reading the module and querying the DB before/after a
   real call, that Explain-this never writes
   `AssistantConversation`/`AssistantMessage` and its request is built
   purely from typed context.
5. Mechanically confirmed (`git diff --quiet`) zero changes to all nine
   named files, and independently re-ran `irene/tests/`,
   `organisations/tests/`, `foundations_journey/tests/` at this commit —
   all pass unmodified.
6. Real-browser run with Adviser Mode off (the shipped default): clicking
   "Explain this" returns the documented safe-fallback sentence, zero
   console/page errors; the gateway-construction monkeypatch test
   independently re-run and confirmed the gateway class is never even
   instantiated on this path.
7–9. Full suite independently re-run on the auditor's own disposable DB:
   **493 passed, 1 pre-existing skip** — an exact match to the diff's own
   claimed figure, reproduced rather than trusted. Zero new migrations
   confirmed mechanically (`makemigrations --check --dry-run`).
10. **Live exploit attempt**: with known baseline field values set
    directly in the DB, POSTed a crafted request for the Key Assets
    question (`question_code=stage3_q7_key_assets`) carrying extra,
    unrelated field names including a fabricated `key_assets_data=HACKED`
    — result was a safe 302 with **zero fields changed**, confirmed by a
    direct post-request DB query. Field names reaching
    `save_stage3_fields` are drawn only from the server-side registered
    `SectionDefinition`, never from arbitrary POST keys, with a second,
    independent allowlist check inside `save_stage3_fields` itself
    (`_require_known_stage3_fields`) as genuine defence in depth. A
    fabricated `question_code` is a 404; `stage3_explain` on the Key
    Assets question is a safe 302, never a 500.

**Verdict: GREEN.** All six Central Architecture requirements verified
independently; no regression, no bypass, no false claim found.

## 4. One finding, fixed immediately

The audit found the two new test files were not referenced in
`.github/workflows/ci.yml`'s explicit per-file test lists — the same
class of gap Increment 1's own audit found and fixed (commit `20568c3`).
Both files pass today but would have silently never run in real CI going
forward. Fixed in commit `08fd1de`:
`irene/tests/test_stage3_orchestration.py` added alongside its sibling
unit tests in `ci/unit`; `irene/tests/test_stage3_browser_wiring.py`
added alongside its sibling HTTP/browser tests in `ci/integration`.
Non-blocking to the GREEN verdict — a durability/process fix, not a
defect in the merged code.

## 5. Current pilot branch state

`wo/IRENE-001-pilot`, all pushed to origin, no PR opened yet:

`ca0c1a2` (Increment 2 core evidence) → `b0df453` (browser-wiring impl) →
`abdd667` (merge) → `08fd1de` (CI-wiring fix, HEAD).

## 6. What remains

Central Architecture's CONDITIONAL GO memo's remaining items, in order:

1. ~~Model/vendor security gate~~ — complete (reported separately):
   `AI_GATEWAY_BASE_URL` confirmed internal-LAN, credential mounted via a
   `600 root:root` Docker secret, not committed to git; one residual
   finding (plain HTTP, not TLS, between the Beta container and the
   internal gateway — LAN-only, flagged honestly, not a clean pass).
2. ~~Final integration reconciliation~~ — complete, this document.
3. **Real-model evaluation** (§4 of the memo): up to 3 real calls via
   `trinity-fast`, ≤US$1.00, ≤2048/512 tokens, ≤30s timeout, no retries —
   not yet attempted. Requires a disposable-test-only budget-enforcement
   wrapper (not product code) before the first call.
4. **Final customer journey** (§5): the full disposable real-browser
   demonstration (login → Home → IRENE → Stage 3 → Explain this →
   save → next question → grouped answers → Key Assets delegation →
   return → pause → resume → verify canonical state) — not yet
   attempted; depends on item 3 above per the memo's own sequencing
   (R4: on-demand AI explanation comes after real-model approval is
   exercised).
5. **Return gate** (§6): final pilot SHA, full evidence package, PR for
   exact-head Architect Acceptance — not yet opened.
