# WO-M008E-WI2 — Visual Rollout

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Exact base SHA:** `4631389d82697b1c2c222254756b4c900fecf395`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Scope

Apply the Product-Authority-approved M008E-WI1 visual system (`docs/evidence/M008E-DESIGN-DIRECTION.md`, `.claude/skills/infosecurs-ui-design/SKILL.md`, `static/organisations/css/app.css`'s shared component layer) consistently across the remaining existing INFOSECURS user-facing application. This is a **visual/UX consistency rollout only**. It does not introduce any new design language — the typography scale, spacing system, colour/status semantics, radius scale, and component vocabulary (`.summary-card`/`.form-card`, `.button--primary`/`--secondary`/`--destructive`, `.dev-panel`, `.progress`, `.option-group`/`.option-card`, `.alert`, `.badge`, `.empty-state`, `.section-header`, `.fieldset--bare`) established in WI1 are the only vocabulary this Work Order may use or extend — never a parallel or divergent visual system.

## Authorised surfaces (at minimum)

Home; Foundations workspace; Stages 1-4; Risks & Actions; Security Policy; Security State; Baseline; Assets; Risks; Evidence; Remediation; Company/Organisation; Profile; Governance; Workplace; Activity; Customer Assurance; the reset confirmation screen; login/pre-organisation surfaces where visually appropriate.

## Hard rule — no product/workflow redesign

If a page requires a meaningful workflow, information-architecture, or product-behaviour change rather than a styling/presentation improvement: **STOP and return to the Architect.** Do not silently redesign product logic. This Work Order is styling/presentation only.

## Design invariants — preserve exactly (no entitlement/security/methodology/data-model changes)

Tenant isolation; the entitlement model; FOUNDATION/MONTHLY/PRO/PAUSED tier behaviour; current routes (unless separately approved); structured answer semantics; UNKNOWN != NO; PARTIAL != YES; M007 posture/completion methodology; deterministic policy truth; the normative-policy/implementation-status separation; Customer Assurance contracts; the Customer Zero reset security controls; zero-LLM normal Foundations interaction; existing approved-policy/history immutability; no data-model or migration changes of any kind; no real customer data; no production authority.

## Customer Zero reset

The approved WI1 direction included improved reset discoverability on Home and Company hub. Every additional surface that reuses this affordance (if any) must reuse the one shared boolean/helper (`organisations.views._customer_zero_reset_enabled_for`), unchanged from WI1 — never duplicate or re-derive the gating logic. The Home/Company hub implementations themselves are already complete (WI1) and are not to be altered by this Work Order except for shared-token/component refreshes that apply uniformly.

## Implementation style — component-first

Use the approved lightweight internal design system from WI1 exclusively. Prefer reusable CSS/component patterns already established; extend them (new component classes) only where a genuinely new UI shape is needed, following the same naming/token conventions. Avoid: page-specific CSS hacks; inline-style sprawl; SPA/framework migration; unnecessary JS; a new commercial UI framework; generic card-everything design; excessive animation; dark/hacker cyber styling; any new design language not already present in WI1's accepted system.

## Browser-led verification — mandatory at 1280/768/375

Continue using: the frontend-design capability where available; the `infosecurs-ui-design` project skill; real Chromium/Playwright; before/after screenshot comparison. Do not implement blind from source. **Every changed surface must be inspected at 1280px / 768px / 375px** before being reported as complete.

## Regression requirements (binding — carried forward from WI1's own incident history)

The WI1 375px `.progress` overflow regression and the WI1 sidebar focus-ring CSS-specificity regression are now permanent regression classes. Explicitly retain/add coverage for every rolled-out surface: progress-text wrapping; no horizontal overflow at 375px; the navigation drawer; long labels/statuses; button wrapping; visible keyboard focus on every interactive element, including any current-page/active-state indicator that layers a box-shadow or outline on top of the sitewide `:focus-visible` rule.

## Full-rollout gates (PID §E10-E12, now in force)

- **Real browser acceptance** at 1280/768/375 proving: keyboard-only navigation; visible focus; no horizontal overflow; no inaccessible colour-only statuses; no clipped controls; no unreadable small text; no broken sidebar/drawer; no duplicated navigation DOM; no unreachable primary actions. A complete novice-user journey must be run: login → Home → start/continue Foundations → Stage 1 → a representative Stage 4 question → Risks & Actions → Security Policy → Security State → Company → locate the Customer Zero reset control → Customer Assurance.
- **Fresh Independent UX/accessibility audit — mandatory, not optional.** A fresh reviewer, never the Implementer, challenging hierarchy/clarity/consistency/typography/whitespace/density/button prominence/form usability/mobile presentation/keyboard behaviour/focus/colour-status clarity/empty-error states/perceived commercial quality. Technical correctness alone cannot produce GREEN for this rollout.
- **Security/regression gate**: full existing test suite; `makemigrations --check`; all seven required GitHub checks; `gitleaks`; dependency scan; SAST/CodeQL; Trivy; tenant isolation; reset isolation; authenticated browser flows; zero unexpected AI calls; DARWIN untouched.

## Required durable artefacts (PID §E13)

`docs/evidence/M008E-BROWSER-RESPONSIVE.md`; `docs/evidence/M008E-ACCESSIBILITY-UX-AUDIT.md`; `docs/evidence/M008E-FINAL-AUDIT.md`; `docs/evidence/M008E-ARCHITECT-ACCEPTANCE.md`.

## Decomposition note

Given the number of authorised surfaces, this Work Order is expected to be delivered as multiple bounded, independently-reviewable Delivery Controller dispatches (e.g. grouped by related surface — Foundations/Stages, Risk & Policy surfaces, Company/Governance surfaces, Customer Assurance/pre-organisation surfaces) rather than one single Implementer pass across the entire application, consistent with this project's established bounded-delivery discipline. Each increment still answers to this one Work Order and its invariants/gates in full.

## M009

M009 remains paused and unauthorised by this Work Order.
