# M010 — IRENE AI-First Product Architecture (governing)

**Status:** Product Authority direction LOCKED; candidate for docs PR. **Owner:** Central Architecture. **Delivery Controller:** GUNNAR. **Customer adviser:** IRENE. **Target:** Foundations tier first; expandable to higher entitlements. **Delivery:** modular monolith, Django/PostgreSQL, server-rendered UI, existing provider-neutral AI gateway. **Prohibition:** no production deployment or real customer data authorisation granted here.

## 1. Product outcome

INFOSECURS becomes an AI-first adviser-led application, not a collection of forms with an optional chatbot. After authenticated login the existing landing page loads and an accessible large IRENE workspace opens (subject to preference). It already knows the member's permitted tenant context, current stage, approved question sequence and next open work. It leads customers through existing M008 structured answers; understands what tasks remain; produces safe links into the manual application; and explains what work is required and why. The sidebar retains Dashboard, Foundations and **Tasks**; AI Adviser is a central entry, not a corner widget. The manual UI is always a first-class alternative.

**Foundations operating doctrine:** "The application owns the question, permitted answers, recorded truth and deterministic consequences. IRENE owns guidance, progress, navigation and safe task administration." Generate prose for genuine clarification only. Most answer selections must cost zero AI calls.

## 2. Decisions (locked)

| ID | Decision | Consequence |
|---|---|---|
| D01 | Customer-facing name IRENE; GUNNAR remains delivery controller | Avoid conflated log/persona identity; brand clearance before launch |
| D02 | Reuse M008 question/answer architecture | Never introduce second baseline form, answer schema, scoring, or question provenance |
| D03 | Multi-stage Foundations journey, 12 Stage-4 control questions and 18 overall requirements | Stage progress, 12-control reviewed/confirmed pair and 18-item completion are **different** measures |
| D04 | Structured options presented from server-side `offered_options` | Radio for exclusive choices, checkbox only for required independent confirmation; no AI-invented options |
| D05 | Canonical writes through existing services and form validation | UI conversation cannot bypass conditional N/A or tenant/entitlement gates |
| D06 | Shared tenant-scoped Task List plus separate user checkpoint and conversation | Tasks are not chat messages; user-chat privacy is not shared task visibility |
| D07 | Deterministic review engine | Scheduled due/review tasks without LLM, then bounded optional AI explanations |
| D08 | Registered read/write tools, no arbitrary SQL/RAG across tenants | Tool authorization and validation are code, not prompt instructions |
| D09 | Progressive versioned Markdown skills | Skills guide wording and procedures but never confer tool authority |
| D10 | One Gunnar campaign with internal work-package checkpoints; one final acceptance | Implementation may run uninterrupted within scope; no unaudited merge or production release |
| D11 | Higher-tier capabilities are feature-flagged, not improvised | Foundational AI tool access is least privilege; M009B remains separately governed |
| D12 | Assistant failure does not block manual security work | Disable IRENE by flag and retain Task List, current Forms and metrics |

## 3. Module context and dependency direction

```text
Authenticated browser / existing INFOSECURS single shell
  ├─ Existing manual application + canonical domain services (always functional)
  ├─ IRENE modal (Continue | Tasks | Ask | Activity)
  └─ Tasks sidebar page (shared organisation task list)
               ↓                         ↓
  Journey orchestration (deterministic)   Task services (transactional)
               ↓                         ↑
  Existing M008 question catalogue /     Scheduled review rules
  offered_options / StructuredAnswerForm  (no LLM required)
               ↓                         ↑
  record_structured_baseline_answer       Current domain objects/review dates
               ↓
  Canonical BaselineAnswer + selection provenance
               ↓
  Existing risk/policy consequences + entitlements.metrics

  Optional AI Adviser orchestrator → authorised read/tools only →
  curated skill/version + bounded tenant-scoped structured projections →
  existing trinity-fast/core gateway alias → validated advisory response
```

Keep this inside the modular monolith. No separate agent runtime, general workflow engine, vector store, message bus or microservice required for the initial release. A scheduled Django command running in an existing authorised scheduler suffices; do not assume one exists without preflight verification.

## 4. Actual M008/M007 contracts to reuse

- Control catalogue keys, order and weights: `security_baseline.catalogue` (`CATALOGUE_KEYS`, `CATALOGUE_VERSION`). There are **12** controls, not 18 questions.
- Structured option identity and mapping: `security_baseline.structured_catalogue.STRUCTURED_OPTIONS`, `FOUNDATIONS_QUESTION_METHODOLOGY_VERSION` and `resolve_option`.
- Server-side offer gating: `security_baseline.stage4.offered_options(control_key, organisation)`; it constrains option lists based on confirmed profile facts. Do not calculate this independently.
- Copy: `security_baseline.stage4.QUESTION_COPY`, `explainer_for`, `stage4_progress`, `progress_copy`. Stable answer codes are identity; text may change under versioned methodology.
- UI validation: `security_baseline.forms.StructuredAnswerForm` with server-side allowed options; a real checkbox applies to JML not-applicable confirmation.
- Write: `security_baseline.services.record_structured_baseline_answer` through a tenant-, entitlement- and option-validated adaptor. Existing routes `security_baseline:foundations_start` and `security_baseline:foundations_question` remain valid navigation fallbacks.
- Organisation-level completion: `entitlements.metrics.get_security_foundations_completion` using 18 `FoundationRequirement` items; posture/Needs Attention remain independently derived from existing services. NEVER compute a second 18-item completion figure.
- Stages 1–3 read/write existing structured profile/workplace/governance/domain forms; Stage 4 uses 12 control questions; Stage 5 shows derived risks/actions; Stage 6 policy preview/review/approval. Validate stage availability against current implementation, not merely an old proposed M008C design document.
- Customer Assurance M009/M005 is a downstream capability, not a baseline answer editor or an AI shortcut around 100% readiness. M010E is an integration adapter only after M009's governed services are available.

## 5. User and organisation semantics

The authenticated user may belong to multiple organisations; context is always server-established, revalidated at **every** API/tool action. A global shared `SecurityTask` belongs to exactly one organisation and is visible to members permitted for Tasks. A checkpoint is scoped to **organisation + user + journey**. Conversation messages are user-private by default within a tenant; only structured, explicitly promoted task descriptions become shared. Membership removal or entitlements downgrade revokes further data access including old conversation retrieval. The assistant must never infer access from previous chat history or a model-supplied organisation ID.

## 6. Advice versus truth versus action

IRENE may read permitted state and present the next deterministic step. The user may ask questions, skip, stop, resume or switch to the manual screen. An `UNKNOWN` answer remains UNKNOWN; offer a confirmation task without forcing confidence. PARTIAL and NO may generate deterministic suggested remediation tasks; neither may assert a resolved control. `NOT_APPLICABLE` is offered only where the existing M008 application permits it (JML confirmation + access-count restriction; remote-access confirmed profile condition). A task marked `done` is **not** proof that a risk is accepted, a policy approved, a control implemented or an evidence item current. Only canonical domain services can change those states.

Read-only advisory text is clearly distinguished from verified fact. AI may propose a task or draft but cannot directly approve control state, certify an organisation, approve policy, accept risk, send customer assurance replies or change entitlements. Significant actions require a user-visible confirmation and independent server-side capability check.

## 7. Task engine as first-class shared operational state

One `SecurityTask` ledger with explicit scope, source identity, source object, assignment, due date, status, priority, dependencies, completion condition, activity events and deduplication. Human-origin tasks and deterministic rule-origin tasks share the ledger. The customer receives a Tasks sidebar page grouped by Foundations, Risks & Remediation, Policies, Evidence & Assurance, and Other; group codes are versioned and policy-controlled. Counts, overdue status and dependencies derive from DB. The adviser retrieves tasks from this exact ledger, not a chatbot-only list. Full state machine: M010 data contract.

## 8. Presentation and availability

A first-login modal opens over the real Home after login; the user may close/minimise to the manual application. Respect user preference and do not reopen after dismissal repeatedly. Tablet/mobile layout is accessible; native modal focus management, Escape, keyboard, labelled controls and reduced motion. Tabs: **Continue, Tasks, Ask, Activity**. Continue is default, never a blank general-purpose model prompt. Persist a journey checkpoint after validated state transition; never pretend a message was saved before the service confirms.

If provider unavailable or quotas exhausted, deterministic questions, status, task CRUD, notifications and manual routes continue normally; only optional free-form clarification is unavailable. Do not make the Task List depend on a model call.

## 9. Subscription model

Reconcile capabilities to existing `ProductArea`/tier gating (Paused=0, Foundational=1, Monthly=2, PRO=3 subject to current code), never hard-code the marketing names as authorization. Foundational: structured guided onboarding, safe task management, bounded explanatory help. Higher tiers may unlock broader adviser/domain tools, evidence analysis and Customer Assurance coordination **only** through separately mapped capability permissions. No automatic promotion or unrestricted provider usage.

## 10. Non-goals and constraints

Not in initial campaign: full autonomous cyber operations, broad document ingestion/RAG, independent AI policy approval, direct email sends, client-wide global search, marketplace/plugins, Slack, continuous agent background cognition, voice, multi-agent swarms, external enterprise integrations, native mobile app, general workflow-builder, M009 bulk orchestration rewrite. Do not "solve" these while implementing M010.

## 11. Success measures and rollout

Measure: stage completion time and abandonment; UNKNOWN follow-up resolution; no duplicate task emission; timely risk/policy reviews; decrease in unanswered assurance questions; safe-advice utility; AI calls/tokens and failure fallback; response latency; accessibility; zero cross-tenant leaks. Capture outcome events without leaking security-sensitive answer prose into logs.

Use feature flags and a single tenant-safe rollout toggle; Customer Zero first in disposable DEV. User-requested one campaign ends in one integrated PR, fresh full audit, architecture exact-SHA acceptance, then separate release/production authorisation. Rollback is feature-flag disable + immutable schema-safe artifact; no deletion of customer tasks as rollback mechanism.

## 12. Governing quality gates

Critical STOP conditions: cross-tenant or entitlement bypass; unsupported security fact; bypass of M008 validation; secret exposure; uncontrolled tool execution; arbitrary SQL/network read; public/real data without authority; loss/corruption of canonical answer; double-creation of same scheduled occurrence; high-risk write without human approval. Work-package CI is continuous and local; full independent product/security audit occurs at the end per one-push doctrine. See M010F and campaign Work Order.
