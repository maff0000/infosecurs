# M010 — IRENE Security, Privacy and Threat Model

**Status:** Governing for every M010 endpoint, model tool, task, scheduler and modal. **Risk acceptance:** No critical/high isolation defects permitted. **References:** `PID.md` §§9–10.1; existing `entitlements` and `organisations` contracts; OWASP GenAI Security Project (https://genai.owasp.org/llm-top-10/); NIST AI RMF (https://www.nist.gov/itl/ai-risk-management-framework); UK ICO AI guidance (https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/).

## 1. Trust boundaries

1. Anonymous browser → authenticated Django session and CSRF barrier.
2. Authenticated user → validated active organisation and membership, current entitlements, role/object permissions.
3. Browser-selected answer → **fresh** current `offered_options` + `StructuredAnswerForm` + canonical domain service.
4. Browser/task action → server-owned `organisation_id`, object access predicate, source allowlist, atomic Task Service.
5. Organisation-scoped database projection → AI provider. Tenant filter applies before projection and after any tool dispatch; the provider response has **zero** grant authority.
6. Uploaded evidence/questionnaires/customer prose → UNTRUSTED DATA. Never interpreted as developer/system instructions and never given tools/privileges.
7. Scheduler execution → tenant-by-tenant, constrained service principal with rules and object selectors; cannot iterate global data into one AI prompt.
8. AI model output → strict schema/content validator → only registered tools → fresh authorisation + user confirmation for guarded writes.

## 2. Policy decision and enforcement points

- Derive session context using the existing `entitlements.session` validators. Verify `get_member_organisation_or_404` on every organisation-scoped route and the existing `require_capability`/`has_capability` contract for every appropriate capability. Never trust organisation, tier, role or user ID supplied by a model or request JSON.
- Model tools use a server-created `AuthorizedContext(user_id, organisation_id, role, capability_snapshot, request_id)` but **recheck actual live membership/entitlements at invocation**; snapshot is not a permanent grant. Role-specific object scope (task assignment, private conversation) is checked again.
- No generic `execute_query`, `get_object`, `fetch_url`, arbitrary file-path reader, Django ORM interpreter, unconstrained SQL or dynamic Python tool. A product-knowledge registry is an allowlist of domain-specific service calls and registered route names, not a database schema dumped into the model.
- Cap tool requests: schema validation; bounded string, list and object sizes; pagination; execution/response budgets; approved enum arguments; no arbitrary filters; signed/allowlisted action registration. Tool outputs must be escaped as data in prompts and HTML.
- Writes use the exact same domain service path as manual UIs. All tools log decision/outcome with actor, organisation, source record, policy version and redacted trace ID, not raw prompt or secret.

## 3. Concrete attacks and expected denial

| Attack | Mandatory defence | Negative test |
|---|---|---|
| User in tenant A asks for B's task ID, conversation UUID, risk or questionnaire | Per-object organisation+membership and role check; generic 404 | A cannot infer existence, data, totals or timings of B |
| Model supplies B's `organisation_id` in tool JSON | Ignore/reject model-supplied identity; server uses active verified tenant | Request rejected; B never queried |
| Member removed mid-conversation | Recheck membership each message/tool call | Existing conversation becomes inaccessible, no stale-cache leakage |
| Role/tier downgraded mid-session | Recheck capability on read/write | No stale token grants higher-tier tools |
| User changes profile between offered options and submission | Server re-evaluates offered options on POST | Forged/stale option rejected, no answer mutation |
| Customer selects JML N/A without required confirmation | Existing StructuredAnswerForm validation | No write; honest error displayed |
| Questionnaire attachment orders model to leak or mark MFA implemented | Untrusted content; structured state projection only; no truth-write tool | No exfiltration or control upgrade |
| AI invents policy approval or security certificate | No approval tool; application-controlled review, evidence and outcome | Advice remains draft/unsupported |
| Other tenant task title leaks through task summary/cache | Tenant-keyed cache or avoid caching; no global semantic index | Mixed-tenant corpus zero crossover |
| Agent loops calling tools or gateway | Max calls, timeouts, daily org/provider allowance, circuit-breaker | Bounded cost, deterministic fallback |
| Assistant writes another user's task/private chat | Role/user scoping + authorisation | 403/404 and no state change |
| JS/HTML in task description, model output or document | Template escaping, CSP, no `mark_safe` for model output | Browser XSS payload inert |
| Scheduler duplicated run / DST boundary / midnight | DB idempotency unique key, UTC occurrences and explicit timezone | Exactly one task and audit event |
| Task's source row deleted/changed | Safe stale-source representation, no orphan cross-tenant reference | No 500, task cannot certify completion |
| Malicious skill file or poison edit | Git-review-only trust, hash/version pin, no customer-authored skill instructions | No new tool permissions or leaked secrets |

## 4. Conversation and data handling

- Maintain `AssistantConversation` and `AssistantMessage` in PostgreSQL with strict organisation+user policy. Default visibility private to originating user; support authorised, explicit task promotion only. Design retention/deletion, privacy notice, processor terms and lawful basis before real-customer enablement; durations **must be decided**, not invented by the Implementer.
- Log minimal structured metadata (intent code, skill ID/version, tool name, execution result category, latency, request ID), not verbatim security-sensitive company context. Establish explicit opt-in/consent and data-minimisation for provider calls where applicable under policy. Never place customer prompts in exception traces or ordinary system logs.
- Sensitive fields (secrets/passwords, tokens, API keys, contact personal data, raw uploaded documents, privileged implementation configurations) are excluded from default AI projection. Mask and minimise permitted values. Never use `docker inspect ... Env` or print environment dumps; credential exposure during prior delivery illustrates the threat.
- External model gateway uses existing `trinity-fast` / `trinity-core` aliases; no hardcoded model names. Enforce TLS, server-side credentials, bounded timeout, maximum context/output and organisation-level cost quota. Provider data handling and geographic processing must be verified for production; do not assume no retention.
- No background LLM ingestion of every record. Scheduled review is deterministic, tenant-by-tenant, using only required fields. In-app notices default; no email delivery until separately authorised with preferences/opt-outs.

## 5. Secure UI and agent action classes

**Class R (read/navigation):** authenticated, capability/object-scoped; may run without extra user confirmation. **Class T (task administration):** create/update permitted tasks under service and idempotency; proposed changes shown for user confirmation unless pre-authorised deterministic scheduler source. **Class D (draft/propose):** generate a suggestion but do not alter canonical security facts. **Class H (high consequence):** approval, risk acceptance, control attestation, external communication, deletion, entitlement change—NO M010 model tool; route to existing manual human-controlled workflow if authorised. A user prompt saying "I approve" cannot replace the application's separate approval mechanism.

## 6. Required adversarial programme

Use two seeded organisations A/B with distinctive secret canaries in every relevant model type, plus two users with differing role/tier and a revoked member. Attack via chat, tool input, direct HTTP, manipulated URL, forged `option_code`, task dependency, conversation ID, notifications, skill loading and scheduler. Verify response, SQL queries (where test harness can inspect), logs, provider payloads, cache, activity events and task writes reveal **zero** B data to A. Inject hostile instructions into user prose, task descriptions, questionnaires and any allowed evidence excerpts. Verify no tool privilege escalation, XSS or security-truth promotion. Test partial execution and failure injection on every write.

## 7. External risk baseline and launch gate

Track OWASP prompt injection, sensitive-data disclosure, excessive agency, vector/embedding weaknesses, improper output handling, misinformation, unbounded consumption and supply-chain risks. Maintain NIST AI RMF governance/test evidence; no claim of formal certification. GDPR DPIA screening, privacy notices, retention controls, vendor data agreements and actual response-to-data-subject requests must be resolved at real customer launch; this pack does not make a legal compliance assertion.

## 8. Irrevocable STOPs

Any cross-tenant leak (including count/timing inference), protected action invoked without independent server grant, secret printed to tools/logs, prompt-content instruction overriding app policy, unexpected destructive mutation, disabled canonical form validations, unbounded model-call loop, unrecoverable loss of work, or invented control assertions triggers immediate STOP. Gunnar must preserve evidence and escalate; the one-push cadence never waives this.
