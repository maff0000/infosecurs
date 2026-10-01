# M008 — Guided Security Foundations Experience, Structured Answers, Repeatable Testing & Policy Quality

**Status:** PRODUCT AUTHORITY AUTHORISED FOR PID PREPARATION AND BOUNDED DELIVERY; catalogue/UX/policy design checkpoint mandatory before substantive workflow implementation.  
**Date:** 2026-09-30  
**Product Authority:** Matt  
**Central Product/Architecture:** Matt + Central Architecture  
**Delivery:** GUNNAR → FORGE Engineer(s), independent PL verification, fresh independent Auditor  
**Repository:** `maff0000/infosecurs`  
**Development host/root:** `dell-debian` / `/srv/infosecurs`  
**Authoritative baseline:** M007 CLOSED PRODUCT_GREEN, frozen product `fb5be593131fde51d4fc2aafce268f64a5816850`; current main as verified 2026-09-30 `24173757c7fdcc856e3163ae6e14ebb2f981716e` (dev exposure PR #77). Revalidate before work.  
**Development GUI:** `http://192.168.11.10:8884/`; retain working dev service and unrelated port-8000 DARWIN container.  
**Subordinate PIDs:** M008A (reset), M008B (question methodology), M008C (guided UX), M008D (policy quality). They are normative, not optional guidance.

## 1. Product Authority's real-world feedback

First hands-on user test: usable technical foundation, but an ordinary non-security SME user finds the experience confusing and insufficiently intuitive; interface quality obstructs meaningful feedback on future features. End-of-journey policy output did not match Product Authority expectations (no actual policy artefact supplied yet, so **do not invent a diagnosis**). Manual testing needs a safe reset button. The standard Security Foundations product **must not ask customers for free-form narrative**: high-quality, conditional, prebuilt answer choices should establish the facts deterministically without repeated AI calls.

## 2. Outcome

A first-time SME owner (roughly 5–49 staff), with no cyber terminology knowledge, can reset synthetic Customer Zero in DEV, begin a clearly guided journey, answer relevant, professionally worded controlled questions, review actual gaps/actions, obtain a credible readable policy generated from verified structured facts, and return later with progress intact. It must be possible to repeat the same journey deterministically during testing.

**Governing doctrine:** *Customers answer questions. Infosecurs builds their security foundation.*  
**Existing doctrine remains binding:** *Structured first. Prose by exception. AI clarifies. Customer confirms. Application owns truth.*

## 3. Product non-negotiables

1. **No discretionary multiline/free-narrative field on ANY customer-facing route reachable within the FOUNDATION product**, including old Profile, Baseline, Assets, Risks, Evidence, Remediation, Policy and guided routes. Fix the reachable legacy surfaces, not merely conceal them on the new wizard. Preserve truthful submission validation server-side. Short, strictly bounded identifiers (legal name, human name/email, asset label), date/number, secure evidence upload, and externally supplied Customer Assurance questionnaire input are exceptions **by data type**, not loopholes for narrative collection. Document each exception.
2. All substantive questions use a finite, versioned, reviewed catalogue: stable question/option codes, plain-English wording, short explanation, applicability rule, dependencies, allowed alternatives, and deterministic mapping to canonical facts/controls. Never map `unknown` to `no`, `partial` to `yes`, or unverified assertions to evidenced/implemented.
3. The existing 12 baseline control keys, security-state and risk assumptions, M007 18-item completion catalogue, posture factors/weights/rounding and single source of truth remain unchanged **unless a separately reviewed methodology change is expressly approved**. M008 should improve how the answers are gathered, not silently move the score.
4. Foundational interactions are deterministic, with **zero LLM calls for normal question rendering, option selection, validation, progress, navigation, metrics or reset**. An optional consequential AI step requires a defined purpose, bounded structured grounding, customer confirmation and separately measured token cost. No generic chat in Foundations.
5. Existing M001–M007 organisation membership, session, PAUSED/FOUNDATION/MONTHLY/PRO entitlement checks, tenant isolation, provenance and file handling are preserved. `PAUSED` cannot use the reset or guided content merely by guessing a URL. No real customer data.
6. A policy is a normative organisational document, **not proof that a security control exists**. Current state, proposed commitment and gap must remain separate, even in polished language or a PDF. Keep existing approved-policy history immutable and downloads reproducible from the stored approved version.
7. Single existing Django/server-rendered modular monolith; no SPA migration, new custom agent framework, paid design framework, external question service, new LiteLLM architecture, or unnecessary dependencies.
8. Desktop, tablet and mobile at 1280/768/375; real Chromium, keyboard, focus, readable typography, sensible contrast, error recovery and WCAG 2.2 AA design target. A visual facelift without usability improvement is not completion.

## 4. Acceptance-stage ordering / stop gate

**Phase 0 — rebaseline:** GUNNAR validates main, preserved release identities, `/srv/infosecurs`, running `:8884` dev service, existing tests, relevant M007 residuals, and all actual FOUNDATION-reachable routes/POSTs. Land these PIDs in Git through an audited documentation PR before implementation. GitHub is authoritative.

**Phase 1 — M008A reset:** deliver the explicitly dev-only, scoped, safe Customer Zero reset independently. A functional reset is urgent for repeatable hands-on tests; inspect the entire tenant-owned object/file dependency graph before any delete. Close M008A GREEN independently.

**Phase 2 — M008B + M008C + M008D DESIGN-ONLY:** produce and submit for Matt's explicit product review: (a) exhaustive field/form/route inventory and no-narrative exception register, (b) all 12 control question/option/mapping proposals with conditional logic and canonical destinations, plus profile/governance/workplace/risk/evidence/remediation paths, (c) responsive HTML/CSS click-through prototype or browser screenshots using the existing design system, and (d) two or more *actual synthetic* proposed policy PDF examples with source fact matrix and policy quality rubric. Include user's current policy sample **if provided**; otherwise label qualitative diagnosis unresolved. **STOP here until Product Authority approves wording, flow and document direction.** Do not infer approval from general M008 green light.

**Phase 3 — implementation after that approval:** M008B deterministic question service/persistence bridge; M008C polished guided journey and removal of Foundation-visible prose forms; M008D policy framework and review UX. Deliver in bounded PRs with real-browser proof and PL review.

**Phase 4 — final acceptance:** repeatable reset→start→complete→review→policy, two synthetic contrasting companies, security and methodology challenges, full six fake/live AI evals because policy/customer assurance are consequential, backup/restore/fresh install, exact-SHA release candidate and zero-context independent Auditor. Only Central Architecture declares M008 PRODUCT_GREEN. Stop; do not start M009/production.

## 5. End-user information architecture

- Entry for non-PAUSED customers: a prominent **Start / Continue Security Foundations** primary action; existing Home two metrics remain visible and accurately derived. PAUSED Home remains minimal with no data/metric calls.
- Guided stages (names provisional until design gate): **Your business → Your people and workplaces → Your security → Risks and actions → Your policy**. Progress derives from saved canonical responses; no artificial completion flag.
- Each stage: one understandable concept per screen, concise explanation, a small mutually exclusive set of substantial answer choices, only applicable follow-ups, save-and-return, Back, clear Not sure, and an honest review/confirm step. Do not force confident answers. Avoid an endless single long form.
- Technical sidebar Security/Company routes continue to function and be guarded. They must not reintroduce narrative input for Foundation users; prefer route to governed structured editor shared with wizard. Customer Assurance remains a distinct Monthly+ workflow; its externally supplied questions and reviewed responses are outside the Foundations free-text restriction.
- Preserve the M007 difference: **Security Foundations Completion = work completed**, **Foundational Security Posture = assessed protection**. A company can complete the programme with poor protections. Do not promise compliance, certification or a clean bill of health.

## 6. Data architecture and migrations

Existing typed canonical stores remain authoritative. `OrganisationProfile` records business context; `BaselineAssessment`/`BaselineAnswer` record 12 baseline statuses; `Workplace` and governance hold actual organisation details; risk, evidence, remediation and policy have their governed models. Any new selection-detail rows must be **provenance/source metadata tied one-to-one to these facts**, not a competing source of truth or a new cross-domain JSON bag. One application service validates an option and writes the corresponding canonical fact + selection metadata transactionally; every legacy path must use or respect that rule. Old notes remain historical inert data, never silently reinterpreted into assertions. Preserve audit/activity history for non-test tenants and approved policy history. Add explicit catalogue versioning and migration/update semantics, retaining stable published control keys and historical interpretation.

## 7. Policy output redesign principle

No more default unbounded AI composing an entire foundational policy as prose from raw customer answers. The default should use a **governed, versioned, professionally authored template/clauses** selected from explicit confirmed facts, with deterministic warnings for gaps/unknowns. If an LLM is used for a bounded exception, it must receive only structured canonical projections and pass the existing truth/security checks; render/approval truth remains application-owned. Preserve existing eight policy section keys if possible, version immutability and PDF history; if source enums need a deterministic/template member, use an additive compatible migration and versioned provenance, not mislabel it `ai` or `manual`. Human must explicitly review and approve.

## 8. Required test personas

- **A — small remote-first Microsoft 365 business:** partial staff MFA, administrator MFA, mixed device protection, backups not restore-tested, missing formal training. Honest risks and warnings; policy must not call partial controls universal.
- **B — office-first business:** Google Workspace, controls largely confirmed, a missing incident route and no supporting evidence on some items. Completed questions do not make evidence magically verified.
- **C — newly reset/unknown:** no substantive answers; both metrics and all states derived correctly; no implementation claims in preview/policy; unsafe generation/approval must fail closed or show accurate disclosures.
- Tests at Foundation, Monthly, Pro and Paused tiers and a second tenant with comparable data to prove no leakage.

## 9. Shared M008 delivery requirements

- Baseline and final direct screenshots, real Chromium functional tests (375/768/1280), XSS, CSRF, session tampering, tier bypass, cross-tenant object ID probes, keyboard drawer/focus (including M007 L1), screen-reader accessible labels, double-submits, edit/back/restore, stale answer dependencies, submission of forged option codes, and counts/metrics separation.
- Explicit AI cost accounting: normal Foundations interaction = 0 calls; record generation calls/token totals separately, including retries; never silently call AI on keystrokes or page navigation.
- Real novice tasks: start, answer, correct, return, identify next action, understand two scores, inspect policy. Matt's first pass is the product checkpoint; distinguish observed failures from suggested enhancements.
- Preserve non-test tenant data, backups and all authorised M001–M007 behavior. Same six CI checks + CodeQL, gitleaks, Trivy zero Critical/High (under established scan settings), fresh clone, fresh volumes, backup/restore, SHA-bound image `DEBUG=False` with no source bind/secrets, zero-context independent Auditor after final source freeze. Evidence-only post-audit commits may preserve verdict after mechanical verification.
- Existing M006/M007 images are protected artifacts and MUST NOT be overwritten/deleted. `DARWIN` owns host port 8000; dev GUI remains on `192.168.11.10:8884` unless explicitly revised. No changes to unrelated Docker projects.

## 10. Evidence set (land in `docs/evidence/`)

`M008-PREFLIGHT-AND-FORM-INVENTORY.md`, `M008A-RESET-SAFETY.md`, `M008B-QUESTION-CATALOGUE-REVIEW.md`, `M008C-UX-PROTOTYPE-AND-APPROVAL.md`, `M008D-POLICY-SAMPLES-AND-RUBRIC.md`, `M008-TEST-MATRIX.md`, `M008-BROWSER-USABILITY.md`, `M008-AI-COST-AND-EVALUATION.md`, `M008-RECOVERY-AND-RELEASE.md`, `M008-AUDIT-0001.md`, `M008-PL-IMPROVEMENTS.md`, `M008-CLOSURE.md`. Evidence may be split into WI-level reports but every area must be traceable. Include screenshots or reproducible artifacts, not assertions alone.

## 11. M008 PRODUCT_GREEN definition

1. M008A reset works twice identically with preserved identity, seed metadata, other tenant data and no outstanding orphan evidence.
2. Matt has explicitly accepted catalogue/answer semantics, guided wireflow and policy sample direction *before* workflow implementation.
3. All FOUNDATION-accessible narrative inputs are removed/replaced (exceptions enumerated and confirmed); server rejects forged free-text fields as authoritative inputs.
4. Every choice is versioned, server-validated, deterministically mapped, tenant-scoped and user-confirmed; old controlled 12-key truth and M007 18-item methodology retained unless separately authorised.
5. Normal Foundations page-to-page flow makes zero LLM calls and accurately communicates progress, unknowns and findings.
6. Both synthetic personas produce factually appropriate risks/actions and legible policy drafts, with uncertainty/gaps not rewritten as existing controls; approval/download history immutable.
7. Existing M001–M007 route/security/AI tests remain green; all six fake/live AI evaluations run green on the exact candidate; any new deterministic policy renderer has golden text/PDF tests.
8. Real-browser accessibility, functional UX, responsive layout and customer task walkthroughs PASS; user testing feedback recorded, not hidden by a technical-only test suite.
9. CI/CodeQL/gitleaks/Trivy/migrations/backup-restore/fresh-install exact-SHA release/independent Auditor GREEN, no unauthorised post-audit source delta, canonical main clean.
10. Customer data/production still NOT AUTHORISED; GUNNAR stops with PL improvements and complete closure for Central Architecture.

## 12. STOP / non-goals

Stop on ambiguity about what a structured answer asserts, missing data ownership, policy factual overclaim, inability to reset without broad/shared deletes, customer auth/session weakening, existing score methodology drift, unbounded model calls, test-only reset reachable under production, uncontrolled migrations, real customer data, or unauthorised post-audit code changes. No subscription/billing, bulk questionnaire file ingestion, ISO certification platform, historical score trends, native mobile app, AI chatbot, redesign of provider gateway or new compliance standards programme in M008.
