# WO-M008E-WI1 — Design Checkpoint: Tooling, Skill, Current-State Review, Three-Page Prototype

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Exact base SHA:** `186a3e6de7d5aee16840de9e3ddb10b81b002487`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Scope

Everything in M008E PID §E14 ("First action") up to and including the Product Authority stop gate (§E5). **This Work Order does NOT authorise rolling any design across the rest of the application, and does NOT authorise M009.**

## Non-negotiable boundaries (reproduced from the PID — binding)

- No change to tenant isolation, the entitlement model, FOUNDATION/MONTHLY/PRO/PAUSED behaviour, the Customer Zero reset security boundaries, the structured question catalogue, option semantics, UNKNOWN≠NO, PARTIAL≠YES, M007 completion/posture calculations, deterministic policy behaviour, the normative/implementation-status separation, approved-policy immutability, Customer Assurance behaviour, zero-LLM Foundations navigation, existing AI contracts, or current routes.
- No new reset mechanism. No weakening of the existing reset's server-side gate. No duplicated security logic in a template — the Home reset affordance (if built in this WI) must reuse the exact same server-side gate the existing `/organisations/<id>/dev-tools/reset/` route already uses, never re-derive or approximate it.
- No SPA framework, no React/Vue/etc., no Tailwind, no commercial component library, no large new JS dependency, no design-framework migration.
- No real customer data. No production deployment. No M009 work of any kind.
- This Work Order's own output is bounded to exactly three representative surfaces (Home, Foundations/guided-question, Company/Organisation hub) plus the required documentation/skill artefacts below — never a broader rollout.

## Implementer tasks, in order

### 1. Design tooling / capability check

Check what design/browser-testing capabilities are available to you (a frontend-design-oriented skill, if one is listed; real Chromium/Playwright support). Use whichever applies. If no dedicated design skill is available, proceed with direct Playwright scripting for all real-browser work (this repository's own established, proven technique — see `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`) and real CSS/HTML authoring by hand; do not block on tooling that isn't present.

### 2. Create the durable design skill

Create `.claude/skills/infosecurs-ui-design/SKILL.md` with the content specified in PID §E3 — the audience, emotional outcome, avoid-list, interaction doctrine, status-colour semantics, and accessibility target given there verbatim. This is durable design doctrine for all future work on this product, not a one-off note — write it to be genuinely reusable by a future, context-free dispatch.

### 3. Current-state visual capture (PID §E4 Phase 1)

Bring up a disposable Docker Compose stack from this worktree (distinct project name/ports, never touching the live `infosecurs-relocation` dev stack or any other running stack on this host — check `docker ps` first). Install Chromium at runtime per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`. Using real Chromium, capture screenshots at 1280px / 768px / 375px of: Home; the Foundations workspace; Stage 1; one representative Stage 4 question; Risks & Actions; Security Policy; the Company/Organisation hub; the current Customer Assurance page; the reset confirmation page (reachable with `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` set on your own disposable stack — do not touch the live dev stack's own flag).

Write `docs/evidence/M008E-CURRENT-UX-REVIEW.md` documenting, with the screenshots as your evidence: visual-hierarchy issues; spacing issues; typography issues; content density; navigation quality; action-hierarchy issues; mobile issues at 375px specifically; status-clarity issues; accessibility/focus issues; inconsistencies across pages. Be specific and critical — this document's whole purpose is to name real problems, not to be diplomatic about them. **No product code changes in this step.**

### 4. The three-page design checkpoint (PID §E4 Phase 2)

In this same worktree, produce real HTML/CSS changes — server-rendered Django templates and CSS, exactly as this codebase already works, no new framework — for exactly these three representative surfaces:

- **Home** (`organisations/templates/organisations/detail.html` and its view) — including the newly-discoverable DEV Customer Zero reset panel (PID §E2/§E9): a clearly differentiated development-only panel ("DEV · Customer Zero" / "Reset this synthetic organisation to its original unanswered state." / a button linking to the EXISTING confirmation page, never executing reset directly). Gate its rendering using the exact same conditions the existing reset view already checks — read `organisations/views.py::customer_zero_reset` and whatever context/flag the template layer already has access to, and reuse that, never re-implement the check. Write a test (or at minimum a clear manual verification you document) proving the panel is absent when any one of the three gates (dev env, flag, fixture organisation) is false.
- **Foundations / the guided-question experience** — the Foundations workspace page and at least one Stage 4 question page.
- **Company / Organisation hub**.

Establish, across these three pages consistently: a typography scale; a spacing system; page-width/content-width rules; navigation/sidebar treatment; buttons (primary/secondary/destructive, clearly distinct); cards/panels; status chips/badges; a progress visual; form controls; option cards; alerts/warnings; empty states; section headers; development-only styling (for the new reset panel specifically — visually distinct from ordinary product content, clearly marked as a dev affordance); responsive rules at 1280/768/375.

Follow PID §E8's direction: build reusable CSS classes/components (page container, page header, page intro, section, card/panel, metric, status, progress, option group, buttons, alert/warning, empty state, metadata, table/list, responsive stack/grid), not page-specific one-off selectors. Refactor existing CSS where warranted rather than only adding new rules on top.

Capture real-Chromium screenshots of all three redesigned pages at 1280/768/375 (before-and-after pairs, using your Phase 1 screenshots as "before").

Write `docs/evidence/M008E-DESIGN-DIRECTION.md` describing: the design language/visual direction chosen and why; the typography scale; the spacing/layout system; the colour and status-badge semantics (and how they preserve the existing green=supported/amber=attention/red=gap/neutral=unknown meaning — never colour-only); the reset-control placement and gating; accessibility choices made; the complete list of changed/new files; any new dependency added (there should be none — if you find yourself wanting one, STOP and report it as a question rather than adding it).

## Verification before you report back

- The existing full test suite for every app whose templates/views you touched still passes (reuse this session's own established disposable-stack-with-real-Chromium convention).
- `makemigrations --check --dry-run` clean (you are not expected to need any migration for this WI — if you find yourself wanting one, STOP and report it).
- `gitleaks detect` clean.
- The Home reset-panel gating is proven both ways: visible when all three conditions hold, absent when any one doesn't (at minimum, test the "flag off" and "non-fixture organisation" cases directly).
- Confirm no SPA framework, no new large JS dependency, no Tailwind, nothing from the "do not introduce" list was added — `git diff` the lockfiles/package manifests if any exist in this repo, confirm unchanged.

## STOP conditions

- Any UX improvement that seems to require changing an underlying product workflow (not just its visual presentation) — STOP, report it, do not implement it.
- Any temptation to roll the new design onto a fourth page — STOP, this WI is bounded to exactly three.
- Any need for a new dependency, framework, or migration — STOP, report it as a question.

## Report format

Report file-by-file what you built, your own design rationale (matching `docs/evidence/M008E-DESIGN-DIRECTION.md`'s own content, this is just a summary for the Delivery Controller), full `git diff --stat`, your test run output, and screenshot file locations (paths on dell-debian, not pasted images). Commit everything to your branch yourself (clear commits, each ending `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`). Do not push, do not open a PR — the Delivery Controller reviews first, then decides whether to dispatch an audit before returning to Product Authority, per the PID's own stop-gate structure (§E5 is a return to Matt for visual approval, not yet a technical PR/merge cycle).
