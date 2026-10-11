# WO-M009A — Secure Questionnaire Artifact Ingestion + XLSX Normalisation/Provenance

**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Exact base SHA:** `93acc86405597641c46b050dd603ab335ebb60d1`
**Status:** ARCHITECT ACCEPTED — AUTHORISED FOR DELIVERY CONTROLLER DISPATCH

## Scope — exactly this, nothing more

Secure ingestion of an uploaded XLSX questionnaire file, deterministic normalisation of its candidate questions with full source-location provenance, and the minimal real customer entry surface needed to prove the feature end to end. This Work Order is **not**:

- bulk AI answer generation (M009B);
- exception-first review (M009C);
- XLSX answer write-back/export (M009D);
- DOCX, PDF, or OCR support (M009D/future);
- assurance packs (M009E).

If implementation work appears to require any of the above, or any change to `QuestionnaireQuestion`/`QuestionnaireResponse`/`questionnaire.grounding`/`questionnaire.outcome`/any AI orchestration module: **STOP and return to the Architect.**

## Non-negotiable boundaries (reproduced from the PID — binding)

- No second questionnaire truth engine. `QuestionnaireQuestion`/`QuestionnaireResponse` schema and logic are untouched by this Work Order.
- No answer generation of any kind — this Work Order extracts and normalises candidate questions only; it never calls `questionnaire.services.generate_questionnaire_response` or any AI orchestration module.
- The originally uploaded workbook is immutable — never modified, never overwritten, retained exactly as uploaded.
- Tenant isolation identical in discipline to `get_member_organisation_or_404` — a non-member or foreign UUID gets 404, never 403, never confirms existence.
- No parser/extractor of any kind may run before the pre-parse security gate accepts the file. The security gate itself may perform only bounded container-level structural inspection — not business/semantic parsing.
- Questionnaire content is DATA. M009A's own application/product paths make **zero AI invocations** — no new AI task, prompt, or invocation record. (The existing, unmodified M005 14-case regression corpus may continue using its own existing, already-governed deterministic fake/testing gateway — that is not a new AI path and is not affected by this rule.)

## Domain placement — frozen (Correction 1)

The M009A models live inside the existing `questionnaire` Django app. **Do not create a new Django app for questionnaire imports.** The conceptual artifact domain remains distinct from `EvidenceItem` (different purpose, different lifecycle — see the PID's M009-5), but it belongs inside the existing questionnaire bounded context, alongside `QuestionnaireQuestion`/`QuestionnaireResponse`.

## Frozen model contracts

### `QuestionnaireImport`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, pk | |
| `organisation` | FK → `Organisation`, **`CASCADE`** | tenant-owned data; deleting the organisation must not be blocked by questionnaire history |
| `uploaded_by` | FK → User, **`SET_NULL`, nullable** | user deletion/deactivation must not destroy the artifact or block identity lifecycle operations |
| `uploaded_at` | `DateTimeField(auto_now_add=True)` | |
| `original_filename` | `CharField` | display only, sanitised for display, never used in any filesystem/parsing decision; **immutable after creation** |
| `stored_filename` | `CharField` | opaque, server-generated `uuid4().hex`, matching `evidence/storage.py`'s own convention; **immutable after creation** |
| `detected_content_type` | `CharField` | from content-sniffing only, never client-supplied; **immutable after creation** |
| `file_format` | `CharField`, choices | `xlsx` is the only value this Work Order's validation accepts; **immutable after creation** |
| `sha256_hash` | `CharField(max_length=64)` | computed streaming, chunk-by-chunk; **immutable after creation** |
| `size_bytes` | `PositiveBigIntegerField` | **immutable after creation** |
| `security_gate_status` | `CharField`, choices: `pending`, `passed`, `rejected`, `failed` | mutable only via the domain service's governed transitions (see "Service-owned state transitions" below) |
| `security_gate_result` | `JSONField` | structured rejection reason(s) / structural inspection summary / scanner provenance (see Final Correction B) — never raw file content |
| `status` | `CharField`, choices: `uploaded`, `security_gate_pending`, `security_gate_rejected`, `security_gate_failed`, `extracting`, `extracted`, `extraction_failed` | this Work Order populates/transitions only these seven; mutable only via governed service transitions |
| `extraction_summary` | `JSONField`, nullable | bounded structured summary — see "Import-level extraction summary" below |
| `supersedes` | self-FK, nullable, **`SET_NULL`** | set when a re-upload is intended to replace a prior import; the prior import and all its questions remain, untouched and inspectable |
| `created_at`/`updated_at` | timestamps | |

**Immutable artifact metadata, binding:** `organisation`, `stored_filename`, `original_filename`, `sha256_hash`, `size_bytes`, `detected_content_type`, `file_format` must be model/service-layer immutable after creation. Security/lifecycle state may advance; the identity of "which bytes were uploaded" may never silently change underneath an existing `QuestionnaireImport`.

### `QuestionnaireImportQuestion`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, pk | |
| `import` | FK → `QuestionnaireImport`, `CASCADE` | |
| `question` | FK → `QuestionnaireQuestion`, nullable, **`SET_NULL`** | set only when `disposition=question` and normalisation succeeds; **the existing M005 model, completely unmodified**. The bridge must not prevent the existing `QuestionnaireQuestion` lifecycle or Customer Zero reset — if the linked M005 question disappears, source artifact/provenance remains intact with `question=NULL` |
| `raw_extracted_text` | `TextField(max_length=32767)` | the literal extracted cell text, always populated regardless of disposition; capped at Excel's own cell maximum (32,767 characters) |
| `source_location` | `JSONField` | the versioned contract below |
| `extraction_order` | `PositiveIntegerField` | preserves original document order |
| `extraction_status` | `CharField`, choices: `pending`, `extracted`, `failed` | |
| `extraction_error` | `TextField`, nullable | |
| `disposition` | `CharField`, choices: `question`, `heading`, `instructional_text`, `excluded_duplicate`, `excluded_ambiguous`, `excluded_other` | **explicit and auditable for every extracted row — never silently dropped** |

### `QuestionnaireExport` — **deferred to M009D, not created by this Work Order**

### Source-location contract — XLSX schema v1 (Correction 10)

```json
{
  "schema_version": 1,
  "format": "xlsx",
  "sheet_name": "<string>",
  "sheet_index": <int>,
  "question_cell": "<e.g. B14>",
  "row": <int>,
  "question_column": "<e.g. B>",
  "answer_cell": "<e.g. C14, or null>"
}
```

`question_cell` replaces the earlier generic `cell` field name so its meaning is unambiguous. `answer_cell` may be `null` where no destination can be safely determined — if null, M009A may still normalise the question, but **M009D must not invent or fuzzy-match an answer destination later; a send-ready round-trip export cannot rely on rediscovering the destination from question text.** Validated against this schema before being persisted; **if a candidate's location cannot be expressed in this exact schema, it fails closed** — `extraction_status=failed` or `disposition=excluded_other`, `raw_extracted_text` still populated, never proceeding as if a valid location existed. `schema_version` exists so a future format (DOCX) adds a new, separately-validated shape rather than overloading this one.

## Import lifecycle — security rejection vs. scanner failure distinguished (Final Correction A)

Deterministic artifact rejection and temporary scanner/backend failure are not the same state and must never be conflated:

```text
uploaded
  → security_gate_pending
      → security_gate_rejected    (terminal for these bytes)
      → security_gate_failed      (retryable)
      → extracting
          → extracted
          → extraction_failed     (retryable)
```

- **`security_gate_rejected`** = deterministic artifact rejection — invalid XLSX, macro content, external relationship, malware detected, hostile package structure, a resource-limit violation. Terminal for those bytes.
- **`security_gate_failed`** = the security decision could not be completed safely because the scanner or another required security component was unavailable or errored. **Retryable.** A scanner result of `UNAVAILABLE` or `ERROR` must therefore: never advance to `passed`; never advance to extraction; place the import in `security_gate_failed`; retain the uploaded bytes privately so the gate can be retried without forcing re-upload. **Do not treat infrastructure failure as evidence that a customer's workbook itself was malicious.** An explicit service operation for retrying the security gate is required (e.g. `retry_security_gate(import_id)`), distinct from re-upload.

## Original-artifact retention — reconciled, binding (Final Correction H)

- For an artifact whose security gate **PASSES**: original bytes are retained; byte identity is immutable; extraction never modifies them; later export (M009D) never overwrites them.
- For an artifact deterministically **REJECTED** by the security gate: audit metadata (hash, size, rejection reason, timestamps) is retained permanently; the hostile/invalid bytes themselves may be deleted per the documented cleanup policy (immediately, or after a short bounded retention window — implementation's choice, documented).
- For an artifact in **`security_gate_failed`**: bytes are retained privately for retry — this is not a rejection and must not be treated as one.

Use this three-way distinction consistently everywhere "immutable original" or "cleanup" is discussed in this Work Order.

## Customer Zero reset reconciliation — mandatory, in scope for this Work Order (Correction 3)

The existing reset system enumerates every direct FK to `Organisation` and deliberately fails closed on model drift. Adding `QuestionnaireImport.organisation` without reconciling the reset manifest **will break the existing Customer Zero reset by design.** This Work Order explicitly authorises the bounded reset reconciliation this new model requires — and only this:

- Update `organisations/reset_service.py` to classify `questionnaire.QuestionnaireImport` as synthetic tenant state deleted by Customer Zero reset.
- Update the reset deletion manifest/evidence documentation accordingly.
- Update reset service tests to cover the new model.
- Delete `QuestionnaireImport` rows before the existing `QuestionnaireQuestion` deletion where ordering requires it; `QuestionnaireImportQuestion` rows disappear through the import's own `CASCADE`.
- **Questionnaire file cleanup**: Customer Zero reset must also remove the target organisation's questionnaire-storage directory after the database transaction, using the same separate-filesystem-resource discipline already used for Evidence. A failure to clean questionnaire bytes must not be silently reported as a completely successful reset.
- **Do not weaken any existing reset authority, typed-RESET confirmation, CSRF, environment gate, or fixture-identity gate.** This is a bounded extension of the existing manifest, not a redesign of the reset mechanism.

## Questionnaire storage — persistent and recoverable (Correction 4)

A new storage root cannot merely exist as an environment variable inside the web container. This Work Order must prove questionnaire source artifacts survive ordinary web-container recreation, mirroring the established private evidence-storage operational pattern:

- persistent storage mount/configuration (not container-ephemeral);
- a private, tenant-scoped directory per organisation;
- opaque filenames (`stored_filename`, as above);
- explicit permissions (mode `0640`, matching evidence storage);
- no static/media public serving path — ever.

Also reconcile the existing backup/restore mechanism and runbook so questionnaire storage is backed up/restored alongside the database and evidence storage. The backup/restore proof may be narrow (one representative import), but **the new artifact class must not be omitted from recovery architecture.** A system that persists questionnaire metadata in PostgreSQL while silently losing the source workbook on container replacement is not acceptable.

## Formula handling — corrected (Correction 5)

**The earlier `read_only=True, data_only=True` instruction was technically wrong and is withdrawn.** With `data_only=True`, `openpyxl` returns the cached result of a formula where one exists, not the formula itself — unsuitable when the requirement is to identify formula cells and never mistake their cached value for literal questionnaire text.

**Binding rule for M009A extraction**: use `read_only=True, data_only=False` (or an architecturally equivalent approach that preserves formula identity). `openpyxl` does not calculate formulas merely because `data_only=False` — formulas are never evaluated either way. Formula cells remain visibly formula cells to application code; they are never evaluated; their cached value is never treated as trustworthy literal questionnaire content; formula-bearing candidate cells are explicitly excluded/fail-classified; their disposition remains auditable. **Do not perform a second `data_only=True` read and substitute cached formula results into extracted questions.** M009D will separately govern formula-injection-safe output.

## Malware scanning — fail-closed (Correction 6)

**Withdrawn**: the earlier allowance for "a stub that logs 'malware scanning not yet integrated'" to mark the security gate PASSED. The scanner abstraction itself remains correct and required; its result must have explicit semantics:

- **CLEAN** — only this result may advance the security gate to `passed`.
- **INFECTED** — reject.
- **UNAVAILABLE** — fail closed; do not parse/extract.
- **ERROR** — fail closed; do not parse/extract.

A deterministic fake scanner is allowed in unit/evaluation tests. A development/runtime "scanner unavailable" implementation may exist to make absence explicit, but **it must BLOCK upload processing, never allow it through.** M009A cannot close GREEN with a runtime file-security gate that claims `passed` while malware scanning is merely a logging stub. If the scanner reports itself unhealthy or unable to give a trustworthy result, that maps to `UNAVAILABLE`/`ERROR` and fails closed via `security_gate_failed` (see "Import lifecycle" above), not to a silent pass.

### Scanner deployment shape — frozen, not an Implementer choice (Final Correction B)

**ClamAV / clamd as an internal Docker Compose service.** Requirements:

- use the official ClamAV container family;
- exact release/version and immutable image digest pinned by implementation — no floating `latest`/`stable` tag as durable project authority;
- no ClamAV port published to the host — reachable only over the internal Compose network;
- FreshClam/signature-update capability enabled;
- a Docker health check required;
- the signature database may use its own persistent Docker volume — signature data is operational/cache data, not customer data, and does not need to enter INFOSECURS business-data backup sets;
- the web/application scanner abstraction talks only to the internal scanner service — no cloud malware scanning, no questionnaire bytes sent to any external SaaS/provider;
- this topology applies to both the normal development Compose architecture and the standalone release Compose architecture — **M009A is not a dev-only capability.** A release artifact in which Customer Assurance upload always fails because no scanner exists is not M009A GREEN.

The scanner result retains bounded operational provenance in `security_gate_result`: scanner backend; engine/version where available; signature/database version or timestamp where available; scan result; scan completion time. **Never persist file content in scanner-result metadata.**

At least one real ClamAV-backed acceptance test must demonstrate: a legitimate XLSX receives `CLEAN`; a standard safe anti-malware test specimen (e.g. the EICAR test file) is detected rather than allowed through.

If integrating this cleanly requires architecture beyond this Work Order: **STOP and return to Architect** rather than silently weakening the gate.

## OOXML container gate — hardened (Correction 7)

Before `openpyxl` sees the artifact, bounded container inspection must cover at minimum:

- `[Content_Types].xml` exists;
- `_rels/.rels` exists;
- `xl/workbook.xml` exists;
- the workbook content type is a permitted non-macro XLSX type;
- no `xl/vbaProject.bin`;
- no macro-enabled workbook content type;
- no `xl/externalLinks/` package parts;
- no encrypted ZIP members;
- no duplicate normalised archive member names;
- no absolute/archive-traversal member names;
- no `..` traversal after normalising path separators;
- no NUL/invalid path tricks.

**Do not extract ZIP members onto the filesystem merely to inspect them.** Reject malformed/ambiguous package structures. Hostile fixtures for each of the above are required (see "Evaluation corpus" below).

### External relationships — not only `xl/externalLinks/` (Final Correction D)

`xl/externalLinks/` alone is too narrow — OOXML external relationships can exist outside that directory. The security gate must inspect **every relevant `.rels` relationship document** and reject any relationship with external targeting, including conceptually `TargetMode="External"`. **Do not permit an external hyperlink/image/object simply because no `xl/externalLinks/` package member exists.** Internal relationship targets must also be normalised and proven to remain inside the package namespace; malformed relationship targets fail closed; required workbook/worksheet relationships must resolve to actual package members. Fixtures required (see "Evaluation corpus"): `xl/externalLinks/`; external `TargetMode`; a malformed/internal-traversal relationship target; a missing relationship target.

### XML hardening before `openpyxl` (Final Correction E)

M009A processes attacker-controlled OOXML. Use **`defusedxml`** with `openpyxl`. The bounded pre-parse package gate must reject OOXML XML parts containing prohibited DTD/entity constructs rather than forwarding them into the semantic parser. Test at minimum: DOCTYPE-bearing OOXML XML; ENTITY/billion-laughs-style input; malformed XML. **The evidence must prove the hardened parser path is actually active** (e.g. a billion-laughs-shaped fixture genuinely rejected end to end), not merely that `defusedxml` is listed in `requirements.txt`.

## Security limits — frozen for M009A-v1 (Correction 8)

Not "proposed." Frozen:

- upload compressed size: **10 MiB**
- total permitted uncompressed archive size: **200 MiB**
- maximum archive entries: **10,000**
- maximum per-entry decompressed/compressed ratio: **100:1**

Implementation must correctly handle zero-sized/zero-compressed edge cases without division errors. If legitimate test evidence shows a limit is inappropriate: **STOP and return to Delivery Controller/Architect with evidence before weakening it.** A more conservative implementation limit is also an architectural change if it materially narrows supported customer files — do not silently alter these values either direction.

### Enforcement against actual streamed bytes, not just metadata (Final Correction F)

Do not rely exclusively on ZIP central-directory metadata for bomb defence. Before semantic parsing: inspect advertised compressed/uncompressed sizes; enforce the frozen ratio/count/total limits above; when any package member is read, use bounded streaming reads and actual decompressed-byte counters; abort immediately if actual bytes exceed the permitted budget; **never call an unbounded read on an attacker-controlled archive member.** The total actual decompressed bytes consumed during gate inspection must remain bounded — this prevents malicious/inconsistent ZIP metadata from bypassing the intended resource limits.

### Upload size limit is streaming, not post-hoc (Final Correction G)

The 10 MiB upload limit is enforced **while consuming the uploaded stream**, not after the fact. Do not call an unbounded `.read()`; do not load the whole upload into memory; do not copy unlimited bytes into questionnaire storage and only check the size afterward. Compute SHA-256 and byte count during the same bounded streaming pass used to persist/quarantine the file. Once the counter exceeds 10 MiB: stop processing; fail/reject cleanly; do not continue storing the body as a valid import. Document how Django's upload/temp-file behaviour interacts with this limit in the M009A evidence.

## Semantic extraction resource limits — frozen for M009A-v1 (Correction 9)

ZIP limits alone are insufficient — a valid XLSX can still create excessive CPU/database work through huge worksheet dimensions or cell counts. Frozen:

- maximum worksheets inspected: **50**
- maximum used rows per worksheet: **20,000**
- maximum used columns per worksheet: **256**
- maximum non-empty cells inspected across the workbook: **100,000**
- maximum normalised question candidates per import: **5,000**
- maximum persisted literal cell text: **32,767 characters** (Excel's own cell maximum)

Exceeding a bound must fail closed with a clear extraction reason. **Do not partially claim a workbook is successfully extracted after silently truncating it at a resource limit.** These are M009A-v1 limits and may be amended later from real Customer Zero evidence.

## XLSX v1 mapping rule — frozen, deterministic tabular questionnaires only (Correction 11)

M009A-v1 supports deterministic **tabular XLSX questionnaires**. For each visible worksheet:

1. Inspect a bounded header region.
2. Normalise header strings by trimming whitespace and case-folding.
3. Identify a question column only through the finite governed header vocabulary below.
4. Identify an answer/response column separately through the finite governed header vocabulary below.
5. If more than one plausible question column is present on the same sheet, **do not guess** — mark that sheet/import ambiguous (`excluded_ambiguous`).
6. If no sheet contains a deterministically identifiable question column, the import ends `extraction_failed` with a useful reason.
7. Process **every** unambiguous questionnaire sheet — never arbitrarily "the first worksheet" only.
8. Literal non-empty values in the identified question column become candidates unless an explicit deterministic exclusion rule applies.
9. Formula cells never become questions (per the formula-handling rule above).
10. Exact normalised duplicates within the same import may be marked `excluded_duplicate`, while preserving the raw/source record.
11. Blank rows do not require a `QuestionnaireImportQuestion` row.
12. Do not persist arbitrary unrelated workbook cells merely because the extractor visited them.

**V1 question-header vocabulary** (case-folded, whitespace-trimmed exact match): `question`, `security question`, `assessment question`, `control question`, `requirement`, `security requirement`, `question / requirement`, `control / question`.

**V1 answer-header vocabulary**: `answer`, `response`, `your answer`, `your response`, `supplier response`, `vendor response`, `company response`.

**Do not include vague columns such as generic `notes` or `comments` as answer destinations automatically.** If actual fixture evidence during implementation proves an additional header alias is clearly needed, document it in the implementation evidence and bring it to Delivery Controller review — **do not introduce fuzzy/AI-based header interpretation in M009A.**

## Non-question dispositions — deterministic only (Correction 12)

Do not claim semantic certainty the deterministic extractor does not possess. `heading` or `instructional_text` may only be assigned when there is a deterministic *structural* rule supporting that disposition (e.g. an obvious merged section row may be structurally classified as a heading). **Do not decide that arbitrary prose "looks instructional" using undocumented natural-language heuristics.** If content in the identified question column cannot be safely classified as a question or a specific structural non-question, use the explicit conservative `excluded_other` disposition with a recorded reason. **No AI classifier in M009A.**

## Import-level extraction summary (Correction 13)

`QuestionnaireImport.extraction_summary` (bounded `JSONField`) must record, at minimum: sheets discovered; sheets processed; sheets skipped and the deterministic reason; question count; excluded count by disposition; failed count; whether an answer destination was found for at least one question. **Do not store arbitrary workbook body content in this summary.** This prevents "a sheet was silently ignored" from becoming invisible product behaviour.

## Service-owned state transitions (Correction 14)

Views must not freely mutate `security_gate_status`, import `status`, the extraction summary, or any artifact-identity field. Implement the upload/security/extraction lifecycle through bounded domain services with explicit allowed transitions; invalid transitions fail closed. The UI calls services — it never directly manipulates lifecycle fields.

### State consistency between `security_gate_status` and `status` (Final Correction J)

Because both fields exist, their permitted combinations must be explicit and tested. The domain service must never create contradictory states such as: gate `rejected` + lifecycle `extracting`; gate `pending` + lifecycle `extracted`; gate `failed` + lifecycle `extracting`. Service tests must enumerate valid transition/state combinations. Use database constraints where they remain simple and valuable; otherwise model/service fail-closed validation plus exhaustive tests is acceptable. Views still never mutate lifecycle fields directly.

## Minimal real customer entry surface (Correction 15)

This Work Order includes the minimal product surface needed to prove the feature, on the existing **Customer Assurance** page:

- an XLSX upload control, with clear accepted-format/size wording;
- CSRF-protected POST;
- **Monthly+ entitlement enforcement** (reuse the existing `customer_assurance` ProductArea — do not create a new entitlement family);
- a tenant-scoped import detail/status page.

The import detail page shows only M009A-scoped information: original safe display filename; uploaded time; security-gate status; extraction status; counts of question/excluded/failed items; extracted question text/source location where safe; a clear failure/rejection reason. **It must NOT add** answer generation, answer review, bulk accept, export/write-back, DOCX/PDF, or AI.

Real Chromium acceptance at 1280px/768px/375px is required for these changed user-facing surfaces. Direct URL entitlement tests must prove: PAUSED denied; FOUNDATION denied; MONTHLY allowed; PRO allowed.

### Untrusted XLSX content rendered in the UI — XSS browser proof required (Final Correction I)

M009A renders external workbook content (extracted question text, source-location data) in the Customer Assurance UI. Add hostile display cases containing, at minimum: `<script>`; HTML tags; event-handler payloads; very long strings; quotes/entity-like content. Prove in real Chromium that: content renders as inert text; no script/event executes; HTML is not interpreted as product markup; no horizontal overflow occurs at 375px; source-location data also renders safely. Django auto-escaping is expected to provide much of this protection, but **acceptance requires proof, not assumption.**

## No async infrastructure (Correction 16)

M009A does not authorise Celery, Redis queues, workers, or any new job platform merely for XLSX parsing. The bounded V1 file/resource limits above make synchronous processing acceptable for this milestone. If implementation evidence proves synchronous processing cannot safely satisfy the bounded product contract: **STOP and return to Architect** — do not solve that by inventing infrastructure.

## Backup / reset / storage tests — acceptance-gating (Correction 17)

Explicit tests must prove: web-container recreation does not lose questionnaire files; Customer Zero reset removes M009A database state; Customer Zero reset removes the fixture tenant's questionnaire file directory; another tenant's questionnaire rows/files remain untouched by that reset; backup/restore includes questionnaire artifact bytes and their matching database metadata; the original artifact's SHA-256 remains identical after extraction. This extends the existing operational guarantees — it does not redesign them.

## Dependencies — corrected, not "openpyxl only" (Final Correction C)

The earlier claim that `openpyxl` is the only dependency this Work Order introduces is **withdrawn — it is false.** M009A explicitly authorises:

- **`openpyxl`** — XLSX parser. Load mode mandated: `read_only=True, data_only=False` (see formula handling above — corrected from the earlier draft).
- **`defusedxml`** — XML hardening required for hostile XLSX processing (see "XML hardening before `openpyxl`" above).

Both must be exact pinned/hash-locked runtime dependencies with licence review, dependency scan, and build-reproducibility evidence per `docs/runbooks/BUILD-REPRODUCIBILITY.md` before this Work Order's own Independent Audit.

If a small, maintained Python client dependency is required to communicate safely with `clamd`, it is permitted under this Work Order, subject to the same pin/hash/licence/security review. **Do not write a bespoke unsafe network protocol merely to preserve an artificial "one Python dependency" rule.**

The ClamAV container itself is also a runtime dependency and requires: exact image version/digest; provenance; vulnerability/container scan evidence (per the deployment shape frozen under "Scanner deployment shape" above).

## Verification before reporting back — full repository gate (Correction 19)

Because M009A adds models, migrations, storage, entitlement-visible UI, and necessarily reconciles the fail-closed Customer Zero reset graph, this Work Order requires **the full repository test suite**, not merely "apps touched plus core." Also required:

- the new M009A evaluation corpus GREEN;
- the existing M005 14-case corpus unchanged and GREEN;
- `makemigrations --check --dry-run` clean after the intended committed migration;
- `gitleaks detect` clean;
- all seven GitHub CI/security checks GREEN;
- `openpyxl` licence/dependency/build-reproducibility evidence;
- real-browser upload/status acceptance at 1280/768/375;
- tenant-isolation adversarial tests;
- the reset regression tests above;
- the backup/restore regression tests above;
- **AI-call verification, corrected wording**: M009A application/product paths make zero AI invocations; no live/external model call is made during M009A verification; the unchanged M005 regression corpus may use its existing, already-governed deterministic fake/testing gateway — that is not a new AI path;
- DARWIN untouched.

## Evaluation corpus (Correction 20)

New fixtures/harness (e.g. `questionnaire/eval/m009a_ingestion_corpus.py`), covering at minimum:

- a well-formed multi-question, multi-sheet workbook (tests the "process every unambiguous sheet" rule);
- a candidate cell containing a formula;
- an external-link workbook;
- a macro-bearing workbook, including one renamed with a `.xlsx` extension (proves content-sniffing, not extension, rejects it);
- an oversized upload;
- a high-expansion-ratio ZIP (zip-bomb shape);
- an archive with too many members;
- a non-XLSX file renamed with a `.xlsx` extension;
- a corrupt/truncated ZIP;
- an archive with duplicate member names;
- an archive with a traversal/absolute member name;
- an archive with an encrypted member;
- a malformed `[Content_Types].xml`;
- a workbook missing required OOXML relationships;
- a semantic-extraction-resource-limit breach (e.g. too many rows);
- a sheet with multiple plausible question columns (ambiguous);
- a workbook with no identifiable question column;
- a legitimate re-upload/`supersedes` case;
- cross-tenant access attempts;
- the immutable-original before/after byte-identity proof;
- an XML/parser-hostility case appropriate to the chosen `openpyxl`/XML stack (e.g. a billion-laughs-shaped entity expansion attempt), so the Independent Auditor can verify malicious XML does not reach an unsafe parser path;
- an OOXML relationship with external `TargetMode` outside `xl/externalLinks/` (Final Correction D);
- a malformed/internal-traversal relationship target and a missing relationship target (Final Correction D);
- a DOCTYPE-bearing OOXML XML part and an ENTITY/billion-laughs-style part, proving `defusedxml` hardening is genuinely active (Final Correction E);
- a crafted-metadata ZIP where advertised sizes understate actual decompressed bytes, proving enforcement is against real streamed bytes, not just central-directory metadata (Final Correction F);
- an upload exceeding 10 MiB proving the stream is aborted mid-transfer, not measured post-hoc (Final Correction G);
- a real ClamAV `CLEAN` result on a legitimate file and a real ClamAV detection on a standard safe test specimen (e.g. EICAR) (Final Correction B);
- a simulated scanner `UNAVAILABLE`/`ERROR` condition proving the import lands in `security_gate_failed` (retryable), not `security_gate_rejected` (Final Correction A);
- hostile display content (`<script>`, HTML tags, event-handler payloads, very long strings, quote/entity-like content) proving inert rendering in real Chromium (Final Correction I).

## Required durable evidence

`docs/evidence/M009A-SECURE-INGESTION-XLSX.md` — implementation rationale, the full security-gate verification (each hostile fixture in the evaluation corpus demonstrably rejected, including the Final-Correction-specific fixtures above), the immutable-original proof (including the three-way rejected/failed/passed retention distinction), tenant-isolation test results, Customer Zero reset reconciliation proof, backup/restore proof, dependency/licence/build evidence for `openpyxl`/`defusedxml`/any `clamd` client/the ClamAV container image, the complete M005-corpus-unchanged confirmation, real-browser acceptance evidence for the Customer Assurance upload/status surface including the XSS-inertness proof, and the state-consistency test matrix for `security_gate_status`×`status`.

## STOP conditions

- Any need to call `generate_questionnaire_response` or any AI orchestration module.
- Any need to modify `QuestionnaireQuestion`/`QuestionnaireResponse` schema or logic.
- Any need for DOCX/PDF handling.
- Any need for an export/write-back capability.
- Any ambiguity in the security-gate contract that cannot be resolved by the frozen rules above without weakening them.
- Any indication synchronous processing cannot safely satisfy the bounded product contract (do not reach for async infrastructure — stop instead).
- Any indication a concrete malware scanner cannot be integrated cleanly within this Work Order's frozen ClamAV/clamd deployment shape.

## Delivery sequence

1. Confirm exact base SHA before touching anything.
2. Implementer builds the two new models + migration (in the existing `questionnaire` app), the security gate (including the ClamAV/clamd deployment, `defusedxml` hardening, external-relationship inspection, and streaming enforcement), XLSX extraction, storage layer, tenant isolation, the Customer Zero reset reconciliation, the backup/restore reconciliation, the minimal Customer Assurance upload/status surface (including the XSS-inertness proof), the M009A evaluation corpus, and the immutable-original proof — strictly within this Work Order's scope.
3. Delivery Controller review (independent spot-check of the highest-risk claims: security-gate rejections actually reject each hostile fixture live including the new Final-Correction fixtures, scanner result semantics genuinely distinguish `security_gate_failed` from `security_gate_rejected`, a real ClamAV scan genuinely detects a test specimen, immutable-original proof genuinely re-reads from disk, tenant isolation genuinely returns 404, Customer Zero reset genuinely removes the new model's rows and files without weakening any existing gate, untrusted content genuinely renders inert in a real browser).
4. Fresh Independent Audit.
5. PR, Architect Acceptance, merge, closure — normal chain.

## Architect acceptance

**Architect:** Central Architecture / Project Architect
**Acceptance date:** 2026-10-10
**Architecture base:** `93acc86405597641c46b050dd603ab335ebb60d1`
**Reviewed WO head before final acceptance corrections:** `119148183c7a9faea34ba8226e881336276c2998`
**Decision:** **ACCEPTED FOR IMPLEMENTER DISPATCH**, conditional on the final A–J corrections in this revision being the only delta.

**This Work Order is DRAFT. No Implementer may be dispatched against it until the Architect accepts it.**
