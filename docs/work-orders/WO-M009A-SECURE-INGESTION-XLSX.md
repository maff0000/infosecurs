# WO-M009A — Secure Questionnaire Artifact Ingestion + XLSX Normalisation/Provenance

**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Exact base SHA:** `93acc86405597641c46b050dd603ab335ebb60d1`
**Status:** DRAFT — awaiting Architect review. **Do not dispatch an Implementer against this Work Order until it is accepted.**

## Scope — exactly this, nothing more

Secure ingestion of an uploaded XLSX questionnaire file and deterministic normalisation of its candidate questions, with full source-location provenance. This Work Order is **not**:

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
- No parser/extractor of any kind may run before the pre-parse security gate accepts the file. The security gate itself may perform only bounded container-level structural inspection (format/archive-member/expansion-ratio/macro/traversal checks) — not business/semantic parsing.
- Questionnaire content is DATA. Nothing in this Work Order sends file content to an AI model — there is no AI call anywhere in M009A's scope.

## Frozen model contracts

### `QuestionnaireImport`

New app or new models within the existing `questionnaire` app (Implementer's own choice, document the decision). Fields:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, pk | |
| `organisation` | FK → `Organisation`, `PROTECT` | tenant scope |
| `uploaded_by` | FK → User, `PROTECT` | |
| `uploaded_at` | `DateTimeField(auto_now_add=True)` | |
| `original_filename` | `CharField` | display only, sanitised for display, never used in any filesystem/parsing decision |
| `stored_filename` | `CharField` | opaque, server-generated `uuid4().hex`, matching `evidence/storage.py`'s own convention |
| `detected_content_type` | `CharField` | from content-sniffing only (magic bytes + archive structure), never client-supplied |
| `file_format` | `CharField`, choices | `xlsx` is the only value this Work Order's validation accepts; the field itself is defined broadly enough that M009D can add `docx`/`pdf` later without a schema change |
| `sha256_hash` | `CharField(max_length=64)` | computed streaming, chunk-by-chunk |
| `size_bytes` | `PositiveBigIntegerField` | |
| `security_gate_status` | `CharField`, choices: `pending`, `passed`, `rejected` | |
| `security_gate_result` | `JSONField` | structured rejection reason(s) / structural inspection summary — never raw file content |
| `status` | `CharField`, choices: `uploaded`, `security_gate_pending`, `security_gate_rejected`, `extracting`, `extracted`, `extraction_failed` | this Work Order populates/transitions only these six; later increments add `ready_for_review`/`completed` etc. without a schema change to this field's choice list being treated as a truth-engine change |
| `supersedes` | self-FK, nullable, `PROTECT` | set when a re-upload is intended to replace a prior import; the prior import and all its questions remain, untouched and inspectable |
| `created_at`/`updated_at` | timestamps | |

### `QuestionnaireImportQuestion`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, pk | |
| `import` | FK → `QuestionnaireImport`, `CASCADE` | |
| `question` | FK → `QuestionnaireQuestion`, nullable, `PROTECT` | set only when `disposition=question` and normalisation succeeds; **the existing M005 model, completely unmodified** |
| `raw_extracted_text` | `TextField` | the literal extracted cell text, always populated regardless of disposition — this is what makes a non-question disposition auditable rather than silently dropped |
| `source_location` | `JSONField` | the versioned contract below |
| `extraction_order` | `PositiveIntegerField` | preserves original document order |
| `extraction_status` | `CharField`, choices: `pending`, `extracted`, `failed` | |
| `extraction_error` | `TextField`, nullable | |
| `disposition` | `CharField`, choices: `question`, `heading`, `instructional_text`, `excluded_duplicate`, `excluded_other` | **explicit and auditable for every extracted row — never silently dropped**, per the PID's send-ready predicate requirement |

### `QuestionnaireExport` — **deferred to M009D, not created by this Work Order**

M009A has no export/output capability at all. Creating this model now would be scope creep against a capability this Work Order doesn't implement.

### Source-location contract (versioned, validated, fail-closed)

```json
{
  "schema_version": 1,
  "format": "xlsx",
  "sheet_name": "<string>",
  "sheet_index": <int>,
  "cell": "<e.g. B14>",
  "row": <int>,
  "column": "<e.g. B>"
}
```

Validated against a schema check before being persisted. **If a candidate's location cannot be expressed in this exact schema, the row's `extraction_status` is `failed` (or `disposition=excluded_other` with `raw_extracted_text` still populated) — it must never proceed as if a valid location existed.** `schema_version` exists so a future format (DOCX's table/row/cell or paragraph addressing) adds a new, separately-validated shape rather than overloading this one.

## Import/artifact lifecycle (state machine — binding)

```
uploaded
  → security_gate_pending
      → security_gate_rejected   (terminal; stored bytes may be deleted immediately — see cleanup below)
      → extracting
          → extracted            (terminal for M009A; M009B+ advances status further)
          → extraction_failed    (retryable — re-run extraction, never re-upload required)
```

## XLSX question/answer-cell identification rules

The Implementer must propose and document a deterministic, testable extraction rule as part of implementation evidence — this Work Order does not freeze the exact heuristic, but binds its shape: **every extracted row must receive an explicit, auditable `disposition`; ambiguous content is excluded with a recorded reason, never guessed into a `question` disposition.** A reasonable starting point: a single designated "questions" worksheet (by name or position, implementation's choice, documented), iterating rows, treating a cell as a question candidate only if it is a literal text value (never a formula — see formula handling below) above a minimum length threshold; non-qualifying cells are recorded with `disposition=heading`/`instructional_text`/`excluded_other` as appropriate, never silently skipped from the `QuestionnaireImportQuestion` table entirely (every row the extractor visits gets a row in this table, even if excluded).

## Security-gate contract (binding, frozen at this Work Order)

- **Allowlist**: only `.xlsx` accepted. Validated by content-sniffing: ZIP local-file-header magic bytes (`PK\x03\x04`) **and** confirmed presence of `xl/workbook.xml` inside the archive (true OOXML spreadsheet structure) — never filename extension or client Content-Type alone.
- **Macro rejection**: reject if `xl/vbaProject.bin` is present in the archive, or if the detected structure indicates a macro-enabled workbook. Only plain `.xlsx` is accepted; `.xlsm` is always rejected regardless of extension.
- **Size limit**: 10 MiB, matching the existing `evidence/storage.py::MAX_UPLOAD_BYTES` order of magnitude (exact figure confirmable/tunable in implementation evidence).
- **Archive expansion limits** (ZIP-bomb defence): a maximum total uncompressed size (proposed: 200 MiB), a maximum per-entry compression ratio (proposed: reject any single archive member whose decompressed:compressed ratio exceeds 100:1), and a maximum archive entry count (proposed: 10,000). Exact figures are implementation-evidence-tunable but must exist and be enforced before any entry is fully decompressed.
- **External-link handling**: reject any workbook containing `xl/externalLinks/` entries outright — fail closed, do not attempt to sanitise or strip.
- **Formula handling at ingestion**: `openpyxl` must be loaded with `read_only=True, data_only=True` — never triggers formula recalculation, never evaluates a formula from an untrusted file. If a candidate cell contains a raw formula rather than a literal value, it is excluded (`disposition=excluded_other`), never guessed from a cached value alone without validation.
- **Path-traversal defence**: reuse the `evidence_file_path` pattern exactly — reject any `stored_filename` containing `/`, `\`, or `.`/`..`, then re-resolve via `realpath` + `commonpath` containment against the organisation's storage directory.
- **Malware scanning**: a scanner abstraction (e.g. `QuestionnaireFileScanner.scan(path) -> ScanResult`) must exist and be called unconditionally in the gate pipeline. A concrete backend (e.g. ClamAV) may be selected during implementation if the evidence supports it; if no concrete scanner is available in this environment, a documented stub that explicitly logs "malware scanning not yet integrated" is acceptable **but must never be silently absent or silently skipped** — the call site and its current behaviour must be visible in the code and in the evidence doc.
- **Tenant isolation**: identical discipline to `get_member_organisation_or_404` throughout.

## Storage layout

Mirrors `evidence/storage.py`'s proven pattern: a new lazy-loaded `QUESTIONNAIRE_STORAGE_ROOT` env var (same lazy-read-only-when-needed discipline as `EVIDENCE_STORAGE_ROOT`), files stored at `{QUESTIONNAIRE_STORAGE_ROOT}/{organisation_id}/{stored_filename}`, mode `0640`, `O_EXCL` no-clobber write.

## Safe cleanup / failure behaviour

- **Security-gate-rejected files**: the `QuestionnaireImport` metadata row (hash, size, rejection reason, timestamps) is retained permanently for audit. The stored bytes themselves may be deleted immediately after rejection (no legitimate ongoing need to retain hostile/rejected bytes) — implementation may choose immediate deletion or a short bounded retention window; either is acceptable if documented in the evidence.
- **Extraction-failed imports**: the file passed the security gate (legitimately safe bytes) — stored bytes are retained, `status=extraction_failed`, and extraction is retryable without requiring re-upload.

## Dependency: `openpyxl`

The only dependency this Work Order introduces. MIT-licensed (compatible, no special licence action beyond the standard review step). Load mode **mandated**: `read_only=True, data_only=True`. Exact version/pin/hash via the normal `pip-compile` relock cycle; dependency scan, licence review, and parser-security tests required per `docs/runbooks/BUILD-REPRODUCIBILITY.md` before this Work Order's own Independent Audit.

## Tenant-isolation tests (required)

Every query path for `QuestionnaireImport`/`QuestionnaireImportQuestion` must prove: a non-member or foreign-organisation UUID returns 404 (never 403, never confirms existence); a `QuestionnaireImportQuestion` is never reachable independent of its parent `QuestionnaireImport`'s own organisation-scoped lookup.

## M009A-specific evaluation corpus (required, new — does not touch the existing M005 corpus)

New fixtures/harness (e.g. `questionnaire/eval/m009a_ingestion_corpus.py`) covering at minimum: a well-formed multi-question workbook with mixed headings/instructional text; a candidate cell containing a formula; a workbook with an external link; a macro-enabled file (including one renamed with a `.xlsx` extension, to prove content-sniffing — not extension — is what rejects it); an oversized file; a ZIP-bomb-shaped archive (crafted high-ratio entry); a non-XLSX file renamed with a `.xlsx` extension; a corrupted/truncated archive; a legitimate re-upload (`supersedes`) scenario; cross-tenant access-attempt cases.

## Immutable-original proof (required)

A direct, mechanical test: upload a file, compute its hash, run extraction, then re-read the stored original bytes from disk and confirm the hash is unchanged. Not "we didn't write code that touches it" — an actual before/after byte-identity proof.

## Verification before reporting back

- The full existing test suite for every app touched, plus `core`, green.
- `makemigrations --check --dry-run` — a new migration for the two new models is expected and must be clean/consistent (no divergence between model state and migration).
- `gitleaks detect` clean.
- Dependency scan/licence review/build-reproducibility evidence for `openpyxl`.
- The M009A-specific evaluation corpus green.
- The existing M005 14-case golden corpus run and confirmed unchanged/green (even though this Work Order never calls the truth engine, this proves no accidental interference).
- No AI call made anywhere during this Work Order's own verification.
- DARWIN untouched.

## Required durable evidence

`docs/evidence/M009A-SECURE-INGESTION-XLSX.md` — implementation rationale, the exact extraction-rule heuristic chosen and why, full security-gate verification (including a demonstrated rejection of each hostile fixture in the evaluation corpus), the immutable-original proof, tenant-isolation test results, dependency/licence/build evidence, and the complete M005-corpus-unchanged confirmation.

## STOP conditions

- Any need to call `generate_questionnaire_response` or any AI orchestration module.
- Any need to modify `QuestionnaireQuestion`/`QuestionnaireResponse` schema or logic.
- Any need for DOCX/PDF handling.
- Any need for an export/write-back capability.
- Any ambiguity in the security-gate contract that cannot be resolved by the frozen rules above without weakening them.

## Delivery sequence

1. Confirm exact base SHA before touching anything.
2. Implementer builds the two new models + migration, the security gate, XLSX extraction, storage layer, tenant isolation, the M009A evaluation corpus, and the immutable-original proof — strictly within this Work Order's scope.
3. Delivery Controller review (independent spot-check of the highest-risk claims: security-gate rejections actually reject each hostile fixture live, immutable-original proof genuinely re-reads from disk, tenant isolation genuinely returns 404).
4. Fresh Independent Audit.
5. PR, Architect Acceptance, merge, closure — normal chain.

**This Work Order is DRAFT. No Implementer may be dispatched against it until the Architect accepts it, and not before PR #101 has merged and the base SHA above is set to the exact resulting canonical main SHA.**
