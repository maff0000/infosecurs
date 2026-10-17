# M010C PID — IRENE Modal, Conversation, Trusted Knowledge/Skills and Bounded Tools

**Priority:** After task spine and deterministic Foundations adapter. **Goal:** A polished, central AI-first workspace and optional, safe explanatory adviser, while retaining model-free default operation.

## 1. UI contract

Implement IRENE modal after authenticated Home render with four tabs Continue, Tasks, Ask, Activity. Continue always presents server-computed next work, no empty general chat landing; modal large desktop, responsive mobile; Task List available without modal via sidebar. Focus trap only while active, return focus on close, keyboard/screen reader/zoom, user's auto-open preference and no repeated reopening after dismissal. Explain AI identity; no fake human identity; name IRENE, GUNNAR only internal delivery. Permitted route names/capabilities unchanged, new nav entries seeded and guarded server-side.

## 2. Conversation and product-map services

Conversation stored per org+owner user with message ordering, bounded length, role and retention flags; only current user's private history readable unless explicit authorisation. Do not share chat history through organisation-wide task page. Load a small structured state projection and relevant `JourneyCheckpoint` and `SecurityTask` summaries, never a full DB dump. Create versioned Product Knowledge registry mapping actual domain names/relations/services/named routes and tool capabilities. Validate every registered route/tool at boot/test, reject unknown source/URL. Recheck tenant and permissions at every message, read and tool call.

## 3. Tools and skills

Implement allowlisted typed read tools and constrained, user-confirmed task proposals, not arbitrary code/SQL/network/files. Use the `M010-ADVISER-TOOLS-AND-SKILLS.md` registry and sample skill template. Boot with concise rules+registry/version+skill manifest; load only relevant skill. Initial trusted skills: Foundations guide and Task administrator. Optional risk/policy/assurance skill manifests may exist disabled with explicit availability flags until their source services and entitlements are ready; no claims about unsupported features. Skills are Git-reviewed and cannot expand authority.

## 4. Provider boundary and costs

Use existing `trinity-fast`/`trinity-core` aliases behind approved AI gateway. No new model credentials in repo, no direct integration with another vendor. No generative call for normal Foundations questions, task list, progress metrics, task state changes, scheduling and deterministic explanations. Optional Ask uses bounded prompts, schema validation, per-user and per-org rate/cost cap, safe refusal of forbidden actions, no secret/raw-prose projection, provider failure fallback. Store tool outcome and timings redacted. Do not use M009 bulk quota accounting as evidence of a global provider-call ceiling. Numerical budgets/retention/timeout require explicitly approved configuration before enabling live model calls; leave adviser mode OFF until verified.

## 5. Guardrails and action UX

Action proposal shows requested task title, source, assignee, due date and whether it changes security truth (should be no); customer explicitly confirms before bounded write. Never permit model to submit Foundation option without a user-tied UI gesture and current server validation. No AI tools for approve policy, accept risk, certify controls, export/send questionnaire, billing/tier changes, destructive delete or privilege adjustment. Show uncertainty rather than fabricate. Every source link derived through route registry and current permission check.

## 6. Testing

Real UI test across 320/375/768/1280 widths, keyboard, Esc, screen reader roles, focus and auto-open preference; manual app works without JS/AI; provider failure/latency; two-tenant conversation/task/log/cache/canary leak tests, prompt injection in task description/questionnaire/prose, fraudulent model tool command, malformed JSON, tool double-submit/idempotency, revoked membership, tier downgrade, XSS, skill-version tampering, model output bounded. Run prompts through fake gateway; optional live gateway only when explicitly authorised with synthetic test data. Record response schema and helpfulness evaluation, but safe negative controls determine release readiness.

## 7. Evidence and STOP

Evidence `docs/evidence/M010C-IRENE-WORKSPACE-TOOLS.md`: screenshots and accessibility report, boot registry/manifest, tool policies, provider budget configuration, adversarial replay, fallback proof. STOP for leaking tenant data or secrets, tool action bypass, ignored user preferences, unbounded model usage, model-invented answers, or unavailable manual fallback.
