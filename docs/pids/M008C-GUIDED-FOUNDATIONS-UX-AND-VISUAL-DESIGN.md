# M008C — Guided Foundations Journey and Professional User Experience

**Parent:** M008. **Depends on:** M008A reset (for repeatable tests), M008B Product Authority-approved question semantics.  
**Status:** UX DESIGN first; no material UI implementation before Product Authority accepts real clickable prototype/screen examples.  
**Preserve:** M007's single `templates/application_shell.html`, `ProductArea`/session/tier guards, Home's two canonical metrics, 18-item Foundations worklist and actual secure routes; don't clone menu DOM or create a second entitlement layer.

## C1. Product problem

The first Product Authority usability test found the working product confusing and intimidating for a typical owner/manager; low presentation quality prevented imagining useful follow-on features. M007 correctly built structural plumbing, not a final onboarding journey. This PID addresses comprehension, action sequence, clarity and visual hierarchy, not merely colours.

## C2. Intended novice experience

- **Home**: one unmistakable primary action **Start/Continue Security Foundations**, next recommended action, the M007 *Foundational Security Posture* and *Security Foundations Completion* cards with human explanations. The latter can increase even when posture stays poor. Never invent a single composite “secure” rating, compliance badge or inaccurate certification signal.
- **Foundations**: a guided five-stage journey: 1 **Your business** (basic shape and tools), 2 **Your people and workplaces** (accountability/how people work), 3 **Your security** (the 12 baseline controls with specific multiple choices), 4 **Your risks and actions** (suggested risk scenarios, factual gaps, selected remediation), 5 **Your security policy** (preview, corrections by structured choices, explicit review/approval, immutable downloadable version). Stage count is navigation, not a stored security score.
- Each question screen shows one primary decision, plain-English context, 3–6 substantial choices where appropriate (not a rigid count if correctness needs more), **Not sure** and evidence link where relevant. Conditional follow-ups only when justified by verified selection; “Other — describe below” is not an allowed escape hatch for Foundations. For unsupported situations provide *This doesn't describe us / request review* as a structured exception state, not a narrative text input or invented fact.
- Save and return later. Back retains exact selected option; edit updates canonical fact and marks dependent answers stale where necessary; no forced completion. No unclear action button labels like “Submit”, “Open” or “Generate” without contextual meaning.
- **Risk/action review** deliberately separates “what is happening now” from “what we recommend next”; unsupported requirements remain unmet until done. A risk reviewed is not a risk solved.
- **Policy** preview before approval, important warnings near the relevant section, what will be asserted clearly visible; sign-off by proper Policy Authoriser only. Version/review date handled by existing lifecycle. A document does not improve baseline states simply by existing.

## C3. Discovery and design deliverables (mandatory STOP gate)

1. Exhaustive inventory of FOUNDATION-reachable routes/forms/widgets as they exist in GitHub main, including old direct URL paths for Profile, Baseline, asset protection, Risk edit, Evidence, Remediation, Policy editor and Home/Foundations; classify every `<textarea>`, contenteditable, `CharField` rendered as multi-line, “Other” box and text-based POST parameter. Identify Customer Assurance Monthly+ carve-out and unavoidable short identifiers.
2. Task analysis: persona A (remote 12-person Microsoft 365 business), persona B (office-first Google Workspace business), persona C reset unknown. Capture expected customer action, required facts, actual canonical owner and screen state per step. Screen transitions must correspond to reachable server-side URL and guard; no decorative dead ends.
3. Build a **navigable responsive prototype** in the project's existing HTML/CSS idiom (or a clearly labelled static click-through under `docs/design/`) with 375, 768 and 1280 captures. Show actual Home, stage index, a baseline question, conditional follow-up, unknown/gap feedback, 18-item worklist, risk/action view, policy preview and confirmation. Not a technical wireframe without visual hierarchy. Present two design variants only if they embody a meaningful choice; no design-framework hunt.
4. Product Authority reviews wording, next-action logic, navigation labels, stage order, spacing, typography, visual density, small-screen accessibility and policy-preview entry. Record decisions in `docs/evidence/M008C-UX-PROTOTYPE-AND-APPROVAL.md` with date, screenshots and explicit accepted/rejected items; **no auto-assumed acceptance**.

## C4. Visual system and interaction rules

One design language: existing application shell/nav, consistent typography and spacing scale, comfortable reading widths, clear contrast, selectable whole option cards backed by native radio/checkbox controls, readable inline help, status chips with text not colour alone, page titles that match navigation, persistent progress indicator that doesn't confuse stage position with 18-item completion, mobile sticky Continue when appropriate without hiding keyboard content. Retire technical explanatory copy such as “worked out fresh from records” where customer-facing; use “Based on what you've told us” with provenance disclosure. Avoid cybersecurity acronyms unexplained; expand MFA once.

Accessibility target WCAG 2.2 AA, with explicit functional checks for native focus semantics, skip link, 375/768/1280 horizontal overflow, active and disabled state, keyboard-only form completion, discernible errors, programmatic label/instruction associations, screen reader announcements for conditional questions and saved state, logical headings, 200% zoom. M007's accepted overlay-click focus-return `strict=True xfail` becomes a tracked improvement: if the new drawer is touched, fix and flip to a passing test; do not silently carry or delete the test.

## C5. Route and architecture boundaries

Single canonical server-rendered Django flow. Templates may include reusable form components/partials; no separate SPA state and no second Foundation truth store. GETs never mutate canonical data. POST requires CSRF, same membership/tenant-scope and M007 `require_capability` guard as ordinary pages. PAUSED Home stays minimal; FOUNDATION can use its own journey; MONTHLY/PRO inherit Foundation as before. An old direct URL must never allow narrative fields to bypass the guided answer service. Do not duplicate existing Security/Company data, routing or policy draft documents; adapt old views to read-only summaries/structured editors where appropriate. No disabled-only hiding as substitute for server validation.

## C6. Test protocol / acceptance

- Real Chromium end-to-end novice scenario from M008A reset: Home → first step → choose → continue → back/edit → log out/relogin → resume → partial/no/unknown/security outcomes → risks/actions → policy review and approved artifact. All at 375,768,1280; no explanatory oral coaching needed to locate primary actions.
- At least one Product Authority hands-on round before UX closure, written observations and triage: P0 stop, P1 confusion/product accuracy, P2 cosmetic. Use **concrete tasks**: user can locate where to start, find meaning of two metrics, express uncertain response, return/edit answer, locate outstanding action, distinguish action from current fact and locate policy preview. Do not claim externally validated UX research from a single internal walkthrough.
- Automatic tests for applicability/progress, no hidden extra completion score, no model calls on navigation, stale dependent answers, state recovery after errors, XSS in identifier labels, entitlement and session replay. CSS/JS no regressions on Home/Foundations or the separate Customer Assurance route.
- Produce `docs/evidence/M008-BROWSER-USABILITY.md` with screenshot evidence and identified residuals, including confirmed real-browser rendered pages (not just template unit tests). Product Authority must explicitly accept if key tasks still seem confusing.

## C7. Non-goals

No “modern-looking” redesign unconnected to customer tasks, chart framework, icon pack, native app, gamification, historical trend display, generic AI chat, rich-text authoring, or modifying entitlement tiers. Don't rename Customer Assurance into Foundations or add bulk document import in this module.
