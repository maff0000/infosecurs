# M008 — AI Call Inventory and Cost Accounting (Design Proposal)

**Status:** DESIGN ARTEFACT. Target: zero LLM calls for routine
structured Foundations questioning (Stages 1-4 and the core of Stage 5).

## Before (current M007 architecture)

| Call | Trigger | Calls per journey |
|---|---|---|
| Risk interpretation (`risk_interpretation_v3`) | Customer requests AI refinement of a generated risk's impact/likelihood/rationale | 1 per risk reviewed (optional, customer-initiated) |
| Policy generation (`policy_generation_v2`) | Every policy draft | **1 per draft — currently the routine default** |
| Questionnaire interpretation/drafting (Customer Assurance only) | External questionnaire question submitted | 1-2 per question (Monthly+ only, out of scope for Foundation-tier accounting) |

## After (proposed M008 architecture)

| Stage | AI calls |
|---|---|
| 1. Your Business | **0** |
| 2. Your People & Workplaces | **0** |
| 3. Your Technology & Data | **0** |
| 4. Your Security (12 controls) | **0** |
| 5. Your Risks & Actions | **0 by default.** Risk *generation* (deterministic `scenario_engine`, already zero-AI today) unchanged. Risk *interpretation* remains an optional, customer-initiated, explicitly bounded call — unchanged from today, not newly added. |
| 6. Your Security Policy | **0 by default** (deterministic clause composition, M008D §2). AI generation becomes a non-default, separately-authorised exception path only. |

**Net result: the entire routine Foundations journey (Stages 1-6, default
path) makes zero LLM calls** — down from 1 guaranteed call (policy
generation) plus any number of optional risk-interpretation calls today.

## Retained/optional AI calls — full accounting

### 1. Risk interpretation (unchanged, already optional)

- **Trigger:** customer explicitly requests AI-refined impact/
  likelihood/rationale for a specific generated risk.
- **Input:** bounded structured risk-register grounding payload
  (existing `risk_register.grounding` contract, unchanged).
- **Output:** validated `InterpretationResponse` (existing contract).
- **Reason deterministic code is insufficient:** impact/likelihood
  refinement genuinely benefits from natural-language reasoning over
  the specific scenario context in a way a fixed lookup table cannot.
- **Model alias:** `trinity-core` (unchanged).
- **Approx. token usage:** ~2,100 prompt / ~760 completion per call
  (consistent with M007's own measured figures, `docs/evidence/
  M007-LIVE-AI-EVALUATION.md`).
- **Caching/idempotency:** none today; each request is a fresh call
  (unchanged — not introduced or removed by M008).
- **User-visible failure behaviour:** existing fail-safe — a failed
  interpretation leaves the risk at its deterministic starting
  impact/likelihood (3/3), with a visible "AI refinement unavailable,
  showing starting values" message (unchanged from M007).

### 2. Policy generation — becomes the exception, not the default

- **Trigger (proposed):** only when Product Authority separately
  authorises a future "AI-assisted clause phrasing" feature — explicitly
  NOT built in M008, and explicitly not the default path for Foundation
  tier ever.
- **Input (if ever built):** the same bounded, minimised structured
  projection the deterministic clause selector already reads — never
  raw customer notes (M006 G1 prohibition, unchanged, restated in
  M008D §3.1).
  M008D §3.1).
- **Output:** validated `PolicyGenerationResult` (existing contract,
  unchanged shape).
- **Reason deterministic code is insufficient:** none identified for the
  Foundation-tier default — this is precisely why the default path is
  being made deterministic. A future bounded exception (e.g. improving
  prose fluency of an already-fact-correct clause) would need its own
  separate justification at authorisation time, not assumed here.
- **Model alias / tokens / caching:** not applicable — no such call
  exists in this design; recorded as a placeholder row only so a future
  dispatch cannot quietly reintroduce an unauthorised default AI call
  without this inventory being updated first.
- **User-visible failure behaviour:** not applicable (no default call to
  fail).

### 3. Customer Assurance (Monthly+, out of scope for Foundation accounting)

Unchanged — `questionnaire_interpretation_v1`/`questionnaire_drafting_v2`
remain exactly as today, a separate, still-permitted workflow explicitly
outside M008's no-AI-for-routine-questioning scope (M008 PID §non-
negotiable #4's own explicit carve-out).

## Instrumentation requirement (for the eventual implementation WI, not this design phase)

A zero-call assertion test for the full Stages 1-6 default-path journey —
mirroring M007's own precedent (`normal baseline interaction session no
inference calls`, already proven in WI6) — extended to cover every new
stage and the new deterministic policy path. This is a test-writing
requirement for the implementation WI, not something this design phase
builds.
