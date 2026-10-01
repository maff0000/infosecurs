# M008 — Design Artefact Checkpoint Package

**Status:** DESIGN ARTEFACT PHASE COMPLETE. Nothing described here is
implemented. This document packages the M008B/C/D design artefacts for
Matt/Product Authority's explicit review and approval, per Central
Architecture's "M008B/C/D DESIGN ARTEFACT PHASE" instruction and the
M008 master PID §4's own mandatory STOP gate ("STOP here until Product
Authority approves wording, flow and document direction").

**M008A (the dev-only Customer Zero reset) is separately CLOSED
PRODUCT_GREEN** (canonical main `71cc2d11da981fe652de45d9bf85138719bf1c5a`)
and remains operational on the dev stack — unaffected by this design
phase, and genuinely useful for comparing the old/current application
against the proposed experience below.

## 1. Clickable prototype

**URL:** https://claude.ai/artifact/JHveVvgY4qb2BvVQabpZy5

A real, responsive HTML/CSS prototype (no SPA framework, no build step —
plain vanilla JS section-switching, same idiom as the real product's own
`shell.js`). Covers, as separate reachable screens: Home, the Foundations
stage-overview landing, a representative simple question, a
representative conditional question (with a bounded follow-up field and
a gated NOT_APPLICABLE-shaped option set), explicit "Not sure" selection
behaviour, a stage-completion interstitial, the Risks & Actions view, the
Security Policy preview/review screen (with the Approve action
structurally disabled against an incomplete state, matching the
no-auto-approve rule), and the DEV-only reset affordance (visually
distinct, explicitly labelled, matching the now-live M008A feature's own
wording). No destructive/production behaviour is wired into it — every
interaction is local, visual-only state.

The prototype's HTML source is also committed at
`docs/design/prototype.html` for a durable, Git-tracked record
independent of the Artifact hosting platform.

## 2. Screenshots at 375 / 768 / 1280px

21 PNGs (7 screens × 3 widths) at `docs/design/screenshots/`, captured
directly from the committed prototype source via a real headless
Chromium render (not hand-described) — `home-{375,768,1280}.png`,
`foundations-*.png`, `q-simple-*.png`, `q-conditional-*.png`,
`q-notsure-*.png`, `risks-*.png`, `policy-*.png`. Confirms the layout
genuinely reflows (sidebar → hamburger drawer at narrow widths, metric
cards and stage tiles stack to one column) rather than merely scaling.

## 3. Proposed complete question catalogue

`docs/design/M008B-QUESTION-CATALOGUE.md` — all 12 existing
`security_baseline.catalogue` controls, each with: customer-facing
title, plain-English question, why-it-matters, richer-than-Yes/No
predefined answers, conditional follow-ups, canonical five-state mapping,
NOT_APPLICABLE eligibility (and its gating condition where applicable),
the real existing `risk_register.methodology` scenario ID(s) it
triggers, the real existing `policy` section key it affects, evidence
expectations, completion effect, and an explicit versioning note. No
control key, weight, scenario, or policy section is renamed or
reweighted — confirmed against the actual current source
(`security_baseline/catalogue.py`, `risk_register/methodology.py`,
`ai_platform/policy_contracts.py`), not invented.

## 4. Conditional-question map

`docs/design/M008C-UX-FLOW-DESIGN.md` §2 — every branching rule, each
keyed to a real, already-existing `OrganisationProfile` fact
(`working_model`, `primary_cloud_provider`, `staff_count`,
`endpoint_management`, `productivity_platform`,
`develops_hosts_own_software`), stating exactly what changes (which
option becomes available, or which help text differs) and confirming no
rule ever removes a question from the 18-item completion catalogue.

## 5. Canonical-state mappings

Embedded directly in the question catalogue (item 3 above) — every
predefined answer option's mapping to YES/PARTIAL/NO/UNKNOWN/
NOT_APPLICABLE is explicit, per control, with the specific business
situations each option is meant to capture (e.g. distinguishing "MFA
required for all staff" from "available but not enforced", both
materially different from a bare Yes/No).

## 6. Free-text replacement register

`docs/design/M008-FREE-TEXT-REPLACEMENT-REGISTER.md` — extends the
already-merged WI0 inventory (`docs/evidence/
M008-PREFLIGHT-AND-FORM-INVENTORY.md`, 12 violations found) with, for
every field: current route, why it violates the doctrine, proposed
replacement interaction, new canonical storage destination, whether the
old field/column is retained for history, whether legacy values stay
visible/read-only, migration requirement, downstream code dependencies,
and whether an AI call is removed. Two fields (`OrganisationProfileForm.
commercial_security_driver`, `RiskEditForm.*`) are confirmed to currently
reach an AI grounding payload; the `PolicyVersionEditForm` replacement is
confirmed to remove the one routine, default AI call in the entire
current M007 architecture.

## 7. Guided UX / Home design

`docs/design/M008C-UX-FLOW-DESIGN.md` — proposed 6-stage structure
(Business / People & Workplaces / Technology & Data / Security / Risks &
Actions / Security Policy — one deliberate split from the master PID's
own illustrative 5-stage list, flagged explicitly in §1 for your own
call), what the customer always sees on every screen (position, why,
how-much-left, what-it-means, what's-next), "Not sure" treatment, and
the redesigned Home layout (§5) — primary "Continue" action before any
metric, both existing M007 metrics preserved with their exact existing
definitions and one plain-language sentence each, "Needs attention"
items linking to their actual gap rather than a bare "click here."

## 8. Three complete sample policies

`docs/design/policies/M008D-sample-policy-{a,b,c}.pdf` — real, rendered
2-page PDFs (not prose descriptions), reusing the master PID's own
already-approved test personas (A ≈ Persona B's shape: mature,
office-first, Google Workspace; B ≈ Persona A's shape: incomplete,
remote-first, Microsoft 365; C: Persona C, freshly reset/all-unknown).
Full synthetic input state and the exact structured facts behind every
clause are in `docs/design/M008D-SAMPLE-POLICIES.md`. Scenario C's PDF
is explicitly marked "Preview — not approvable," every section states
plainly that nothing has been confirmed, and no fact is fabricated.

## 9. Policy clause-to-source truth matrix

`docs/design/M008D-POLICY-TRUTH-MATRIX.md` — every clause used across
the three sample policies, its source fact, and its explicit
classification (CURRENT_CONFIRMED_PRACTICE / NORMATIVE_REQUIREMENT /
GAP_OR_FUTURE_ACTION / UNKNOWN-CANNOT-CLAIM). The one hard rule this
enforces: every PARTIAL-sourced control produces two separate sentences
in the rendered policy (what's true + what's missing), never one blended
claim — proven against all three samples, not merely stated as a
principle. Policy architecture itself (deterministic clause-composition
pipeline, replacing the one-shot AI generation default) is at
`docs/design/M008D-POLICY-ARCHITECTURE.md`.

## 10. AI/cost inventory

`docs/design/M008-AI-COST-INVENTORY.md` — before/after call accounting
per stage. Target (zero LLM calls for the routine default journey)
achieved in the proposed design: policy generation's current one
guaranteed call per draft becomes a non-default, unbuilt exception path;
risk interpretation remains exactly as today (optional, customer-
initiated, unchanged); Customer Assurance (Monthly+) is explicitly out
of scope, unchanged.

## 11. Known design tradeoffs / items requiring Product Authority decision

1. **Stage split** — Business vs. Technology & Data as two stages
   instead of the master PID's illustrative one combined "Your business"
   stage (M008C §1). Recommend the split; your call.
2. **Methodology non-changes flagged, not pre-decided** — no control
   weight, scenario, or policy section changes in this proposal; if you
   want to reconsider any of these, that is explicitly a separate,
   later methodology-change decision (M008 master PID §3 item 3), not
   assumed here.
3. **Page-length target** — both complete sample policies render at
   exactly 2 pages, within the existing M004 2-4 page target; this was
   achievable without omitting any warning or fact, so no breach is
   being proposed or flagged for reconsideration at this time.
4. **"Fresh login" vs. session-rotation question**, already resolved
   during M008A's own delivery (full `logout()`, not mere rotation) —
   noted here only because the master PID's own §8 wording ("require
   fresh login") could have been read either way; recorded for
   continuity, not a new open question.
5. **A future bounded AI-assisted clause-phrasing exception** for policy
   text is explicitly named as NOT part of this proposal and NOT
   authorised — flagged in the AI/cost inventory's own placeholder row
   so a later dispatch cannot quietly reintroduce a default AI call
   without this document being revisited first.

## What happens next

Per the master PID's own gate and Central Architecture's explicit
instruction: **STOP here.** No M008B/C/D implementation begins until you
explicitly approve or request changes to the artefacts above. M008A
remains live on the dev stack in the meantime if you'd like to compare
today's application against the proposed experience directly.
