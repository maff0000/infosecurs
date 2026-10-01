# M008B — Structured Security Foundations Question Methodology and Canonical Answer Bridge

**Parent:** M008. **Status:** DESIGN / Product Authority review required before code that changes question semantics.  
**Accepted baseline:** `security_baseline.catalogue.CATALOGUE_VERSION=2026-09-baseline-v1` with 12 stable control keys; `BaselineAnswer.answer` is one of YES/PARTIAL/NO/UNKNOWN/NOT_APPLICABLE; `BaselineAnswer.note` is a customer narrative field to retire from Foundation-facing UI; `entitlements.metrics` computes 12 weighted controls and the 18-item completion catalogue from canonical state. `OrganisationProfile` already has useful typed enums. M008B must not create a competing canonical score/fact store.

## B1. Goal

Ask a small-business owner *what actually happens in their business* using specific prewritten options, not ambiguous Yes/No forms or optional note boxes. Map each confirmed option to a canonical existing fact and one of the five real control states, **without interpreting customer prose or calling AI**. Ask follow-ups only when needed to distinguish materially different states, e.g. backups exist **and** restores have been tested.

## B2. Hard requirements for each catalogue entry

For every question define: stable namespaced `question_code`, parent existing canonical `control_key` or typed profile target, immutable `catalogue_version`, plain-English prompt, one-sentence why-it-matters/help, a finite ordered set of `{option_code,label,meaning,derived_state}`, applicability condition, conditional follow-up graph, evidence-needed flag or separate optional evidence-link action, dependencies, `unknown` fallback, default, source/provenance and revision/migration policy. Submit names, labels and mappings for Product Authority acceptance. A display label alone has no state authority; the server validates codes and **owns** meaning.

### Illustrative first-pass control choices (proposals, NOT yet accepted catalogue wording)

The left/right columns are meant to avoid a generic Yes/No. Every item ALSO provides **`not_sure`→UNKNOWN**; `not_applicable` is shown only if a separately governed, factually verified condition permits it, never as an easy escape.

| Stable existing key | Proposed meaningful choices → existing baseline state | Critical interpretation |
|---|---|---|
| `mfa_user_accounts` | All ordinary accounts protected→YES; some protected→PARTIAL; none→NO | Admin-only MFA does **not** imply every staff account protected. Ask platform only when needed. |
| `mfa_privileged_accounts` | All privileged accounts→YES; some→PARTIAL; none→NO | Not knowing who holds privileged accounts is UNKNOWN, not N/A. |
| `endpoint_protection` | All in-use work devices protected→YES; some→PARTIAL; none→NO | Company-managed vs BYOD should condition language, never fabricate vendor/EDR. |
| `patching` | All relevant devices/software updated routinely→YES; inconsistent/some→PARTIAL; no established update practice→NO | Automatic updates alone do not prove full patch coverage. Include follow-up for scope if needed. |
| `device_encryption` | All business-data devices encrypted→YES; some→PARTIAL; none→NO | N/A requires genuine absence of relevant devices/storage, not assumption from cloud-only claim. |
| `backups` | Important data backed up **and a restore tested**→YES; backup exists but restores untested/partial coverage→PARTIAL; none→NO | Central policy invariant: having backups does not prove restore capability. |
| `joiner_mover_leaver` | Defined and followed access removal process→YES; informal/inconsistent→PARTIAL; none→NO | Distinguish promptness and role changes without subjective AI inference. |
| `privileged_access_separation` | Dedicated limited admin accounts→YES; some separation→PARTIAL; day-to-day/admin shared broadly→NO | Do not conflate MFA with separate privileged identities. |
| `security_awareness_training` | Recurring awareness activity provided to staff→YES; occasional/informal→PARTIAL; none→NO | No certification or LMS claim implied. |
| `incident_reporting_route` | Staff know a clear route and person responsible→YES; informal/inconsistent awareness→PARTIAL; no route→NO | A future *policy promise* never flips this to YES. |
| `email_phishing_protection` | Active spam/phishing protections on all business email→YES; some/basic or partial coverage→PARTIAL; none→NO | A platform name alone (e.g. Microsoft 365) is not proof of enabled protection. |
| `remote_access_control` | Governed remote access for all applicable work→YES; some unmanaged paths→PARTIAL; none→NO | Explicit remote-work inapplicability must be supported by current workplace/profile facts; cloud access may still be remote. |

These are **hypotheses to be challenged** in the review; phrases like `all`, `some`, `routinely`, and `clear` require measurable in-product examples and/or a limited diagnostic follow-up. Do not code this table straight into product without Product Authority approval; report ambiguities instead. Keep the existing `CATALOGUE_BY_KEY` keys stable.

## B3. Non-control structured inputs (full Foundations route coverage)

- **Business:** legal name as bounded identifier, staff headcount as number/range, sector from finite choices (requires method-approved vocabulary), customer/security motivation from a choice list, Microsoft 365 / Google Workspace / Other / Not sure selection, cloud and data-category yes/no/unknown. If `other` is selected, store `other_unclassified`/controlled choice and offer human follow-up later; **do not reveal a narrative box**.
- **People/governance:** choose responsibility from existing member/person roles; short names/emails only if identity necessary; roles are selected, not customer prose. Existing Account Holder bootstrap retained.
- **Workplace:** office/remote/hybrid patterns and counts as typed numbers; short workplace identifiers permitted, not descriptive essays; existing `sync_working_model` remains sole derivation authority.
- **Assets:** curated asset categories/examples from existing key-asset catalogue, tick/select known types, optional bounded asset label, business criticality choices; unrecognised asset marked for later specialist review without coercing false classification.
- **Risk:** preserve confirmed/draft/dismissed lifecycle; use the governed existing risk scenario catalogue and selectable owner/priority/treatment options, not user-authored threat/vulnerability prose; AI can still propose risks via existing controlled service but user selects/confirm/dismisses structured proposals.
- **Evidence:** file upload (separate real-file type, not prose), controlled kind/control/relationship, clear evidence sufficiency status, optional date; safe filename is a file attribute not a narrative input. Do not infer content-based evidence truth from a filename.
- **Remediation:** curated actions tied to a specific control/scenario with managed state, owner/target date; unknown/unmapped issue is an exception for a later practitioner, not an open-ended form.
- **Policy review:** structured accept/flag/approve controls; no Foundation-facing section textarea. Customer Assurance question input and review-answer editing remain in distinct MONTHLY+ workflow, unaffected by this specific restriction.

## B4. Persistence contract

1. **No extra editable scores/answer stores.** For baseline: use a **single service write** that accepts `(organisation, control_key, selected_option_code, version, actor[, followup])`, validates membership/entitlements/applicability, and maps to the real `BaselineAnswer.answer`. If extra detail must survive, a narrowly scoped, per-control `AnswerSelectionDetail` (or similarly named) can record the selected option/follow-up codes, catalogue version, provenance and confirmed actor; it is **not independently editable truth** and cannot disagree with canonical `BaselineAnswer.answer`. Schema requires unique scoped key, tenant constraints and transactional update. Do not keep two answer-save paths that drift (`security_baseline.views` and asset-specific protection page share `save_baseline_answers` today—route both through the same validated logic).
2. For existing typed Profile, Workplaces, Governance, Assets etc, map options **into the existing correct model/field**. Add only the smallest genuinely needed typed fields for approved options; no generic `answers_json` data lake. Record which field owns each question. Unknown answers must be first-class, not blank vs false confusion.
3. **Conditional relevance:** use approved canonical facts and stable question dependencies; changing an upstream fact invalidates or marks dependent selections for reconfirmation rather than retaining an impossible previous YES. All validation server-side; forged disabled/hidden option codes, foreign control keys or bypassed ordering are rejected. Circular dependency detection and a deterministic stable topological ordering are mandatory.
4. Version answer meaning explicitly. If wording only clarifies text, unchanged semantic code can remain; if option meaning changes, bump structured catalogue version and make an explicit coexist/retire/migrate decision. Do not change M007 `FOUNDATION_METRIC_VERSION` or M002 `CATALOGUE_VERSION` casually; if new applicability changes what a baseline answer *means*, STOP for methodology ruling. Historical selections remain decipherable.
5. Save on deliberate Next/Save (or an explicit single choice submission) transactionally; back/forward reload shows persisted choice; repeated submissions idempotent. No speculative auto-approval or free-text side-channel in POST.

## B5. Explainability, cost and safety

Users see a short readable implication after selecting, e.g. “MFA protects administrator accounts, but ordinary staff accounts are not all covered”; it must derive from confirmed selections, not LLM-generated narrative. “Not sure” remains available and clearly identifies follow-up rather than penalising the user's honesty. Show gaps as gaps and schedule suggested actions without promoting security posture until control genuinely changes. Foundation completion should increment on deliberate known answers, including NO, PARTIAL and valid N/A, but **not** UNKNOWN. No normal structured questions invoke AI; instrument counter and assert zero model calls across the whole wizard.

## B6. Product Authority design checkpoint package

Before implementation create `docs/evidence/M008B-QUESTION-CATALOGUE-REVIEW.md` with: full catalogue tables; every actual FOUNDATION-visible field/form/URL and proposed replacement; selected option-state mapping; 12 control answered examples (remote, office, all UNKNOWN); dependency graph; explicit semantic assumptions and debated answer meanings; version/migration proposal; exception register of unavoidable identifiers. Provide Matt a human-readable 20–30-minute walkthrough in browser/HTML and highlight choices needing his judgement. **STOP.** No destructive alteration of the accepted baseline catalogue before acceptance.

## B7. Engineering / audit acceptance

All 12 controls show bounded specific options and appropriate dependent followups; every answer maps server-side to exactly the approved state; `UNKNOWN!=NO`, `PARTIAL!=YES`, N/A gated, no all-staff assertion from admin-only MFA, backups without tested restores not YES. Profile and ancillary routes contain no reachable discretionary narrative entry for FOUNDATION tier. Forged POST, stale choice, reordered step, cross-tenant refs, double submit, back/forward all held; M007 metrics exactly preserved for equivalent canonical states. Questionnaire and existing AI evaluations unaffected; normal question session no inference calls. Auditor compares actual saved rows and outbound AI grounding, not just UI labels.
