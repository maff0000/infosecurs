# M003 — Evidence & Security State

**Status:** AUTHORISED FOR BUILD  
**Parent:** `/PID.md`  
**Depends on:** M002 PRODUCT_GREEN  
**Authoritative baseline main SHA at authorisation:** `775dad84d32dc28350d0193de62a7be319a60401`  
**Presentation target:** `PRODUCT_USABLE`  
**Required delivery framework:** FORGE  
**Project root:** `/srv/infosecurs`  
**Development host:** `dell-debian`  
**Project truth:** GitHub

## 1. Purpose

M003 turns Infosecurs from a self-assessment/risk tool into an evidence-backed security-state system.

It must let a small organisation answer:

1. What security state have we said is true?
2. What evidence do we have for that state?
3. Where is evidence missing, stale, contradictory or withdrawn?
4. What actions are open to improve the state?
5. What changed, who changed it, and when?

M003 is the foundation M004 Policy and M005 Questionnaire Assurance will later rely upon.

It is not a generic document-management system and it is not a full GRC platform.

## 2. Core architecture invariant — one security truth

> **Do not create a second editable security-control truth store.**

The canonical customer-stated control fact already exists in M002:

`security_baseline.BaselineAnswer`

That remains authoritative for the organisation's current self-assessed answer to a baseline control.

M003 must not create another table containing an independently editable answer for the same control.

Instead:

```text
BaselineAnswer
    +
linked evidence
    +
evidence provenance/lifecycle
    +
history
    =
Current Security State projection
```

The projection is deterministic application logic.

Evidence may support, contradict or provide context for an answer. Evidence does not silently change the answer itself.

## 3. Truth / evidence semantics

### 3.1 Customer-stated fact

A `BaselineAnswer` is a customer-confirmed statement such as:

`MFA for ordinary users = yes`

That means the customer says it is true. It does not mean Infosecurs independently verified it.

### 3.2 Evidence

Evidence is an artefact or reference relevant to the stated security fact.

Examples:
- screenshot showing an MFA policy;
- PDF configuration/export/report;
- screenshot showing BitLocker/FileVault state;
- external reference to a system/report;
- evidence that contradicts a stated answer.

Evidence is not automatically proof merely because it exists.

### 3.3 Current Security State

The product derives a user-facing state from:
- canonical control answer;
- evidence links;
- evidence lifecycle/freshness;
- contradictions.

Permitted M003 V1 assurance labels:

```text
Not confirmed
Not applicable
Customer stated
Supporting evidence attached
Evidence conflict
Evidence stale
```

Do not use:

```text
Verified
Certified
Compliant
Audited
```

unless a later module has a real basis for those words.

## 4. User outcome

A Customer Zero user can:

1. open an organisation's Security State page;
2. see every baseline control and its canonical current answer;
3. see whether evidence is attached;
4. open a control and inspect linked evidence;
5. upload a small evidence file or add an external evidence reference;
6. link one evidence item to one or more controls;
7. state whether a link supports, contradicts or contextualises the answer;
8. see the assurance label update deterministically;
9. mark evidence superseded or withdrawn without deleting the historical record;
10. create a remediation action directly from a risk or control gap;
11. update the action through a deliberately small lifecycle;
12. attach completion evidence to an action;
13. inspect a readable security/evidence activity timeline;
14. return later and see the same state, evidence, actions and history.

## 5. Non-goals

M003 does not build:
- AI document parsing;
- OCR;
- semantic document search;
- embeddings/vector database;
- questionnaire ingestion;
- policy generation;
- automatic certification;
- automatic evidence verification;
- active vulnerability scanning;
- cloud/M365/Huntress/uSecure evidence collectors;
- scheduled evidence collection;
- Redis/Celery/background workers;
- general-purpose workflow engine;
- arbitrary office-document processing;
- public evidence sharing;
- external customer production identity;
- full records-management/retention product;
- ISO 27001 control library;
- proprietary numeric maturity scoring.

Do not pre-build M004–M006.

## 6. Domain model

Create a bounded `assurance` / `evidence` domain. Exact Django app naming is an implementation decision; semantics are not.

### 6.1 EvidenceItem

Tenant-owned.

Minimum fields:
- stable UUID;
- organisation;
- evidence kind;
- title;
- short description;
- source/origin label;
- observed/captured date where known;
- optional valid-until/expiry date;
- lifecycle status;
- recorded/uploaded actor;
- created/updated timestamps.

Evidence kinds:

```text
file
external_reference
```

Do not create a separate customer-attestation evidence kind merely to duplicate `BaselineAnswer`.

Lifecycle:

```text
active
superseded
withdrawn
```

Evidence content is never silently replaced. A replacement is a new `EvidenceItem`; the old item is retained historically and may reference its replacement.

### 6.2 File evidence metadata

For file evidence record at minimum:
- original safe display filename;
- opaque stored filename/path;
- detected file type;
- byte size;
- SHA-256;
- upload timestamp.

Bytes and SHA-256 are immutable after creation.

### 6.3 External reference evidence

For external-reference evidence:
- reference/URL;
- source label;
- observed date where known.

M003 does not fetch or crawl the URL.

### 6.4 ControlEvidenceLink

Explicit tenant-owned association:

`EvidenceItem -> canonical BaselineAnswer/control key`

Relationship:

```text
supports
contradicts
context
```

Minimum metadata:
- organisation;
- evidence;
- baseline/control target;
- relationship;
- short optional rationale;
- linked_by;
- linked_at.

One evidence item may link to multiple controls and one control may have multiple evidence items.

The link operation must verify all referenced objects belong to the same organisation.

### 6.5 RemediationAction

Tenant-owned, deliberately small.

Minimum fields:
- stable UUID;
- organisation;
- title;
- description;
- status;
- priority;
- optional related Risk;
- optional canonical control key / BaselineAnswer;
- optional related KeyAsset;
- created_by;
- optional assigned_to;
- optional target date;
- completed_by/completed_at where applicable;
- created/updated timestamps.

Status:

```text
open
in_progress
done
accepted
```

`accepted` means the organisation consciously accepts the issue/risk for now; it does not mean the underlying control requirement is met.

Priority:

```text
low
medium
high
critical
```

Do not build a configurable workflow engine.

### 6.6 ActionEvidenceLink

Allow evidence to be associated with a remediation action, especially completion evidence.

This association does not automatically mark the action done and does not automatically change a baseline answer.

## 7. Current Security State projection

Create a deterministic service/view model over existing canonical `BaselineAnswer`.

For each control return at minimum:
- control key;
- catalogue label/question;
- canonical answer;
- answer updated_at;
- evidence counts by relationship/lifecycle;
- active supporting evidence;
- active contradictory evidence;
- stale evidence;
- open remediation count;
- derived assurance label.

### 7.1 Derived label rules

No answer / `unknown`:

`Not confirmed`

Supporting evidence may be visible, but the answer remains unconfirmed until the customer changes the canonical answer.

Evidence must never silently turn `unknown` into `yes`.

`not_applicable`:

`Not applicable`

Evidence may be attached as context.

`yes`, `partial`, or `no` with no active evidence:

`Customer stated`

Active contradictory evidence:

`Evidence conflict`

This outranks supporting/stale labels.

Only stale/superseded supporting evidence:

`Evidence stale`

Active supporting evidence and no active contradiction:

`Supporting evidence attached`

This does not mean verified.

The implementation may refine exact precedence if necessary but must preserve these semantics and document the deterministic order.

## 8. Evidence freshness

Evidence may optionally have `valid_until`.

If it is in the past, the item is stale for current-state projection.

Do not automatically delete, withdraw or supersede stale evidence.

If no `valid_until` is supplied, do not invent one.

## 9. Private file evidence — Beta boundary

M003 V1 supports a deliberately small private upload capability.

Accepted types:

```text
PDF
PNG
JPEG
plain text
```

Do not accept DOCX/XLSX/ZIP or arbitrary file types in M003.

Default maximum size:

`10 MiB per file`

Do not trust browser MIME, extension or filename. Validate file signature/content sufficiently for these four supported classes. Reject mismatches.

Store file evidence privately in a persistent Docker-mounted path external to the immutable application image. Do not serve it from a public static/media directory.

Example container path:

`/data/evidence`

Evidence files may only be downloaded through an authenticated, tenant-scoped endpoint with:
- organisation membership checked in the lookup path;
- no user-supplied filesystem path;
- opaque stored names;
- safe `Content-Disposition: attachment`;
- `X-Content-Type-Options: nosniff`;
- safely encoded original filename.

M003 does not parse, OCR, execute or send uploaded file contents to AI.

Because Beta remains restricted to synthetic / Customer-Zero-safe data, M003 need not introduce malware-scanning infrastructure solely for this bounded repository. Reconsider malware controls explicitly before arbitrary real-customer uploads are authorised.

## 10. Evidence integrity

For every uploaded file:
- calculate SHA-256 while ingesting/streaming;
- persist size and detected type;
- use an opaque server-generated storage identifier;
- never derive storage path from original filename;
- never overwrite existing evidence bytes in place.

SHA-256 is an integrity identifier, not proof the evidence is true.

Never reveal cross-tenant duplicate/hash information.

## 11. Provenance

Every evidence item must make its origin understandable.

At minimum show:
- who recorded/uploaded it;
- when Infosecurs received it;
- source/origin label;
- observed/captured date if supplied;
- file hash/type/size for files;
- lifecycle status;
- what controls/actions it is linked to.

Do not generate provenance using AI.

## 12. Security-state history / timeline

M003 must provide an append-only tenant-owned activity trail for assurance/evidence events such as:

```text
control_answer_changed
evidence_created
evidence_linked
evidence_unlinked
evidence_superseded
evidence_withdrawn
action_created
action_status_changed
action_evidence_linked
```

Minimum:
- organisation;
- event type;
- actor;
- occurred_at;
- relevant stable object/control identifiers;
- small structured metadata.

Update the existing shared baseline save path so a genuine canonical answer change emits `control_answer_changed`.

Record:
- control key;
- previous answer;
- new answer;
- whether note changed.

Do not duplicate the free-text note into the event log.

No event is required if nothing changed.

The timeline is history, not a second source of current truth.

## 13. Remediation from M002 risks

A user must be able to turn an M002 Risk's proposed treatment into a real remediation action.

Suggested interaction:

```text
Risk
  ↓
Create action
  ↓
pre-filled title/description from proposed treatment
  ↓
user reviews/edits
  ↓
Open action
```

Creation is explicit; do not automatically create actions for every risk.

Completing an action does not automatically:
- mark the linked risk resolved;
- change a BaselineAnswer;
- claim the control is implemented.

The user may attach evidence and separately update the canonical control answer when appropriate.

## 14. Relationship to M002

Do not rewrite M002 risk derivation.

M003 may display control keys/assets/assumptions already associated with a Risk.

Evidence and actions can link to those same canonical controls/assets.

Do not make uploaded evidence retroactively alter historic risk derivation.

## 15. No new AI requirement

M003 V1 requires no new AI feature.

Do not invoke `trinity-core` to:
- summarise evidence;
- decide whether evidence is valid;
- extract control state from files;
- classify uploads;
- mark actions complete.

No new live-AI evaluation gate is required unless implementation introduces a new AI path with Central Architecture approval.

## 16. Tenant isolation

Automated negative tests must prove organisation A cannot:
- list B's evidence;
- view B's evidence metadata;
- download B's evidence file;
- link B's evidence to A's control;
- link A's evidence to B's control;
- inspect B's security-state projection;
- inspect/mutate B's remediation actions;
- attach B's evidence to A's action;
- see B's timeline events;
- infer another tenant's evidence existence through hash/dedup behaviour.

Cross-tenant evidence-file access is catastrophic.

## 17. Transactions / consistency

State-changing operations and their activity events must be transactionally coherent where practical.

Do not persist an event claiming a state change that rolled back.

## 18. UX

Suggested organisation navigation:

```text
Profile
Security baseline
Assets
Risks
Security state
Evidence
Actions
Activity
```

Refine grouping if needed to avoid clutter.

Security State is the primary M003 page.

Examples:

```text
Multi-factor authentication (staff)
Current answer: Yes
Assurance: Supporting evidence attached
Evidence: 2
Open actions: 0
```

```text
Device encryption
Current answer: Not confirmed
Assurance: Not confirmed
Evidence: 0
Open actions: 1
```

Avoid unnecessary scores and GRC-heavy terminology.

Control detail should show:
- canonical answer;
- note;
- evidence;
- relationship;
- freshness/lifecycle;
- actions;
- relevant activity;
- link to edit the canonical baseline answer.

Do not create a second answer store/form.

Evidence page supports upload/reference/link/unlink/supersede/withdraw. No rich preview required.

Actions stay simple; no Kanban/project-management subsystem.

## 19. Mechanical tests

At minimum:

Evidence:
- file/reference creation;
- lifecycle transitions;
- immutable file content/hash metadata;
- invalid type rejected;
- extension/MIME mismatch rejected;
- size limit enforced;
- safe filename handling;
- private download headers;
- tenant isolation;
- no path traversal;
- withdrawn/superseded retained historically.

Links:
- supports/contradicts/context;
- cross-tenant linking impossible;
- duplicate-link behaviour deterministic;
- one item can support multiple controls;
- unlink does not delete evidence.

Security State:
- unknown remains `Not confirmed`;
- evidence never silently changes canonical answer;
- yes/no/partial with no evidence => `Customer stated`;
- active support => `Supporting evidence attached`;
- contradiction => `Evidence conflict`;
- stale evidence => `Evidence stale`;
- not-applicable distinct;
- precedence deterministic.

History:
- answer changes create event;
- unchanged save creates no false answer-change event;
- evidence/action events append correctly;
- rollback leaves no false event.

Actions:
- explicit create from risk;
- lifecycle transitions;
- completion does not change baseline/risk automatically;
- evidence can attach;
- tenant isolation.

Regression:
- all M001/M002 tests remain GREEN;
- deterministic M002 risk generation unchanged;
- M002 AI interpretation remains suggestion-only.

## 20. Browser acceptance

Fresh Auditor must:

1. start exact audited commit on fresh Docker data;
2. create/login synthetic Customer Zero;
3. create enough profile/baseline/assets for one yes, one no, one unknown, and one M002 risk;
4. open Security State and verify truthful states;
5. upload a valid synthetic PNG/PDF to the yes control;
6. verify `Supporting evidence attached` without verified/compliant wording;
7. download through authenticated endpoint and verify bytes/hash + safe headers;
8. add an external evidence reference;
9. add contradictory evidence and verify `Evidence conflict`;
10. create stale evidence and verify `Evidence stale`;
11. supersede/withdraw evidence and verify history retained but active support removed;
12. create a remediation action from an M002 risk;
13. progress open -> in progress -> done and attach completion evidence;
14. prove BaselineAnswer did not change automatically;
15. explicitly change the canonical answer via the existing shared baseline path and verify Security State updates;
16. verify Activity timeline;
17. exercise cross-tenant IDs for evidence metadata/file download/control link/action/activity and verify blocked;
18. confirm no unexplained console errors.

Establish non-vacuity for private-download and cross-tenant checks.

## 21. Storage / Docker / reproducibility

Continue the locked build-reproducibility doctrine.

Use an explicit persistent evidence volume/path for development.

Do not put uploads in Git or the immutable image.

Any new dependency follows direct pin + complete hash lock + security scan.

Do not add object storage merely because it may be useful later; local private persistent storage is sufficient for Beta unless an observed requirement proves otherwise.

## 22. Security controls for evidence

At minimum:
- authenticated access;
- tenant-scoped lookup;
- CSRF on mutations;
- bounded uploads;
- allowlisted file signatures;
- no executable upload type;
- opaque stored filenames;
- safe content disposition;
- `nosniff`;
- no traversal;
- no direct file URLs;
- server-computed hashes;
- no file content in logs;
- no evidence content sent to AI.

## 23. Audit/event integrity

Do not build blockchain/hash-chain/event-sourcing infrastructure.

Normal transactional PostgreSQL immutable event rows are sufficient for Beta.

Events are not editable from the product UI.

## 24. Existing AuditEvent

Do not perform a broad rewrite of M001's minimal `organisations.AuditEvent` merely to unify it with M003.

The two may coexist for Beta.

## 25. Delivery gates

Existing required checks remain:

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
```

M003 additionally requires:
- fresh FORGE Auditor GREEN;
- real-browser M003 acceptance GREEN.

No new AI eval is required.

If implementation unexpectedly needs a new AI path, stop and raise `PRODUCT_AUTHORITY_GAP`.

## 26. Evidence closure / post-audit delta

Use the existing GitHub evidence contract exactly.

After the final product audit:
- evidence-only deltas may proceed under the evidence-only rule;
- CI-only deltas require affected checks;
- **any product/runtime source-file touch, including comments/docstrings, requires a fresh Auditor before merge.**

No judgment call based on perceived harmlessness.

## 27. Definition of PRODUCT_GREEN

M003 is PRODUCT_GREEN only when:

1. M002 remains PRODUCT_GREEN.
2. `BaselineAnswer` remains the single canonical editable control answer.
3. evidence can be recorded as file or external reference.
4. files are private, bounded, hash-identified and tenant-scoped.
5. evidence links explicitly support/contradict/contextualise canonical controls.
6. evidence never silently changes a baseline answer.
7. Current Security State is deterministic and honestly labelled.
8. `unknown != no` remains true.
9. stale/superseded/withdrawn evidence retains history.
10. remediation actions work through the small defined lifecycle.
11. completing an action never silently changes a control answer or risk.
12. activity history records meaningful changes without becoming a second truth store.
13. cross-tenant evidence/file/link/action/timeline access is negatively tested.
14. all M001/M002 tests remain GREEN.
15. all required GitHub checks are GREEN on the closing head.
16. fresh FORGE Auditor is GREEN on the exact audited product SHA with real-browser evidence.
17. closure obeys the post-audit delta doctrine.
18. merged `main` reproduces the accepted result from a fresh clone.
19. GUNNAR verifies GitHub truth before asking Central Architecture to authorise M004/M005.

Stop after M003 PRODUCT_GREEN. Do not automatically begin M004.
