# M008E — Product UX & Visual Design Hardening

**Parent:** `M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Status:** AUTHORISED — bounded product-design milestone, Phase 1 (checkpoint) only. Does not authorise M009.

M008E is **not** authority to redesign product architecture, change security truth, alter M008 methodology, change entitlement behaviour, weaken accessibility/security controls, or begin M009.

## E0. Governing chain

This milestone follows the same mandatory delivery chain already governing this repository (`docs/architecture/DELIVERY-GOVERNANCE.md`): Architecture decision → PID / Amendment → Git-tracked Work Order → Delivery Controller → Implementer → Independent Audit → PR → Architect Acceptance → Merge → Closure. Every Delivery Controller, Implementer, and Auditor prompt dispatched under this PID must repeat the governing boundaries below and must not rely on prior chat memory.

## E1. Purpose

Transform the existing technically-correct M008 product into a visually polished, coherent, commercial-grade SME security-assurance product.

Current UI characteristics requiring improvement:

- overly generic Django/admin-style presentation;
- weak visual hierarchy;
- repetitive plain cards;
- insufficient distinction between primary and secondary actions;
- limited product personality;
- weak progress/status visualisation;
- functional but under-designed forms/question screens;
- navigation/sidebar that works but does not yet feel premium;
- insufficiently visible Customer Zero test/reset affordance;
- pages that look like internal tooling rather than something an SME would pay for.

**The goal is not "make it flashy."** The goal is: calm, clear, premium, trustworthy B2B software for non-security-specialist SME owners/managers — mature SaaS, professional financial/software tooling, deliberate visual hierarchy, excellent typography, confidence and clarity, restrained security aesthetics.

**Do not produce:** hacker/neon aesthetics; matrix imagery; excessive gradients; generic Bootstrap look; excessive card containers; gimmicky animation; overly dense enterprise dashboards; cybersecurity cliché iconography; dark-mode-first SIEM aesthetic.

## E2. Customer Zero reset discoverability

The existing reset implementation and security boundaries are already accepted (M008A, `docs/evidence/M008A-RESET-DELETION-MANIFEST.md`). **Do not create a second reset mechanism. Do not weaken the current protections.** The existing reset route/service (`organisations.views.customer_zero_reset`, `/organisations/<organisation_id>/dev-tools/reset/`, `organisations.reset_service.reset_customer_zero_organisation`) remains canonical.

Current gating, unchanged: `DJANGO_ENV=development`; `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true`; organisation is the trusted `CustomerZeroFixture`; authenticated/authorised user passes the existing reset controls.

The usability problem is discoverability only: the reset control currently lives under the Organisation/Company hub and is too difficult for Product Authority to find during repeated testing.

M008E must make the existing reset action visibly discoverable on Customer Zero's primary Home experience. Preferred direction — a clearly differentiated development-only panel/banner:

> **DEV · Customer Zero**
> Reset this synthetic organisation to its original unanswered state.
> `[ Reset test organisation ]`

The action **must** link to the existing confirmation page. It **must not** directly execute reset from Home. It **must not** appear outside development; when the explicit reset flag is off; for a non-Customer-Zero organisation; or for an unauthorised user. **Use the exact same server-side gate already governing the reset feature — never duplicate security logic in a template.**

## E3. Design tooling / Claude Code capabilities

Before implementation, evaluate and use the appropriate Claude Code design capabilities:

- **Frontend-design capability** — for stronger composition, typography, spacing, hierarchy, colour, distinctive SaaS design, and avoidance of generic AI-generated frontend patterns, if available to the dispatched agent.
- **Real-browser (Chromium/Playwright) inspection** — do not redesign purely by reading templates/CSS. Navigate the real application, capture screenshots, inspect viewport behaviour, validate rendered hierarchy, test keyboard/focus, review actual states and content. Required viewport widths: 1280 / 768 / 375.
- **A project-specific design skill**, `.claude/skills/infosecurs-ui-design/SKILL.md`, created under a governed Work Order as durable design doctrine for all future work on this product. It must encode at minimum: the audience (SME owner/manager/security-responsible person, typically non-specialist, roughly 5–49 employees); the intended emotional outcome (calm, trustworthy, capable, clear, professional, reassuring without pretending everything is fine); what to avoid (hacker aesthetics, excessive dashboards, generic Bootstrap visual language, excessive rounded cards, meaningless gradients, tiny low-contrast text, technical cyber jargon, visual clutter, overuse of icons, "AI-looking" generic SaaS design); the interaction doctrine (one obvious primary action per screen; strong headings; concise explanatory copy; visible progress; substantial, clear option controls; unmistakable selected state; legitimate "Not sure" treatment; clear gaps/warnings/actions; restrained secondary information); status-colour semantics (green = supported/satisfactory/completed where appropriate; amber = attention/confirmation; red = gap/action required; neutral = unknown/not applicable/informational; colour is never the sole carrier of meaning); and accessibility (WCAG 2.2 AA target, visible focus, keyboard operability, readable typography, appropriate hit areas, responsive 375/768/1280, no keyboard traps).

## E4. Design approach — do not redesign every page yet

This milestone starts with a bounded design checkpoint, in two sequential phases, before any broad implementation.

**Phase 1 — current-state visual capture.** Using real Chromium against the canonical dev environment, capture representative current-state screenshots of: Home; the Foundations workspace; Stage 1; a representative Stage 4 question; Risks & Actions; Security Policy; the Company/Organisation hub; the current Customer Assurance page; the reset confirmation page. Capture at least 1280px / 768px / 375px for each. Document visual-hierarchy issues, spacing issues, typography issues, content density, navigation quality, action hierarchy, mobile issues, status clarity, accessibility/focus issues, and inconsistencies in `docs/evidence/M008E-CURRENT-UX-REVIEW.md`. **No product changes in this phase.**

**Phase 2 — the design checkpoint.** Produce a visual-design direction for ONLY three representative surfaces: Home; Foundations / the guided-question experience; the Company/Organisation hub. These three establish the design system — **do not roll it across the whole product yet.** Produce real HTML/CSS changes in an isolated branch/worktree and capture screenshots at 1280/768/375. The design must establish: typography scale; spacing system; page-width/content-width rules; navigation/sidebar treatment; buttons; cards/panels; status chips/badges; progress visual; form controls; option cards; alerts/warnings; empty states; section headers; development-only styling; responsive rules.

The implementation must prefer the existing Django/server-rendered architecture. **Do not introduce:** an SPA framework; React/Vue/etc.; Tailwind unless separately justified and approved; a commercial component library; a large new JS dependency; a design-framework migration. Existing CSS may be refactored where warranted.

## E5. Product Authority stop gate

After the representative Home / Foundations / Company design is rendered and captured: **STOP. Do not roll the redesign across the remaining application.** Return to Central Architecture / Product Authority with: before/after Home screenshots; before/after Foundations screenshots; before/after Company screenshots; 1280/768/375 views; a description of the design language; typography choices; the spacing/layout system; colour/status semantics; reset-control placement; accessibility observations; the complete changed-path list; and any dependencies added (preferably none). **Matt must explicitly approve the visual direction before broad implementation — general approval of M008E is not approval of the proposed design.**

## E6. After product approval

Only after explicit Product Authority approval may the Delivery Controller issue implementation Work Orders to apply the accepted design system across the current application. Expected surfaces: Home; Foundations; Stages 1–4; Risks & Actions; Security Policy; Security State; Baseline; Assets; Risks; Evidence; Remediation; Company; Profile; Governance; Workplace; Activity; Customer Assurance; the dev reset confirmation screen; login/pre-organisation surfaces where visually appropriate.

**Do not alter the underlying product workflow merely for visual consistency.** If a UX improvement requires a behavioural/product-flow change, STOP and return to the Architect.

## E7. Product invariants — M008E must preserve

Existing tenant isolation; the entitlement model; FOUNDATION/MONTHLY/PRO/PAUSED behaviour; the Customer Zero reset security boundaries; the current structured question catalogue; exact option semantics; UNKNOWN != NO; PARTIAL != YES; M007 completion/posture calculations; deterministic policy behaviour; the normative-policy/implementation-status separation; existing approved-policy/history immutability; Customer Assurance behaviour; zero-LLM normal Foundations navigation/interaction; existing AI contracts; current routes unless an explicit UX change is separately accepted; no real customer data; no production authorisation. **Visual design must never alter truth semantics.**

## E8. CSS / component direction

Build a coherent, lightweight internal design system rather than individual page-specific hacks. Prefer reusable classes/components for: page container; page header; page intro; section; card/panel; metric; status; progress; option group; primary/secondary/destructive buttons; alert/warning; empty state; metadata; table/list; responsive stack/grid. Avoid giant CSS files full of one-off selectors. Avoid inline-style proliferation. Do not abstract into a generic component framework unnecessarily — this remains server-rendered Django.

## E9. Reset Home control acceptance criteria

When `DJANGO_ENV=development` **and** `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` **and** the current organisation is the trusted Customer Zero fixture: Home visibly shows the DEV Customer Zero reset control, and clicking it leads to the existing reset-confirmation screen. When any gate is false: no reset affordance is rendered on Home. The direct endpoint remains fail-closed under the existing rules regardless. No duplicated reset implementation.

## E10. Real browser acceptance (full-rollout gate, after Product Authority approval)

Final M008E implementation must use actual Chromium at 1280px / 768px / 375px, proving: keyboard-only navigation; visible focus; no horizontal overflow; no inaccessible colour-only statuses; no clipped controls; no unreadable small text; no broken sidebar/drawer; no duplicated navigation DOM; no unreachable primary actions. A complete novice-user task sequence must be run: login → understand Home → start/continue Foundations → answer Stage 1 → answer a representative Stage 4 question → understand Risks & Actions → inspect Security Policy → navigate Company → locate the Customer Zero reset control. A Product Authority who knows nothing about the template locations must be able to find the reset action without being told where it lives.

## E11. Independent UX audit (full-rollout gate, after Product Authority approval)

In addition to the normal technical audit, a fresh UX/accessibility reviewer — never the Implementer — must review screenshots and real browser interactions for: hierarchy; clarity; consistency; typography; whitespace; density; button/action prominence; form usability; mobile presentation; keyboard behaviour; focus; colour/status clarity; empty/error states; perceived commercial quality. They must challenge whether the product looks like a credible SME SaaS product rather than an internal Django engineering interface. **Technical correctness alone cannot produce GREEN for M008E.**

## E12. Security / regression (full-rollout gate, after Product Authority approval)

Do not weaken existing regression coverage. The final gate includes: the existing full test suite; `makemigrations --check`; all seven required GitHub checks; `gitleaks`; the dependency scan; SAST/CodeQL; Trivy; tenant isolation; reset isolation; authenticated browser flows; zero unexpected AI calls; DARWIN untouched. No real customer data. No production deployment.

## E13. Required durable artefacts

Before implementation: this PID. Each implementation unit then requires its own Git-tracked Work Order. The evidence set includes at minimum: `docs/evidence/M008E-CURRENT-UX-REVIEW.md`; `docs/evidence/M008E-DESIGN-DIRECTION.md`; `docs/evidence/M008E-PRODUCT-AUTHORITY-APPROVAL.md`; `docs/evidence/M008E-BROWSER-RESPONSIVE.md`; `docs/evidence/M008E-ACCESSIBILITY-UX-AUDIT.md`; `docs/evidence/M008E-FINAL-AUDIT.md`; `docs/evidence/M008E-ARCHITECT-ACCEPTANCE.md`.

## E14. First action (this WI's own scope)

1. confirm canonical Git/main state;
2. create this PID;
3. inspect/install/configure the required Claude Code frontend-design/browser-testing capabilities as appropriate;
4. create `.claude/skills/infosecurs-ui-design/SKILL.md` under this governed Work Order;
5. capture current real-browser screenshots (E4 Phase 1);
6. prepare the three-page design checkpoint (E4 Phase 2);
7. STOP for Product Authority visual approval (E5).

**Do not start M009. Do not redesign the entire application before the visual checkpoint.**
