# M008C — Guided Foundations Journey: Flow, Conditional Map, Home Experience (Design Proposal)

**Status:** DESIGN ARTEFACT — not implemented, not approved.

## 1. Stage structure (proposed)

| # | Stage | Customer-facing name | What it covers | Existing data it reads/writes |
|---|---|---|---|---|
| 1 | Business | **Your Business** | Legal name, size, sector/motivation, productivity platform, cloud provider, software development, data handled | `OrganisationProfile` |
| 2 | People & Workplaces | **Your People & Workplaces** | Headcount, working pattern, workplace locations, governance roles | `workplace.Workplace`, `governance.OrganisationPerson`/`GovernanceRoleAssignment` |
| 3 | Technology & Data | **Your Technology & Data** | Endpoint management (company/BYOD), data categories, assurance status (Cyber Essentials/ISO) | `OrganisationProfile` (continued) |
| 4 | Security | **Your Security** | The 12 baseline controls | `security_baseline.BaselineAssessment`/`BaselineAnswer` |
| 5 | Risks & Actions | **Your Risks & Actions** | Deterministically generated risks (from `risk_register.scenario_engine`), remediation | `risk_register.Risk`, `remediation.RemediationAction` |
| 6 | Security Policy | **Your Security Policy** | Preview, review, approve | `policy.PolicyDocument`/`PolicyVersion` |

This splits the current single "Your business" step (PID master §5's
provisional 5-stage list) into **Business** and **Technology & Data**,
because `OrganisationProfile` genuinely has two different kinds of
question — who/what the business is (stage 1) versus what technology and
data it actually handles (stage 3) — and putting every `OrganisationProfile`
field in one stage made an earlier draft of this flow feel like one long
form rather than a guided journey. This is the one deviation from the
master PID's own illustrative 5-stage list; flagged explicitly for Product
Authority's own call, per Central Architecture's §5 ("recommend a
different grouping if usability evidence supports it").

Each stage is navigation only — `Stage ∈ {1..6}` has no row anywhere; the
real, unchanged 18-item `Security Foundations Completion` and weighted
`Foundational Security Posture` remain the sole source of progress truth,
computed from `entitlements.metrics` exactly as today.

## 2. Conditional questioning map

Governed, versioned branching driven by already-structured facts — not a
generic workflow engine (per PID's own explicit instruction). Each rule
below reads one or more existing/profile fields and changes which
question or option set is shown, never which canonical fact is stored.

| Upstream fact | Downstream effect |
|---|---|
| `OrganisationProfile.working_model == "office"` | `remote_access_control`'s NOT_APPLICABLE option becomes available (§M008B control 12) |
| `OrganisationProfile.primary_cloud_provider` is a real provider AND working model doesn't imply local storage | `device_encryption`'s NOT_APPLICABLE option becomes available (§M008B control 5) |
| `OrganisationProfile.staff_count == 1` | `joiner_mover_leaver`, `privileged_access_separation`, `security_awareness_training` each gain a NOT_APPLICABLE option (sole-trader case) |
| `OrganisationProfile.endpoint_management` | Changes `endpoint_protection`'s offered option set (company-managed-only businesses never see the "BYOD doesn't" option) |
| `OrganisationProfile.productivity_platform` (Microsoft 365 / Google Workspace / Other) | Changes only the *explanatory help text* under `email_phishing_protection` and `mfa_user_accounts` — never the options, never the underlying methodology (PID §3's own explicit instruction: "platform-specific explanatory guidance may differ without changing underlying methodology") |
| `OrganisationProfile.develops_hosts_own_software` (boolean) | If `False`: no software-development-specific questions are ever presented anywhere in the journey — there are none in the current 12-control catalogue today, so this rule has no visible effect yet, but is recorded here as a standing rule for any future control addition, per PID §3's "no internally developed software → software-development questions should not be asked" example |
| `OrganisationProfile.handles_payment_card_data` / `handles_special_category_data` | Does not change Stage 4's question set today (no PCI/special-category-specific baseline control exists yet); recorded as a structural fact already captured, available to a future control without re-asking |
| Any `BaselineAnswer` change after a dependent fact changes | The dependent answer is marked `stale`/flagged for re-confirmation, never silently kept — this applies today only within Stage 4 itself (no control currently depends on another control's answer, only on `OrganisationProfile` facts, which themselves don't change during Stage 4) |

No rule above removes a question from the canonical 18-item completion
catalogue — a NOT_APPLICABLE answer still counts toward completion
(unchanged rule); conditional branching changes which *options* are
offered for a question that is still always asked, never which questions
exist.

## 3. What the customer always sees, every stage

Per Central Architecture §5's requirement, every stage screen states, in
plain language, before the question itself:

1. **Where they are** — a persistent, small stage indicator ("Stage 4 of
   6: Your Security"), never conflated with the 18-item completion count
   (explicit instruction: "a persistent progress indicator that doesn't
   confuse stage position with 18-item completion" — M008C PID §C4).
2. **Why they're being asked** — the "why it matters" line from the
   catalogue (§M008B), one sentence, always visible, never hidden behind
   a tooltip only.
3. **How much is left** — "X of 12 security questions answered" within
   Stage 4 specifically (a stage-local count, separate from both the
   stage indicator and the 18-item completion figure — three genuinely
   different numbers, each clearly labelled so none is mistaken for
   another).
4. **What the answer means** — the short, deterministic explainer text
   from M008B §B5 ("MFA protects administrator accounts, but ordinary
   staff accounts are not all covered") appears immediately after
   selection, before moving on.
5. **What happens next** — after Stage 4 completes, an explicit interim
   screen states "We've worked out N risks and recommended actions from
   your answers" before moving to Stage 5 — never a silent transition.

No internal engineering term (baseline, canonical state, risk engine,
governance model, methodology resolver) appears anywhere in
customer-facing copy, per Central Architecture §5's explicit list.

## 4. "Not sure" behaviour

"Not sure" is never visually or linguistically penalised — it sits as an
ordinary, equally-weighted option in the predefined-answer list (never a
separate "I don't know" escape link below the real options), and its
resulting explainer text is informational, not corrective: "We'll mark
this as not yet confirmed — you can come back to it any time." Matches
PID's "Not sure remains available and clearly identifies follow-up rather
than penalising the user's honesty" (M008B §B5) and "do not force
confident answers" (master PID §5).

## 5. Home experience (§7)

Proposed Home layout, answering "what should I do next?" before exposing
detail, without changing any metric definition:

```
┌─────────────────────────────────────────────────────┐
│  Welcome back, Infosecurs Limited                     │
│                                                         │
│  ┌───────────────────────────────────────────────┐   │
│  │  ▶  Continue Security Foundations                │   │
│  │     Stage 3 of 6 — Your Technology & Data        │   │
│  └───────────────────────────────────────────────┘   │
│                                                         │
│  Your security at a glance                             │
│  ┌─────────────────────┐  ┌─────────────────────┐    │
│  │ Foundational         │  │ Foundations           │    │
│  │ Security Posture      │  │ Completion             │    │
│  │ 42%                   │  │ 6 of 18 (33%)          │    │
│  │ Based on what you've  │  │ Work completed so far  │    │
│  │ told us so far        │  │                         │    │
│  └─────────────────────┘  └─────────────────────┘    │
│                                                         │
│  Needs attention                                        │
│  • Staff account MFA isn't enabled yet → [Go to Security] │
│  • No tested backup restore → [Go to Security]          │
└─────────────────────────────────────────────────────┘
```

The single **"Continue Security Foundations"** primary action always
appears first, above both metric cards — directly answering "what
should I do next" before any number. The two metric cards keep their
exact existing M007 labels/definitions (Foundational Security Posture =
assessed protection; Security Foundations Completion = work completed)
with one added sentence of plain-language explanation each, exactly as
M007's own completion-vs-posture distinction already requires preserving
("a company can complete the programme with poor protections" — never
implied otherwise). "Needs attention" items link directly to the specific
stage/question that would resolve them — replacing the current literal
"click here"-only link wording (M007 WI5 known limitation) with the
actual gap's own plain-language description.

PAUSED-tier Home remains deliberately minimal (no metric calls), unchanged
from M007.

## 6. Technical/architecture boundary (unchanged from M007/M008 master PID)

Single server-rendered Django flow. No SPA. GETs never mutate. Every POST
still goes through `require_capability`-guarded, CSRF-protected,
tenant-scoped views exactly as M007 established. This design introduces
no new truth store — every stage writes into the exact same canonical
models (`OrganisationProfile`, `BaselineAnswer` via the new structured
service in M008B §B4, `Workplace`, `Risk`, `RemediationAction`,
`PolicyVersion`) that already exist.
