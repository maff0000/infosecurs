# M010E PID — Entitlement Expansion and Customer Assurance Guide Integration

**Priority:** After M010A–C; integrate only with actual merged M009 services. **Objective:** Reuse the same IRENE shell and Tasks domain for higher tiers without widening Foundational privileges or rewriting M009.

## 1. Entitlement contract

Register each IRENE tool, skill and modal feature in a server-owned capability matrix backed by existing `ProductArea`, `has_capability` and route decorators. Current tiers are Paused (0), Foundational (1), Monthly (2), PRO (3), subject to exact existing code. Do not infer eligibility from UI hiding, customer chat wording or model-supplied package tier. Foundational guided core and permitted Tasks remain usable if model adviser disabled. Paused/invalid entitlement fails closed. Down-tier transitions invalidate prior higher-tier tool access immediately; old conversation history containing privileged tenant context is not retrievable under an insufficient tier (review access/retention policy).

## 2. Feature progression

**Foundational:** 6-stage guided structured inputs, checkpoints, shared Tasks, deterministic explanations, review reminders; bounded optional general help if permitted budget/consent.
**Monthly/PRO:** optional broader authorised read/guide services for risk/policy/evidence, remediation and Customer Assurance exceptions. Exact tier allocation remains a product/entitlement matrix that Gunnar must propose from already-seeded ProductAreas and get reconciled in the final campaign evidence; never expose every tool to every user by default. No enterprise/SaaS billing expansion.

## 3. Customer Assurance adapter

M009's 100%-ready Foundations gate and `customer_assurance` entitlement remain the sole admission truth. IRENE can explain why a customer cannot yet upload, show exact authorised Foundations blockers, navigate to the upload page and manage missing work tasks. When user meets readiness+entitlement, IRENE may link to existing secure XLSX/CSV upload and display authorised import status/extraction counts and later bulk-generation status if implemented. A user must review CONFIRM/GAP and exceptions in existing M009 review UI; AI never fabricates supported controls or approves/export-sends on its own.

M009 file uploads still pass M009A/B common malware/content/security gates; never accept a file through a new raw chat attachment bypass. M009B Increment 3/4 quota, liveness/claim and bulk processing contracts are independently governed and not in scope of M010. IRENE task review may produce safe links to M009 source rows and share task status, but the underlying questionnaire draft/answer writer stays M009-owned. If bulk features are not merged, disable related IRENE features and demonstrate truthful fallback; do not infer from README that they exist.

## 4. Product boundary and graceful refusal

If a Foundational-tier member asks "Complete this supplier questionnaire for me", IRENE should explain available Foundations progress and the entitlement-dependent Customer Assurance workflow without leaking restricted data or invoking generation. When Monthly/PRO user requests it, apply both exact entitlement and readiness gate on every tool. Incomplete org is blocked by existing middleware/endpoint even if model tries direct POST. Multi-org user gets current-org-specific state only.

## 5. Tests

Tier matrix for Paused/Foundation/Monthly/PRO, invalid session, revoked user, explicit tier downgrade mid-tool, hidden/direct-link bypass, Foundations 99% versus 100%, CSV/XLSX upload access through existing views, injection through imported questionnaire, two-org import IDs, CONFIRM/GAP review not silently accepted, provider failure with manual M009 still functional. Re-run all affected M009 tests unmodified; no new M009 schema or prompt changes.

## 6. Evidence/STOP

Evidence `docs/evidence/M010E-ASSURANCE-ENTITLEMENTS.md`: actual capability mapping, feature flag mapping, M009 exact version integration inventory, two-tenant and four-tier matrix, availability-disabled cases, regression results. STOP if the model or modal bypasses M009 readiness, changes M009 bulk retry/budget, fabricates assurance evidence or makes a higher-tier capability available at lower tier.
