# M002 Amendment Replan — 2026-09-23

**Status:** Central Architecture planning artefact, NOT authoritative product/architecture text.
**Authoritative amendment:** `docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md` §0.
**Purpose:** the KEEP/MODIFY/RETIRE mapping and revised delivery sequence Central
Architecture asked GUNNAR to return alongside the PID amendment, kept in Git
for traceability (GitHub is project truth) without being mistaken for the
amendment itself.

No product code has changed as a result of this document. It is a plan.

**Update, same day:** Central Architecture reviewed the first version of
this replan and the landed PID §0 against GitHub and approved it with
three final rulings (no `AI novel suggestion` Risk status in M002 V1;
asset-specific protection UX is REQUIRED not deferrable; catalogue size
preference is ~12-20, not 20-30) plus the `unknown`≠`no` invariant. The PID
itself was amended in place to reflect these (§0.4/§0.4a/§0.5/§0.7) rather
than layered with a second append section, since nothing had been built
against the first wording yet. The KEEP/MODIFY/RETIRE table and sequence
below are updated to match; no further Central Architecture checkpoint is
required before M002 PRODUCT_GREEN.

---

## 1. What triggered this

Two live evaluation rounds against the real `trinity-core` gateway (PID §18,
golden corpus) on the pre-amendment architecture
(`profile + baseline + assets -> LLM -> risks`) surfaced a structural
problem: the model was asked to reproduce database UUIDs
(`asset:<uuid>` grounding references) and invent risk framing from raw
facts with no methodology in between. Two prompt-repair rounds
(`risk_generation_v2`, `risk_generation_v3`) fixed real, specific defects —
verdict went from 7/8 failing cases to 2/8 plus one hard failure — but the
remaining failures (UUID copy-fidelity, empty `asset_reference`) are a
different class of problem: an architecture error, not a wording gap.
Central Architecture's ruling: stop prompt-repairing an LLM's ability to
reproduce identifiers; fix the division of labour instead.

## 2. KEEP / MODIFY / RETIRE

### `security_baseline` app

| Component | Disposition | Why |
|---|---|---|
| `catalogue.py` (12 baseline areas) | **KEEP** | Unaffected. Still the canonical control-fact catalogue. |
| `BaselineAssessment` / `BaselineAnswer` models | **KEEP** | Already the single canonical answer store §0.5 requires — asset-oriented surfacing reads/writes here, never a second copy. |
| Views/forms/templates | **KEEP**, unchanged | Core flow unaffected. Asset-contextual entry points are new surfaces added in `key_assets`/asset views (below), reading/writing this same canonical model — not a change to `security_baseline` itself. |
| Tests | **KEEP** | Unaffected. |

### `key_assets` app

| Component | Disposition | Why |
|---|---|---|
| `KeyAsset` model + category/criticality enums | **KEEP**, unchanged | Categories already match §0.4's asset-category list exactly. |
| `suggestions.py` (deterministic starter suggestions) | **KEEP**, unchanged | This *is* journey step 2 ("Asset discovery") already. |
| Asset list/create/edit views/templates | **KEEP** | Unaffected. |
| Asset detail view/template | **MODIFY, REQUIRED for V1** | Central Architecture ruling: must surface the relevant canonical `security_baseline` answers for that asset's category (§0.5) — reads/writes the same canonical `BaselineAnswer` rows via `security_baseline`'s own forms/model, never a duplicate. This is new asset-contextual surface area, not a new question model. |
| Tests | **KEEP**, **+MODIFY** for the new asset-contextual surface | Existing tests unaffected; new tests needed for "edit from asset view = same canonical record" (no duplicate-answer regression). |

### `ai_platform` app

| Component | Disposition | Why |
|---|---|---|
| `AIInvocationRecord` model | **KEEP** | Still records whatever the (now narrower) AI call is. |
| `gateway.py` mechanism — HTTP client, error taxonomy, credential handling, timeout, lazy config | **KEEP** | Sound infrastructure, task-shape-independent. |
| `orchestration.py` — bounded retry, invocation-record lifecycle, candidate cap | **KEEP the mechanism**, **MODIFY the payload it orchestrates** | Same shape of problem (call once, retry once if retryable, record outcome), different request/response contract. |
| `testing.py` (`FakeGateway`) | **KEEP the mechanism**, **MODIFY fixtures** | Test seam is task-shape-independent; fixture content changes with the new contract. |
| `contracts.py` — `GroundingPayload`, `RiskCandidate`, `GenerationResult` | **MODIFY** | `GroundingPayload`'s "raw fact bag for open generation" shape is retired. `RiskCandidate.grounding_refs`/`asset_reference` as *AI-authored* fields are retired — those become server-populated. New shape: a narrower payload carrying server-assembled candidate risk scenarios (from the new deterministic engine, §5 below) plus catalogue context; AI returns interpretation only (suggested likelihood/impact, rationale, treatment, clarification questions, prioritisation, dedup notes) keyed to an opaque scenario reference it is never asked to construct or reproduce precisely. |
| `prompts/risk_generation_v1/v2/v3.py` | **RETIRE as "current"**, **KEEP as historical record** | Never delete per the module's own versioning doctrine. They solved (and partially solved) the wrong task; the exposure/vulnerability distinction and prompt-injection-boundary language they developed are reused in the new prompt, not thrown away. |

### `risk_register` app

| Component | Disposition | Why |
|---|---|---|
| `Risk` model — `impact`/`likelihood`/computed `score`/`risk_band` properties | **KEEP**, unchanged | Deterministic scoring mechanism is sound and architecture-independent. |
| `Risk` model — `source`/`status` enums | **KEEP**, unchanged | No `AI novel suggestion` status in M002 V1 (Central Architecture ruling) — every persisted `Risk` row originates from the catalogue, so the existing `draft_ai_suggested`/`confirmed`/`dismissed` set (with `source=ai`, since AI still interprets/prioritises catalogue candidates) is sufficient as-is. |
| `Risk` model — new fields | **NEW** | `exposure`, `vulnerability`/`control_gap`, `threat_event`, `consequence`, and a reference to the catalogue scenario that produced the candidate (§0.2 derivation spine). |
| `Risk.key_asset` FK, `asset_reference` | **KEEP the FK**, **RETIRE the free-text AI-authored string** | Populated deterministically by application code from the scenario instantiation — never parsed out of model output (§0.6). |
| `grounding.py` (`build_grounding_payload`) | **RETIRE the shape**, **KEEP the safety discipline** | The reverse-one-to-one-traversal / explicit-organisation-filter tenant-scoping pattern is exactly right and must be carried into its replacement unchanged. The *content* it assembles (raw fact bag for open generation) is superseded by the new deterministic scenario-instantiation engine (§5). |
| `services.py` (`generate_draft_risks`) | **MODIFY** | Becomes two phases: (a) deterministic candidate assembly (no AI, no network call) from assets + control-state + catalogue; (b) a bounded AI interpretation call over the assembled candidates. Regeneration safety (only ever creates new rows, never mutates confirmed) is unchanged and still required. |
| Views/templates (list/detail/edit/confirm/dismiss) | **KEEP the flow**, **MODIFY the fields shown** | Confirm/dismiss/edit semantics on a `Risk` row are unaffected by how the row was populated. Templates need the new exposure/threat_event/consequence/risk_scenario fields. |
| `eval/golden_corpus.py`, `eval/harness.py`, `run_ai_eval` command | **MODIFY substantially** | Corpus cases represent catalogue-instantiated scenarios, not raw fact bags. The `grounding_refs_subset_of_supplied_facts` objective check retires (there is nothing for the model to fabricate a reference to anymore); new objective checks cover the new contract (no identifier fabrication possible by construction, likelihood/impact in bounds, interpretation stays attached to the scenario it was given). |
| Tenant-isolation tests | **KEEP the discipline**, **MODIFY the payload assertions** | The "cross-tenant fact must never appear in an outbound AI payload" test (PID §16, critical) still applies — the payload shape it inspects changes. |

### New required work (§0.4 of the amendment)

| Component | Disposition |
|---|---|
| Versioned methodology catalogue (asset category → exposures → control checks → threat events → consequence types → suggested treatments, ~12–20 scenarios preferred, 20–30 as a ceiling not a quota) | **NEW** |
| Deterministic scenario-instantiation engine (assets + control-state answers + catalogue → candidate `Risk` rows, no AI) | **NEW** — this is the core of the corrected architecture. |
| New AI practitioner-interpretation contract + prompt | **NEW**, reusing `ai_platform.gateway`'s mechanism |
| Asset-specific protection-check UX | **NEW, REQUIRED for V1** (Central Architecture ruling — not deferrable) |

## 3. Revised bounded delivery sequence

Phase boundaries chosen so each phase's Engineer dispatch(es) can be
reviewed/integrated before the next depends on them, matching the FORGE
pattern already used for M002 Phase 1/2.

```text
Phase M002-3a (parallel, independent)
  - Methodology catalogue (data module, ~12-20 scenarios preferred, each
    scenario carrying the exact field set PID §0.4 specifies, including
    the unknown-vs-no applicability rule per §0.4a)
  - Risk model migration (new exposure/vulnerability/threat_event/
    consequence/scenario fields; no new status value - schema only)

Phase M002-3b (depends on 3a)
  - Deterministic scenario-instantiation engine
    (assets + control-state + catalogue -> candidate Risk rows, no AI,
    unknown != no honoured throughout)
    Reuses risk_register/grounding.py's tenant-scoping discipline.

Phase M002-3c (depends on 3b)
  - AI practitioner-interpretation layer: new ai_platform contract + prompt
    + orchestration wiring over 3b's assembled candidates - interpretation/
    clarification/prioritisation only, never a new persisted Risk row.
    Reuses ai_platform/gateway.py's HTTP/retry/credential mechanism
    unchanged.

Phase M002-3d (depends on 3b, can run alongside 3c)
  - Risk register views/templates rewire for the new fields and two-phase
    generate flow. Review/confirm/dismiss/edit semantics unchanged.
  - Asset-oriented protection UX, REQUIRED for V1 (Central Architecture
    ruling): key_assets asset-detail surfaces the relevant canonical
    security_baseline answers per §0.5, editing the same canonical record.

Phase M002-3e (depends on 3c + 3d)
  - Golden corpus + eval harness rework for the new contract.
  - PL runs the live evaluation against real trinity-core (should be
    structurally safer now - no identifier fabrication is possible by
    construction, since the AI is never asked to produce one).

Phase M002-3f
  - Fresh FORGE Auditor (real-browser acceptance, PID §22) against the
    corrected flow.
  - Evidence, GitHub-required-checks reconciliation, PR, merge - per the
    same discipline already used for M001 and this PID's earlier
    governance work.
```

Not resuming implementation until Central Architecture reviews this replan
alongside the landed PID amendment, per explicit instruction.
