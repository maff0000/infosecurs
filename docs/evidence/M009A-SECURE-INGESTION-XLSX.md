# M009A — Secure Questionnaire Artifact Ingestion + XLSX Normalisation/Provenance

**Work Order:** `docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Branch:** `wo/M009A-work-order` (base `4fe38b91bde5e859d19da8a9a1c489ccc3cb7f41`)
**Status:** Implementer-complete — awaiting Delivery Controller review, fresh Independent Audit, PR, Architect Acceptance.

This is the required durable evidence document (WO-M009A's own "Required
durable evidence" section). It covers implementation rationale, the full
security-gate verification against every fixture in the evaluation
corpus, the immutable-original three-way retention proof, tenant
isolation, Customer Zero reset reconciliation, backup/restore, dependency/
licence/build evidence, the M005-corpus-unchanged confirmation,
real-browser acceptance including the XSS-inertness proof, and the
`security_gate_status`×`status` state-consistency matrix.

All work was built and verified on dell-debian inside a disposable Docker
Compose stack, project name `m009a` (`WEB_HOST_PORT=18900`,
`POSTGRES_HOST_PORT=18901`) — never the canonical `infosecurs-relocation`
deployment (port 8884) and never any other stack already running on that
host.

## Implementation rationale (file-by-file)

- `questionnaire/models.py` — `QuestionnaireImport` / `QuestionnaireImportQuestion`
  added to the EXISTING `questionnaire` app (Domain placement, Correction
  1) — no new Django app. `QuestionnaireQuestion`/`QuestionnaireResponse`
  above them in the file are byte-for-byte unchanged. The frozen
  (`security_gate_status`, `status`) state-consistency contract (Final
  Correction J) is enforced in `QuestionnaireImport.save()` via
  `IMPORT_ALLOWED_STATE_COMBINATIONS` — a fail-closed backstop underneath
  the service layer, not a substitute for it. Artifact-identity fields are
  enforced immutable the same way `evidence.models.EvidenceItem.save()`
  already does for its own `IMMUTABLE_FILE_FIELDS`. One naming note: the
  WO's own frozen-contract table calls the FK field `import`; this is a
  reserved Python keyword and cannot be a model attribute name (`obj.import`
  is a `SyntaxError`), so it is named `import_record` throughout — same FK
  target/`on_delete=CASCADE`, same semantics, substantively unchanged.
- `questionnaire/migrations/0003_m009a_questionnaire_import.py` — the one
  committed migration for both new models + their indexes.
- `activity/migrations/0007_m009a_questionnaire_import_events.py` — Django
  tracks `choices=` as migration state even though it is not a DB column
  constraint; six new `ActivityEvent.EVENT_QUESTIONNAIRE_IMPORT_*` choices
  required this companion migration for `makemigrations --check` to stay
  clean.
- `questionnaire/upload_handler.py` — `QuestionnaireUploadSizeGuardHandler`,
  a custom `django.core.files.uploadhandler.FileUploadHandler` installed as
  the FIRST handler on the request (`install_upload_size_guard`, called by
  the upload view BEFORE `request.POST`/`request.FILES` is ever touched).
  Computes the running byte count and SHA-256 incrementally inside
  `receive_data_chunk`, raising Django's own `StopUpload(connection_reset=
  True)` the instant the total exceeds the frozen 10 MiB limit — a genuine
  mid-stream abort (closes/resets the connection), never "read everything,
  reject after" (Final Correction G). See that module's own docstring for
  the full documented interaction with Django's default upload-handler
  chain (Memory/TemporaryFileUploadHandler still materialises the real
  `UploadedFile` completely normally; this handler is a transparent
  observer that can abort early, never a replacement storage handler).
- `questionnaire/import_storage.py` — mirrors `evidence/storage.py`'s
  proven pattern exactly: lazily-resolved `QUESTIONNAIRE_STORAGE_ROOT`
  (never `EVIDENCE_STORAGE_ROOT` — a deliberately separate storage root),
  per-organisation directory (`0750`), opaque `uuid4().hex` filenames
  (`0640`), strict `os.path.realpath`/`os.path.commonpath` containment on
  every read/delete. `store_and_hash_uploaded_file` is ONE bounded
  streaming pass that persists bytes, computes SHA-256/byte-count, and
  sniffs the ZIP signature, all in the same pass — a defence-in-depth
  re-check of the 10 MiB limit independent of whether `upload_handler`
  already aborted earlier.
- `questionnaire/security_gate.py` — the bounded, pre-parse OOXML
  container gate (Correction 7, Final Corrections D/E/F). Never imports
  `openpyxl`. Structural checks: entry count (≤10,000), traversal/
  absolute member names, duplicate member names, encrypted members
  (general-purpose flag bit 0), required members present
  (`[Content_Types].xml`/`_rels/.rels`/`xl/workbook.xml`), forbidden
  members (`xl/vbaProject.bin`, anything under `xl/externalLinks/`),
  permitted (non-macro) workbook content type. Then a REAL-BYTES pass over
  **every** archive member (not only the few parts semantically inspected)
  using `_bounded_decompressed_read` — a shared, mutable global byte
  budget (200 MiB) plus a per-entry 100:1 ratio check against ACTUAL
  streamed bytes, never trusting central-directory metadata alone (Final
  Correction F). Every XML part this gate reads (`[Content_Types].xml`,
  every `.rels` document, `xl/workbook.xml`) is parsed with `defusedxml`
  (Final Correction E) from those already-bounded-read bytes. Every
  `.rels` document anywhere in the package is inspected for
  `TargetMode="External"` and for relationship targets that fail to
  resolve to a real, in-package member after `..`-normalisation (Final
  Correction D) — not only `xl/externalLinks/`.
- `questionnaire/scanner.py` — the four-state scanner abstraction
  (`CLEAN`/`INFECTED`/`UNAVAILABLE`/`ERROR`). `ClamdScanner` is a bounded,
  timed-out hand-written client for `clamd`'s documented `INSTREAM`
  protocol (see that module's own docstring for the "small protocol vs.
  small dependency" judgement call, explicitly permitted either way by the
  WO). `UnavailableScanner` deterministically returns `UNAVAILABLE` —
  never `CLEAN` — when `CLAMAV_HOST` is unset; this is the Correction 6
  withdrawal of the earlier "stub that logs and passes" made literal.
- `questionnaire/xlsx_extraction.py` — deterministic extraction.
  `openpyxl.load_workbook(file_path, read_only=True, data_only=False)`
  (Correction 5, binding) — formula cells are detected via
  `cell.data_type == "f"` and excluded, never evaluated, never
  cache-substituted (no second `data_only=True` read anywhere in this
  module). Governed header vocabulary (Correction 11), bounded header-scan
  window, ambiguous/no-question-column handling, exact-duplicate
  detection, the one deterministic structural heading rule (a merged,
  horizontally-spanning top-left cell — Correction 12 forbids any NLP
  "looks instructional" heuristic), and the full Correction 9 resource
  ceiling set. Merged-range detection needed one documented workaround:
  `openpyxl`'s `read_only=True` mode exposes no `ws.merged_cells` API at
  all (confirmed directly against this pinned `openpyxl==3.1.5`) — rather
  than abandon `read_only=True` or open the workbook a second time with
  `openpyxl` itself, `_merged_ranges_for_worksheet` reads ONLY that one
  worksheet's own XML part (`ws._worksheet_path`) via a bounded `zipfile`
  read + `defusedxml` parse, the same hardened discipline
  `security_gate.py` already uses elsewhere.
- `questionnaire/import_services.py` — the ONE governed service layer
  (Correction 14): `ingest_questionnaire_import` / `retry_security_gate`,
  plus the internal gate→scanner→extraction pipeline functions. Views
  never construct a lifecycle transition themselves. Implements the
  lifecycle diagram and the `security_gate_rejected` (deterministic,
  terminal, bytes removed) vs. `security_gate_failed` (scanner/
  infrastructure, retryable, bytes retained) distinction exactly (Final
  Correction A).
- `questionnaire/forms.py` / `views.py` / `urls.py` / `templates/
  questionnaire/import_upload.html` / `import_detail.html` — the minimal
  real Customer Assurance surface (Correction 15): upload control +
  tenant-scoped detail/status page, CSRF-protected, reusing the EXISTING
  `customer_assurance` ProductArea (the `questionnaire` URL namespace
  already mapped there before M009A — no `entitlements` change needed).
  Display-only: no answer generation/review/export/DOCX/PDF/AI anywhere on
  either page.
- `activity/models.py` — six new `EVENT_QUESTIONNAIRE_IMPORT_*` choices,
  additive only.
- `organisations/reset_service.py` — `questionnaire.QuestionnaireImport`
  added to `EXPECTED_DELETE_DIRECT_FK_MODELS`; deleted inside the existing
  transaction BEFORE `QuestionnaireQuestion` (per the WO's explicit
  ordering instruction); `QuestionnaireImportQuestion` cascades
  automatically (no direct FK to `Organisation`). Filesystem cleanup
  extended to attempt EVIDENCE and QUESTIONNAIRE storage directory removal
  independently, both outside the DB transaction, with `ResetResult`
  gaining `questionnaire_directory_removed` and `ResetFilesystemError`
  naming whichever resource(s) failed — never silently reporting a
  partial filesystem failure as a clean reset.
- `docker-compose.yml` / `docker-compose.release.yml` — new `clamav`
  service in BOTH topologies: `clamav/clamav:1.4.3@sha256:75fb5fd9...`
  (exact digest, resolved via `docker pull` + `docker inspect`), no
  `ports:` mapping (internal-only), its own named volume for the signature
  DB, a Docker healthcheck (`clamdcheck.sh`). New `QUESTIONNAIRE_STORAGE_ROOT`
  /`CLAMAV_HOST`/`CLAMAV_PORT` env vars and a new `infosecurs_questionnaire_
  data`/`infosecurs_release_questionnaire_data` volume for `web`.
- `requirements.in`/`requirements.txt`, `requirements-dev.txt` — `openpyxl==
  3.1.5`, `defusedxml==0.7.1` (direct), `et-xmlfile==2.0.0` (transitive),
  hash-locked via `pip-compile --generate-hashes` inside a container built
  from the exact pinned Python digest this repo's build-reproducibility
  doctrine already requires.
- `scripts/backup.sh`/`restore.sh`, `docs/runbooks/BACKUP-RESTORE.md`,
  `core/management/commands/seed_backup_restore_fixture.py` — a third
  archive (`questionnaire-<timestamp>.tar.gz`) alongside the existing
  evidence archive, same discipline; the seed command now also creates one
  representative `QuestionnaireImport` through the REAL ingest pipeline
  (real scanner, since this command only ever runs against a live stack
  with `clamav` reachable).
- `questionnaire/eval/m009a_ingestion_corpus.py` — every hostile/
  legitimate fixture as a pure Python builder function (never a committed
  binary), consumed by the test files below.
- `questionnaire/tests/test_m009a_models.py`, `test_m009a_storage.py`,
  `test_m009a_security_gate.py`, `test_m009a_scanner.py`,
  `test_m009a_extraction.py`, `test_m009a_import_services.py`,
  `test_m009a_views.py`, `test_m009a_entitlement.py`,
  `test_m009a_browser_acceptance.py`,
  `organisations/tests/test_m009a_reset_reconciliation.py` — the M009A
  evaluation corpus and acceptance tests (Correction 20).
- `.github/workflows/ci.yml` — every new M009A test file wired into the
  `ci/unit` or `ci/integration` job's own curated test list (this repo's
  CI does not discover tests automatically — see "CI wiring" below for an
  important pre-existing gap this surfaced).

## CI wiring — an important pre-existing gap, noted not fixed

`.github/workflows/ci.yml`'s two jobs each run a HAND-CURATED list of
test files, not `pytest` discovery. While wiring in the new M009A files I
confirmed `organisations/tests/test_reset_service.py` and
`test_reset_views.py` (the EXISTING M008A reset-service tests, predating
this Work Order) are not in either job's list at all — a pre-existing gap,
not something this Work Order introduced or is in scope to fix. The NEW
`organisations/tests/test_m009a_reset_reconciliation.py` IS wired into
`ci/unit` (see the diff). Flagging this for Delivery Controller/Architect
attention rather than silently fixing an unrelated pre-existing CI gap
under this Work Order's own banner.

## Security-gate verification — every evaluation-corpus fixture

All fixtures live in `questionnaire/eval/m009a_ingestion_corpus.py`,
exercised by `questionnaire/tests/test_m009a_security_gate.py` (gate-level)
and `test_m009a_extraction.py` (extraction-level). **30/30 security-gate
tests pass, 12/12 extraction tests pass** (see "Full test run output"
below for the literal command/output).

| Fixture | Outcome proven |
|---|---|
| Valid multi-sheet workbook | ACCEPTED at the gate; extraction processes BOTH sheets (3 questions total) |
| Formula cell | Gate ACCEPTS (no opinion on formulas); extraction excludes it (`excluded_other`, never evaluated, never cache-substituted) |
| External-link directory (`xl/externalLinks/`) | REJECTED |
| External `TargetMode` outside `xl/externalLinks/` (worksheet `.rels`) | REJECTED (Final Correction D) |
| Malformed/traversal relationship target | REJECTED (Final Correction D) |
| Missing relationship target | REJECTED (Final Correction D) |
| Macro-enabled workbook (`xl/vbaProject.bin` + macro content type) | REJECTED |
| Oversized upload (>10 MiB) | REJECTED mid-stream by `upload_handler` (proven in `test_m009a_storage.py`'s `test_abort_above_max_bytes_deletes_partial_file`) |
| Zip-bomb shape (60 MiB real decompressed content) | REJECTED — real-bytes ratio check |
| Too many archive members (10,050) | REJECTED |
| Non-XLSX file renamed `.xlsx` | REJECTED by content-sniffing, before the container gate even runs |
| Corrupt/truncated ZIP | REJECTED |
| Duplicate member names | REJECTED |
| Traversal/absolute member name | REJECTED |
| Encrypted member | REJECTED |
| Malformed `[Content_Types].xml` | REJECTED |
| Missing required OOXML relationship (`xl/workbook.xml` absent) | REJECTED |
| Semantic-extraction resource-limit breach (rows / worksheet count) | `extraction_failed`, sheet- or import-level, with a clear reason |
| Ambiguous question columns | `extraction_failed` (`ambiguous_question_column`) |
| No identifiable question column | `extraction_failed` (`no_question_column`) |
| Legitimate re-upload / `supersedes` | Accepted twice, independently |
| Cross-tenant access attempt | 404, never 403 (see "Tenant isolation") |
| Immutable-original byte-identity | See "Immutable-original retention" below |
| Billion-laughs entity expansion (`[Content_Types].xml`) | REJECTED by `defusedxml`, proven via a genuine entity-expansion payload (Final Correction E) |
| DOCTYPE-bearing `xl/workbook.xml` | REJECTED by `defusedxml` |
| Crafted metadata understating actual decompressed bytes | REJECTED — caught via bounded real-bytes streaming (Python's own `zipfile` detects the declared-size/CRC inconsistency mid-read; this gate turns that into an ordinary rejection, not an unhandled exception) (Final Correction F) |
| Real ClamAV `CLEAN` / EICAR detection | See "Malware scanning" below |
| Simulated scanner `UNAVAILABLE`/`ERROR` | `security_gate_failed`, retryable, bytes retained (Final Correction A) |
| Hostile display content (XSS families) | Inert in real Chromium (see "Real-browser acceptance") |

## Malware scanning — real ClamAV proof (Final Correction B)

`questionnaire/tests/test_m009a_scanner.py::TestRealClamdBackend` runs
against the REAL `clamav` Compose service (internal-only, no host port —
confirmed via `docker compose ps`: `3310/tcp` with no host mapping):

- `ping()` → `True`.
- A legitimate XLSX (the valid multi-sheet corpus fixture) → `CLEAN`.
- The standard EICAR test string → `INFECTED`, with a non-empty
  `infected_signature`.

These three tests are skipped automatically wherever `CLAMAV_HOST` is
unset (e.g. a bare `pytest` run outside the Compose stack, or GitHub
Actions CI) — they ran for real inside the `m009a-web-1` container, which
has `CLAMAV_HOST=clamav` from `docker-compose.yml`.

## Immutable-original retention — three-way proof (Final Correction H)

`questionnaire/tests/test_m009a_import_services.py::
TestImmutableOriginalRetentionThreeWay`:

- **PASSED**: bytes on disk, re-read from disk after the full pipeline
  completes, compared byte-for-byte against the original upload — identical.
- **REJECTED**: bytes removed from disk immediately; audit metadata
  (`sha256_hash`, `size_bytes`, `security_gate_result`, timestamps) remains
  permanently in the DB row.
- **`security_gate_failed`**: bytes remain on disk, re-read and compared
  byte-for-byte — identical; never deleted while in this state.

`QuestionnaireImport.save()`'s immutability guard
(`test_m009a_models.py::TestImmutableFields`) independently proves
`organisation`/`stored_filename`/`original_filename`/`sha256_hash`/
`size_bytes`/`detected_content_type`/`file_format` cannot be changed after
creation, while lifecycle fields remain writable through a legal
transition.

## State-consistency matrix (Final Correction J)

`questionnaire/tests/test_m009a_models.py::TestStateConsistency` is
parametrised over EVERY allowed `(security_gate_status, status)` pair from
the WO's own lifecycle diagram (7 combinations, each proven to save
cleanly) and a representative set of contradictory pairs named explicitly
in the WO plus several more (6 combinations, each proven to raise
`QuestionnaireImportStateConsistencyError` before reaching the database).

## Tenant isolation

`questionnaire/tests/test_m009a_views.py::TestDetailViewTenantIsolation`/
`TestRetryView` and `organisations/tests/test_m009a_reset_reconciliation.py
::TestResetLeavesOtherTenantUntouched`:

- A non-member requesting another organisation's import detail/retry page
  gets 404, never 403.
- Pairing a genuine member's OWN organisation_id with ANOTHER
  organisation's import id also 404s (proves the import is scoped by both
  the URL's organisation AND its own FK — not merely a guessable UUID).
- A Customer Zero reset leaves another tenant's `QuestionnaireImport` rows
  AND files completely untouched, byte-for-byte.

## Customer Zero reset reconciliation

`organisations/tests/test_m009a_reset_reconciliation.py`:

- Reset removes every `QuestionnaireImport`/`QuestionnaireImportQuestion`
  row for the fixture organisation, AND its questionnaire-storage
  directory on disk.
- `ResetResult.questionnaire_directory_removed` correctly reports `True`/
  `False`.
- A reset with no questionnaire imports at all is a safe no-op.
- `TestModelDriftFailsClosed`/`test_the_real_unmodified_model_graph_passes_
  preflight` (existing M008A tests, re-run unmodified) continue to pass —
  the preflight model-graph guard is unaffected by the new model (it was
  explicitly added to the manifest, not left to be "discovered" as drift).
- No existing reset safeguard (typed-RESET confirmation, CSRF, environment
  gate, fixture-identity gate) was touched.

## Backup / restore (questionnaire storage)

Real run against the `m009a` disposable stack (see "Full test run output"
for the literal commands/output):

1. `seed_backup_restore_fixture` ran against the live stack — built a
   representative `QuestionnaireImport` through the REAL ingest pipeline
   (real `clamav`), confirmed `security_gate_status=passed`.
2. `scripts/backup.sh` produced `questionnaire-<ts>.tar.gz` alongside the
   existing `db-*.sql`/`evidence-<ts>.tar.gz`, with its own
   `questionnaire_archive_sha256` manifest entry.
3. `scripts/restore.sh` into a fresh, disposable project verified all
   three checksums before touching anything, restored the DB dump,
   un-tarred evidence AND questionnaire archives into fresh volumes, and
   brought `web` up with `migrate --noinput` reporting no pending
   migrations.
4. The restored `QuestionnaireImport`'s stored file's SHA-256 was
   compared directly against the SOURCE stack's own copy of the same
   file (not merely re-hashed in isolation) — identical — and against the
   `QuestionnaireImport.sha256_hash` DB column on the restored stack.

## Dependency / licence / build-reproducibility evidence

See `docs/delivery/BUILD-REPRODUCIBILITY.md`'s new "New dependencies"/
"ClamAV container image" sections (this Work Order's own addition) for
the full table. Summary:

- `openpyxl==3.1.5` (MIT), `defusedxml==0.7.1` (PSF-2.0), `et-xmlfile==
  2.0.0` (MIT, transitive) — added to `requirements.in`, hash-locked via
  `pip-compile --generate-hashes` inside the pinned-Python-digest
  container this repo's doctrine already mandates.
- `pip-audit -r requirements.txt` — zero known vulnerabilities for all
  three new packages at the time of this change.
- `clamav/clamav:1.4.4@sha256:a52f45e42753dca691b6c9fd09fe68d6ca9ac22fa8cd
  6a8a45d9237e188049e3` — resolved via `docker pull` + `docker inspect`,
  not a floating tag. **Trivy history on this image, both resolved
  live during this dispatch:** `1.4.3` scored 32 HIGH + 2 CRITICAL
  (`aquasec/trivy:0.70.0 image --severity CRITICAL,HIGH --ignore-unfixed`);
  the newer `1.4.4` tag was pulled and scanned the same way, scoring 0
  CRITICAL / 15 HIGH — strictly better, so `1.4.4` was pinned instead of
  `1.4.3`. **The residual 15 HIGH findings on `1.4.4` are OS-package CVEs
  inside ClamAV's own official upstream Alpine-based image** (not
  anything this Work Order's own code introduces) and are NOT currently
  covered by this repository's `security/container` CI job, which only
  builds+scans the APPLICATION image from this repo's own `Dockerfile` —
  it has never scanned the pulled `postgres` image either, for the same
  "we don't rebuild this, upstream owns its own patch cadence" reason.
  Flagged here for Delivery Controller/Architect visibility, not silently
  fixed or silently ignored — a future obligation to re-pin once ClamAV
  publishes a tag with these fixed, mirroring this repo's own existing
  "temporary exact-version security overlay" precedent for exactly this
  class of situation (`docs/delivery/BUILD-REPRODUCIBILITY.md`'s Python
  base-image section).
- **Application image Trivy scan (this Work Order's own code added to the
  existing, already-accepted application image):** `docker build` from
  this repo's `Dockerfile` (openpyxl/defusedxml/et-xmlfile now included)
  + `trivy image --severity CRITICAL,HIGH --ignore-unfixed` — **0
  vulnerabilities**, matching this repo's existing accepted baseline
  exactly (see `docs/delivery/BUILD-REPRODUCIBILITY.md`'s own "0
  vulnerabilities" baseline for the pre-M009A image).
- No bespoke malware-scanner Python client dependency added —
  `questionnaire.scanner.ClamdScanner` is a small, bounded, timed-out
  client for `clamd`'s own documented `INSTREAM` protocol (see that
  module's docstring for the full reasoning).

## Streaming upload limit — Django interaction (Final Correction G)

Documented in full in `questionnaire/upload_handler.py`'s own module
docstring. Summary: Django's `MultiPartParser` calls every handler in
`request.upload_handlers` with each chunk AS IT ARRIVES OFF THE WIRE,
before `request.POST`/`request.FILES` is populated and before any view
code runs. `QuestionnaireUploadSizeGuardHandler`, installed FIRST,
computes the running byte count/SHA-256 in that same `receive_data_chunk`
call and raises Django's own `StopUpload(connection_reset=True)` the
instant the limit is exceeded — genuinely aborting the connection, not
reading the rest of an attacker-controlled body and discarding it. It
returns each chunk unchanged, so Django's normal default handler chain
(`MemoryFileUploadHandler`/`TemporaryFileUploadHandler`) still
materialises the `UploadedFile` completely normally for any upload within
the limit — this handler only ever observes or aborts, never replaces
storage.

## Zero AI invocations

`questionnaire/tests/test_m009a_import_services.py::TestZeroAiInvocations`
proves the full ingest pipeline (storage → gate → scanner → extraction)
creates zero `ai_platform.AIInvocationRecord` rows. No M009A module
imports anything from `ai_platform`. The M005 14-case golden corpus
(unchanged — see below) continues to exercise its own existing,
already-governed fake/testing gateway, per the WO's explicit carve-out.

## M005 corpus — unchanged, confirmed GREEN

`questionnaire/eval/golden_corpus.py` and `harness.py` are byte-for-byte
untouched by this Work Order.
`questionnaire/tests/test_eval_harness.py test_eval_golden_corpus.py
test_eval_command.py` — **55/55 passed** (see "Full test run output").

## Real-browser acceptance (Correction 15, Final Correction I)

`questionnaire/tests/test_m009a_browser_acceptance.py`, real Chromium
(installed at runtime per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`
— never baked into any image):

- **XSS-inertness** (`TestXssInertness`, 375px): a workbook containing
  `<script>`, `<img onerror>`, `<svg onload>`, a 5,000-character string,
  and a quote/entity-heavy string is ingested through the real pipeline
  and its extracted text rendered on the import-detail page.
  `window.__auditXssFired` never fires, zero `pageerror`s, the hostile
  text is present as literal DOM text, no live `<script>` element carries
  the payload, and `scrollWidth <= clientWidth` (no horizontal overflow).
- **Upload + status acceptance** (`TestUploadAndStatusAcceptance`,
  parametrised 1280×800 / 768×1024 / 375×812): drives the real upload
  `<input type=file>` with a legitimate workbook, submits, lands on the
  import-detail page, zero page errors, no horizontal overflow at any
  width.

## A real bug found and fixed during this dispatch's own verification

The first real-Chromium run of `TestUploadAndStatusAcceptance` (the
upload-form acceptance test, not the XSS test) landed on `/accounts/
login/` after submitting the upload form — a genuine finding, not a test
artefact of the kind this report would otherwise gloss over. Root-caused
by instrumenting the actual network responses: the form's own submit
button and `application_shell.html`'s header "Log out" button are BOTH
`button[type="submit"]`, and the test's own CSS selector was ambiguous,
matching the header's logout form first — a test-authoring bug, not a
security defect. Fixed by scoping the test's selector to the upload
form specifically.

While investigating this, a second, independently real and more
important finding surfaced by reasoning about Django's own documented
behaviour (and confirmed by the rest of the test suite staying green
after the fix): installing `QuestionnaireUploadSizeGuardHandler` from
inside the view itself is too late for a REAL CSRF-enforced request -
`django.middleware.csrf.CsrfViewMiddleware` reads `request.POST` (to find
the CSRF token) during its own `process_view` hook, which runs BEFORE the
view, triggering Django's lazy multipart-body parse with whatever
`upload_handlers` the request already had at that point. `django.test.
Client` does not enforce CSRF by default, so every Client-based test
already in this corpus was blind to this ordering problem. The fix:
`questionnaire.upload_handler.QuestionnaireUploadSizeGuardMiddleware`,
installed in `MIDDLEWARE` (`config/settings.py`) BEFORE
`CsrfViewMiddleware`, narrowly scoped to exactly the one questionnaire-
import-upload path. See `questionnaire/upload_handler.py`'s own module
docstring for the full account. This is now the actual enforcement point
for Final Correction G in a real request; the view's own call to
`install_upload_size_guard` remains as a harmless, idempotent defence-in-
depth no-op.

## Backup / restore — real run, full detail

Performed against the `m009a` disposable stack (never
`infosecurs-relocation`), `git rev-parse HEAD` at the time
`4fe38b91bde5e859d19da8a9a1c489ccc3cb7f41` (pre-commit — this Work Order's
own implementation changes were not yet committed when this proof ran):

```text
$ docker compose -p m009a exec -T web python manage.py seed_backup_restore_fixture
organisation_id=2e02f7e1-545c-4cc7-8aed-c473205e9ab9
evidence_item_id=91fbc275-c042-4b00-85b9-479f9f8d4e4f
questionnaire_import_id=c107d70d-edd7-4bdb-8ecb-1c44d0deaf0a
questionnaire_import_security_gate_status=passed
Backup/restore demo fixture ready (idempotent, synthetic).

$ docker compose -p m009a exec -T web sh -c 'sha256sum /data/questionnaire/<org>/<stored>.xlsx'
48209b1d24cc7e4ba7c7ec1c5939839b2dbef6c69d6af62242a02a0d905cdb20  (matches QuestionnaireImport.sha256_hash exactly)

$ COMPOSE_PROJECT_NAME=m009a scripts/backup.sh /tmp/m009a-backup-demo
...
  DB dump:       db-infosecurs_m009a-20261010T211524Z.sql
  Evidence:      evidence-20261010T211524Z.tar.gz
  Questionnaire: questionnaire-20261010T211524Z.tar.gz
  Manifest:      manifest-20261010T211524Z.json

$ scripts/restore.sh /tmp/m009a-backup-demo m009arestore .env.m009arestore
Verifying archive checksums against manifest before restoring... Checksums verified OK.
...
Operations to perform:
  Apply all migrations: account, activity, admin, ai_platform, auth, ...
Running migrations:
  No migrations to apply.
Restore complete.

$ docker compose -p m009arestore exec -T web sh -c 'sha256sum /data/questionnaire/<org>/<stored>.xlsx'
48209b1d24cc7e4ba7c7ec1c5939839b2dbef6c69d6af62242a02a0d905cdb20  (IDENTICAL to source stack's own copy, not merely re-hashed in isolation)

$ docker compose -p m009arestore exec -T web python manage.py shell -c "... QuestionnaireImport.objects.get(id=...).sha256_hash"
48209b1d24cc7e4ba7c7ec1c5939839b2dbef6c69d6af62242a02a0d905cdb20  (matches both file hashes above)

$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18910/healthz/
200
```

**Web-container recreation (separately from backup/restore) does not lose
questionnaire files** - proven directly on the `m009a` stack itself:

```text
$ docker compose -p m009a stop web && docker compose -p m009a rm -f web
$ docker compose -p m009a up -d web
$ docker compose -p m009a exec -T web sh -c 'sha256sum /data/questionnaire/<org>/<stored>.xlsx'
48209b1d24cc7e4ba7c7ec1c5939839b2dbef6c69d6af62242a02a0d905cdb20  (unchanged across a full container stop/rm/recreate cycle)
```

The restore-target stack and its named volumes were torn down
(`docker compose -p m009arestore down -v`) immediately after this
verification; the source `m009a` stack was left running for the
remainder of this dispatch's own work.

## A verification-environment flakiness finding (not a code defect)

After the first fully-GREEN full-suite run, several more browser-heavy
operations ran back-to-back in the SAME long-lived `m009a-web-1`
container on this shared, loaded dell-debian host (54 other containers,
`free -h` showing swap 100% full at the time) without a container
restart in between: the real backup/restore cycle, a manual web-container
stop/rm/recreate proof, and two more full-suite runs. The second and
third full-suite runs each reported the SAME 49 failures (not randomly
different ones each time) - all of them real-Chromium browser tests
(this Work Order's own `TestUploadAndStatusAcceptance[768-1024]`/
`[375-812]`, plus PRE-EXISTING, unrelated tests like `remediation/
risk_register`'s `*_narrow_viewport_regression.py`). The container's
`/dev/shm` is Docker's tiny 64 MiB default, which Chromium is well known
to exhaust under sustained repeated-launch load inside a container - and
the deterministic (not random) repeat of the identical 49 failures
across two consecutive runs is consistent with an accumulated, not
self-healing, per-container resource ceiling (leaked shared-memory/
zombie renderer state), not a code regression: none of the intervening
changes touched product code in any way that could explain browser tests
failing (one was an unused dead-code removal in `questionnaire.
upload_handler`, confirmed by `python -c "import questionnaire.
upload_handler"` succeeding cleanly). Recreating `web` fresh (`docker
compose -p m009a stop web && rm -f web && up -d web`, then reinstalling
Chromium into the new container's writable layer per the standard runbook
procedure) and re-running the full suite is the controlling verification
this evidence document reports below - this finding is disclosed for
transparency, not swept aside.

## Full test run output

This is the controlling, authoritative run - against a freshly recreated
`web` container (clean `/dev/shm`, no accumulated browser-process state -
see the flakiness finding above) and the final, fully-cleaned repository
state (no stray duplicate files):

```text
$ docker compose -p m009a exec -T web pytest -q
2337 passed, 7 skipped, 1 xfailed, 788 warnings in 1684.24s (0:28:04)
[exit code 0]
```

(An earlier run, before two stray duplicate files - `questionnaire/
m009a_ingestion_corpus.py` and `questionnaire/test_m009a_security_gate.py`,
both artefacts of an intermediate `scp` mistake during this dispatch, cleaned
up well before any commit - were removed, reported `2358 passed`; the
difference is fully accounted for by that cleanup, not by any missing
coverage. Every M009A-specific test file and the M005 corpus were also
independently re-confirmed passing standalone after the cleanup, below.)

Broken out by the files this Work Order added/touches most directly, run
together standalone for a focused read (all also included in the full
run above):

```text
$ docker compose -p m009a exec -T web pytest \
    questionnaire/tests/test_m009a_models.py \
    questionnaire/tests/test_m009a_storage.py \
    questionnaire/tests/test_m009a_security_gate.py \
    questionnaire/tests/test_m009a_extraction.py \
    questionnaire/tests/test_m009a_scanner.py \
    questionnaire/tests/test_m009a_import_services.py \
    questionnaire/tests/test_m009a_views.py \
    questionnaire/tests/test_m009a_entitlement.py \
    questionnaire/tests/test_m009a_browser_acceptance.py \
    organisations/tests/test_m009a_reset_reconciliation.py \
    questionnaire/tests/test_eval_harness.py \
    questionnaire/tests/test_eval_golden_corpus.py \
    questionnaire/tests/test_eval_command.py \
    -q
155 passed, 16 warnings in 79.77s (0:01:19)
```

(the last three files are the M005 14-case golden corpus - unchanged,
confirmed still GREEN alongside the new M009A corpus in the same run; the
first ten files are entirely new M009A test files, including the 3 real-
ClamAV scanner tests and the 4 real-Chromium browser acceptance tests at
1280/768/375px.)

$ docker compose -p m009a exec -T web python manage.py makemigrations --check --dry-run
No changes detected

$ gitleaks detect --source=. -v --redact   (after committing)
no leaks found

$ pip-audit -r requirements.txt
No known vulnerabilities found

$ trivy image --severity CRITICAL,HIGH --ignore-unfixed <this repo's own built image>
0 vulnerabilities (openpyxl/defusedxml/et-xmlfile included, matches pre-M009A baseline)
```

The 7 skips are pre-existing and unrelated to M009A: 6 in
`core/tests/test_production_config.py` and 1 in `core/tests/
test_static_files.py`, each with an explicit, documented reason
(DJANGO_ENV=production-conditional settings read once at settings-module
import time, or a real `collectstatic`-populated STATIC_ROOT, neither of
which this disposable `DJANGO_ENV=test` stack provides - each test's own
skip message names the exact alternative run procedure and the pre-
existing evidence document that already carries its real-stack proof).
The 1 xfail is also pre-existing and unrelated to M009A.
