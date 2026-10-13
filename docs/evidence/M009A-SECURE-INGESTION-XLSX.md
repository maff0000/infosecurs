# M009A — Secure Questionnaire Artifact Ingestion + XLSX Normalisation/Provenance

**Work Order:** `docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Branch:** `wo/M009A-work-order` (base `4fe38b91bde5e859d19da8a9a1c489ccc3cb7f41`)
**PR:** `#102` (`https://github.com/maff0000/infosecurs/pull/102`, base `main`@`93acc86405597641c46b050dd603ab335ebb60d1`)
**Status:** Implementer-complete, PR #102 opened, Central Architecture
independently reviewed PR #102 and required three bounded blocking
corrections plus two documentation corrections (2026-10-11) - see
"Central Architecture independent-review corrections (2026-10-11)" below
for the full account of what changed and why. Of those three blockers,
Blocker 2 (the pinned ClamAV runtime image) was STOPPED on 2026-10-11
pending an Architect ruling; the Architect has now ruled and Blocker 2 is
RESOLVED 2026-10-12 - see "Blocker 2 — RESOLVED 2026-10-12" below. This
document now describes the fully corrected state on top of the original
six implementation commits - still awaiting fresh Delivery Controller
re-review, fresh Independent Audit, Architect Acceptance, merge.

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
host. The Blocker 2 resolution pass (2026-10-12, see below) found the
`m009a` project still up from the prior correction pass and so used a
further distinct disposable project name, `m009ab2fix` (`WEB_HOST_PORT=
19000`, `POSTGRES_HOST_PORT=19534`) — again never `infosecurs-relocation`
and never colliding with `m009a` or any other stack already running on
the host.

## Central Architecture independent-review corrections (2026-10-11)

Central Architecture independently reviewed PR #102 after the original
six implementation commits (`b13e8aa`..`a810a8f`) and found it
substantively strong but required three bounded blocking corrections plus
two documentation corrections before merge. This dispatch covers exactly
those five corrections against worktree HEAD `a810a8f736a7ea82736eff1dcd
9054dc9f911504` (confirmed via `git rev-parse HEAD` before any change was
made) - no ingestion architecture was reopened, no re-upload/supersession
UI was added, and no M009B/C/D/E work was started.

### Blocker 1 — `supersedes` made real and tenant-safe (service-layer only)

**Finding:** `ingest_questionnaire_import(...)` accepted a `supersedes=`
kwarg, but nothing validated it belonged to the same organisation as the
new import, and no test proved the actual supersession contract.

**Architect's explicit ruling, followed literally:** no re-upload/
supersession UI was added. The upload UI remains exactly as minimal as it
was before this correction (upload → security gate → extraction/status).
`questionnaire/views.py`'s `questionnaire_import_upload` view still never
passes `supersedes=` to the service - it is not reachable from any
product surface today, exactly as before.

**Fix** (`questionnaire/import_services.py`): a new `_validate_supersedes_
target(supersedes, organisation)` helper, called at the very top of
`ingest_questionnaire_import` - before any bytes are streamed/stored and
before any `QuestionnaireImport` row is created. It runs a single,
combined `QuestionnaireImport.objects.filter(pk=supersedes.pk,
organisation=organisation).exists()` query (never trusting the caller's
in-memory `supersedes.organisation_id` attribute alone) and raises the
existing `questionnaire.models.QuestionnaireImportValidationError` if the
reference does not resolve - which `questionnaire/views.py` already
imports and catches around this exact call site, so the error-handling
path required zero view changes.

A real, non-theoretical edge case was found and fixed during this
dispatch's own verification: `QuestionnaireImport.id` is a
`UUIDField(default=uuid.uuid4)`, so an UNSAVED in-memory instance already
has a non-`None` `.pk` before `.save()` is ever called - an initial `if
supersedes.pk is None` check would NOT have detected an unpersisted
reference. Confirmed by writing
`TestSupersedesContract::test_supersedes_an_unpersisted_import_fails_
closed`, watching it fail with a database-level `IntegrityError` on a
dangling `supersedes_id` foreign key (the naive check let the row through),
and fixing the guard to do a real DB-scoped existence check instead - the
version now committed.

**New test** (`questionnaire/tests/test_m009a_import_services.py::
TestSupersedesContract`, 3 tests, all GREEN), proving the full contract
step by step exactly as required:

1. ingests a legitimate original workbook (`corpus.valid_multi_sheet_
   workbook()`), reaching `security_gate_status=passed`/`status=extracted`;
2. records its row id, `sha256_hash`, the stored bytes read directly off
   disk, and the full set of its extracted `QuestionnaireImportQuestion`
   ids/texts - BEFORE the second ingest touches anything;
3. ingests a second, distinct legitimate workbook
   (`corpus.workbook_with_duplicate_question_text()`) with
   `supersedes=<first import>`;
4. proves two distinct `QuestionnaireImport` rows now exist
   (`QuestionnaireImport.objects.filter(organisation=org_a).count() == 2`);
5. proves `second.supersedes_id == first.id`;
6. re-reads the first import's row from the DB and its stored bytes from
   disk (not merely the DB hash field) and proves both, plus every one of
   its extracted questions (ids and texts), are byte-for-byte/row-for-row
   unchanged after the second ingest;
7. a second test proves that `supersedes` pointing at an import belonging
   to a DIFFERENT organisation (`org_b`) raises
   `QuestionnaireImportValidationError` and that the WHOLE ingest attempt
   fails closed for `org_a` - no new `QuestionnaireImport` row is created
   at all (never a degraded success with `supersedes` silently landing as
   `NULL`), no file is left orphaned on disk, and no
   `QuestionnaireImport` anywhere ends up with `supersedes` pointing at
   the foreign row; a third test proves an unpersisted `supersedes`
   reference is rejected the same way.

All three tests pass against the real pipeline (real fake-scanner-backed
gate, real extraction, real storage) - see "Full test run output" below.

**Linked-supersession UX is deliberately deferred, not forgotten:** the
domain/service contract this evaluation-corpus item requires is now
proven end to end; a future Work Order may add an actual re-upload/
"supersede this import" control to the Customer Assurance UI, but M009A
itself adds none, per Central Architecture's explicit ruling above.

### Blocker 2 — ClamAV 1.4.6 evaluation: ~~STOPPED, pin unchanged, finding reported~~ SUPERSEDED 2026-10-12

**SUPERSEDED 2026-10-12 — do not treat this section as the final state.**
Everything below in this section is left fully intact, byte-for-byte, as
the real, true account of what this dispatch found and did on 2026-10-11
— nothing here is deleted or rewritten. The Architect has since ruled on
the open question this section raised, and a fresh, independent
re-resolution superseded this STOP; see "Blocker 2 — RESOLVED 2026-10-12"
immediately below this section for the current, controlling state. In
short: the `clamav/clamav:1.4.6` tag is a floating tag and moved between
2026-10-11 and 2026-10-12 — the digest this section recorded
(`sha256:57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23`)
genuinely scored 1 fixable HIGH on 2026-10-11 exactly as reported; a later,
different build published under the same `1.4.6` tag
(`sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`)
is what the Architect's required fresh re-resolution found on 2026-10-12,
and it is genuinely clean. Both findings are true of their respective
digests at their respective times; neither contradicts the other.

**Finding:** the current pin, `clamav/clamav:1.4.4@sha256:a52f45e427
53dca691b6c9fd09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3`, is stale -
1.4.5 and 1.4.6 both shipped security fixes, and 1.4.6 is the current LTS
patch.

**What was actually done, live, on dell-debian (no fabricated digest):**

```text
$ docker pull clamav/clamav:1.4.6
Digest: sha256:57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23

$ docker inspect --format '{{index .RepoDigests 0}}' clamav/clamav:1.4.6
clamav/clamav@sha256:57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23
```

So the real, resolved candidate reference is `clamav/clamav:1.4.6@sha256:
57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23`.

**Trivy scan of the exact candidate image** (`aquasec/trivy:0.70.0 image
--severity CRITICAL,HIGH --ignore-unfixed`, this repo's own existing
`security/container` invocation style):

```text
Total: 1 (HIGH: 1, CRITICAL: 0)

Library  Vulnerability    Severity  Status  Installed  Fixed     Title
pcre2    CVE-2026-103111  HIGH      fixed   10.48-r0   10.49-r0  pcre2: Out-of-bounds
                                                                   write via crafted
                                                                   regular expression
```

This is a genuine FIXABLE HIGH finding (`Status: fixed`, a newer package
version exists) on the real, current official `1.4.6` tag. Per this
dispatch's own explicit instruction - "If the real, current official
1.4.6 image still reports any fixable CRITICAL or HIGH finding: STOP this
specific sub-task... Do not create an undocumented exception" - **this
sub-task is STOPPED.** `docker-compose.yml`/`docker-compose.release.yml`
are UNCHANGED by this correction: the pin remains `clamav/clamav:1.4.4@
sha256:a52f45e42753dca691b6c9fd09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3`.
No different/undocumented image tag was substituted, and no ad-hoc
overlay (of the kind `docs/delivery/BUILD-REPRODUCIBILITY.md`'s
"Temporary exact-version security overlay" section documents as a
Central-Architecture-authorised exception for the Python base image) was
invented unilaterally for ClamAV - that pattern exists and could in
principle apply here, but authorising a NEW overlay is an Architecture
decision this Implementer dispatch is not authorised to make on its own.

**For context, re-verified live in the same pass** (not from memory - a
fresh scan of the currently-pinned digest, same Trivy invocation):

```text
$ docker pull clamav/clamav@sha256:a52f45e42753dca691b6c9fd09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3
(already up to date)

Total: 15 (HIGH: 15, CRITICAL: 0)
  c-ares (CVE-2026-33630), libcrypto3/libssl3 (CVE-2026-14456), libcurl x7
  (CVE-2026-11352/11586/12064/8286/8458/8925/9547), pcre2 x4
  (CVE-2026-103111/86145/89157/89161) - all Status: fixed.
```

So the currently-pinned `1.4.4` image carries 15 pre-existing fixable
HIGH findings (0 CRITICAL) that were already disclosed in this document's
earlier revision but were never wired into CI (see Blocker 3 below - that
gap is now closed, with a real consequence disclosed there). `1.4.6`
would have been a strict improvement (15 → 1 HIGH) but is not itself
clean, and this dispatch's own governing instruction requires a STOP
rather than accepting "better but not clean" as a silent decision. This
is returned to Central Architecture/Delivery Controller as an open
question: either author an Architecture-governed temporary overlay (same
shape as the existing Python-base-image precedent) for whichever
individual package(s) remain unfixed on the best available official tag,
or accept the residual risk explicitly and documented, or hold M009A's
ClamAV pin at a decision point until upstream publishes a fully clean
tag. No outcome was chosen unilaterally here.

Because the pin is unchanged, the scanner topology itself (no published
port, healthcheck, FreshClam, `CLAMAV_HOST=clamav` wiring,
`UnavailableScanner` fail-closed-when-unset behaviour) is byte-identical
to before this dispatch - re-confirmed, not re-invented: `docker compose
-p m009a ps` shows `m009a-clamav-1` exposing `3310/tcp, 7357/tcp` with NO
host-port mapping, and `questionnaire/tests/test_m009a_scanner.py::
TestRealClamdBackend` (`test_ping`/`test_legitimate_xlsx_is_clean`/
`test_eicar_test_file_is_detected`) was re-run against the real, unchanged
`clamav` service in a freshly recreated disposable `m009a` stack and all
3 still pass for real (see "Full test run output" below) - this dispatch
did not merely assume the existing proof still held, it re-ran it.

### Blocker 2 — RESOLVED 2026-10-12 (Architect ruling + fresh re-resolution, overlay NOT needed)

**Architect's ruling** on the open question the STOPPED section above
returned: re-resolve upstream fresh (never trust any cached/previously-
recorded digest) before building any overlay; if a current official tag
is already 0 CRITICAL/0 HIGH, pin that directly — no overlay required.

**Fresh re-resolution, done live on dell-debian for this correction pass
(no fabricated or memorised digest — independently re-pulled and
re-scanned by this Implementer dispatch, not merely taken from the
Delivery Controller's own re-resolution immediately preceding it):**

```text
$ docker pull clamav/clamav:1.4.6
Digest: sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469
Status: Image is up to date for clamav/clamav:1.4.6

$ docker image inspect clamav/clamav:1.4.6 --format '{{.RepoDigests}}'
[clamav/clamav@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469]
```

This is a DIFFERENT, newer digest than the one the STOPPED section above
recorded for the same `1.4.6` tag on 2026-10-11
(`sha256:57deb108fc4c72778aa83eafbca7bb7153e28c3f57c005afd38d31f16da86f23`)
— direct, mechanical confirmation that the tag is floating and has moved,
exactly as the Architect's instruction anticipated it might.

**Version/OS facts confirmed inside the new digest, live:**

```text
$ docker run --rm clamav/clamav:1.4.6@sha256:b5b910ce... clamscan --version
ClamAV 1.4.6/28150/Sun Oct 11 06:26:01 2026

$ cat /etc/alpine-release
3.24.2

$ cat /etc/apk/repositories
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community

$ apk policy pcre2
pcre2 policy:
  10.49-r0:
    lib/apk/db/installed
    https://dl-cdn.alpinelinux.org/alpine/v3.24/main
```

`pcre2` — the exact package that carried the one fixable HIGH on the
2026-10-11 digest (`CVE-2026-103111`, fixed in `10.49-r0`) — is already at
`10.49-r0` on this new digest, sourced from the image's own stable `v3.24/
main` repository (no edge repo added, no manual package pin needed).

**Fresh Trivy scan of the exact new digest** (`aquasec/trivy:0.70.0 image
--severity CRITICAL,HIGH --ignore-unfixed`, this repo's own existing
`security/container` invocation style — identical tool, identical
version, identical flags to every prior scan in this document):

```text
$ trivy image --severity CRITICAL,HIGH --ignore-unfixed \
    clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469

Report Summary
┌────────────────────────────────────────────┬────────┬─────────────────┐
│ Target                                      │  Type  │ Vulnerabilities │
├────────────────────────────────────────────┼────────┼─────────────────┤
│ clamav/clamav:1.4.6@sha256:b5b910ce... (alpine 3.24.2) │ alpine │        0        │
└────────────────────────────────────────────┴────────┴─────────────────┘
Legend: '0' = Clean (no security findings detected)
```

**0 CRITICAL / 0 HIGH — genuinely clean.** Per the Architect's ruling,
this is pinned directly:
`docker-compose.yml`/`docker-compose.release.yml`'s `clamav` service
`image:` line is now
`clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`
— no `Dockerfile.clamav`, no derived/overlay image of any kind was built.
**The obligation note the STOPPED section above carried forward** (echoing
`docs/delivery/BUILD-REPRODUCIBILITY.md`'s "temporary exact-version
security overlay" precedent — "re-pin once ClamAV publishes a genuinely
clean tag") **no longer applies and is explicitly retired here**: no
overlay was ever built for ClamAV, so there is nothing to later replace —
a future reader should not go looking for a `Dockerfile.clamav` that was
never created. The scanner topology itself (no published port,
healthcheck, FreshClam, `CLAMAV_HOST=clamav` wiring, `UnavailableScanner`
fail-closed-when-unset behaviour) is otherwise byte-identical to before —
only the `image:` line's tag and digest changed, in both compose files,
identically. Full re-proof (scanner health/ping/CLEAN/INFECTED, drift
guard, `makemigrations --check`, full suite) against the new pinned image
is in "Full test run output — Blocker 2 resolution correction pass
(2026-10-12)" below.

### Blocker 3 — ClamAV image now enters the durable container CI gate

`.github/workflows/security.yml`'s `security/container` job previously
only built+scanned the INFOSECURS application image. It now ALSO scans
the exact pinned ClamAV image, resolved directly from
`docker-compose.yml` (never a hand-copied literal that could drift out of
sync with the real pin) via a new `Resolve pinned ClamAV image reference`
step, then a second, independent `aquasecurity/trivy-action` step at the
identical pinned Trivy version (`v0.70.0`), identical severity gate
(`CRITICAL,HIGH`), identical `--ignore-unfixed` policy, and identical
fail-the-job-on-findings discipline (`exit-code: "1"`) as the existing
application-image scan - which is completely unmodified, not weakened in
any way.

**A real, disclosed consequence, not a silent one:** because Blocker 2's
ClamAV version bump was STOPPED (see above) and the currently-pinned
`1.4.4` image carries 15 pre-existing fixable HIGH findings, enabling
this new gate means `security/container` WILL fail on its next real
GitHub Actions run against this exact pin, until Central Architecture
resolves the open question left at the end of Blocker 2 (an authorised
temporary overlay, an accepted/documented residual-risk exception, or a
revisited pin decision). This Implementer dispatch deliberately did NOT
weaken the new gate's severity/ignore-unfixed/exit-code settings to avoid
that outcome - doing so would have been exactly the kind of "silently
decide it's acceptable" response this dispatch's own instructions
prohibit. Flagging this plainly for Delivery Controller/Architect
decision, consistent with this evidence document's own established
practice of disclosing real findings rather than engineering around them
unilaterally (see the pre-existing "CI wiring" and "A verification-
environment flakiness finding" sections below, both carried over
unchanged from the original dispatch).

**RESOLVED 2026-10-12** — this paragraph's predicted consequence is now
moot, not realised: Blocker 2 is no longer STOPPED (see "Blocker 2 —
RESOLVED 2026-10-12" above). The pin is now the genuinely clean
`clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`,
so `security/container`'s next real GitHub Actions run will scan a 0
CRITICAL/0 HIGH image and pass, not fail. This paragraph is left intact
because it was a true, honest prediction at the time it was written — it
is simply superseded by the Architect's subsequent ruling and the fresh
re-resolution that followed it.

**Drift guard** (new `questionnaire/tests/test_m009a_clamav_image_pin.py`,
wired into `.github/workflows/ci.yml`'s `ci/unit` job): a small,
dependency-free regex-based check (deliberately no new YAML-parsing
dependency for this alone) proving `docker-compose.yml` and
`docker-compose.release.yml` declare the IDENTICAL digest-pinned
`clamav/clamav` image reference, and that neither ever regresses to a
floating `latest`/`stable` tag. 3/3 tests pass (see "Full test run
output" below).

### Governance correction — stale Work Order status sentence fixed

`docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`'s header already
correctly said `ARCHITECT ACCEPTED — AUTHORISED FOR DELIVERY CONTROLLER
DISPATCH` and carried the durable Architect Acceptance record at the
bottom, but its FINAL sentence still read "This Work Order is DRAFT. No
Implementer may be dispatched against it until the Architect accepts
it." - stale and self-contradicting the rest of the document. Corrected,
in a new commit, to state the document's governance state unambiguously
(accepted; implementation in progress/under correction). No historical
commit was rewritten or deleted.

### Evidence correction — this document

This section, plus the targeted updates elsewhere in this document
(status line above; "Dependency / licence / build-reproducibility
evidence" below now records the 1.4.6 evaluation and STOP; "Full test run
output" below now records this correction pass's real run), reconcile
this evidence document to the actual final state - without erasing any
of the original dispatch's real history (the original "CI wiring" gap
disclosure, the real upload-form/CSRF-middleware-ordering bug found and
fixed, and the `/dev/shm` browser-flakiness finding below are all
UNCHANGED, because they are still true and still happened).

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

**Added 2026-10-11 (Central Architecture independent-review corrections
to PR #102 — see that section above for the full account):**

- `questionnaire/import_services.py` — new `_validate_supersedes_target`
  fail-closed tenant guard, called first inside
  `ingest_questionnaire_import` (Blocker 1).
- `questionnaire/tests/test_m009a_import_services.py` — new
  `TestSupersedesContract` (3 tests): the full same-organisation
  supersession contract, the cross-organisation rejection, and the
  unpersisted-reference rejection (Blocker 1).
- `questionnaire/tests/test_m009a_clamav_image_pin.py` — new drift guard
  proving `docker-compose.yml`/`docker-compose.release.yml` pin the
  identical ClamAV image digest (Blocker 3).
- `.github/workflows/security.yml` — `security/container` now also scans
  the exact pinned ClamAV image (Blocker 3).
- `.github/workflows/ci.yml` — the new drift-guard test wired into
  `ci/unit`'s curated list.
- `docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md` — one stale
  sentence corrected (governance correction).
- `docs/evidence/M009A-SECURE-INGESTION-XLSX.md` — this document,
  reconciled (evidence correction).
- `docker-compose.yml`/`docker-compose.release.yml` — deliberately
  **UNCHANGED** (Blocker 2 STOPPED — see above).

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

**Re-confirmed 2026-10-11** (Central Architecture independent-review
correction pass): since Blocker 2's version bump was STOPPED (the ClamAV
pin is unchanged), this proof was re-run, not merely assumed still valid,
against a freshly recreated disposable `m009a` stack - `docker compose -p
m009a ps` showed `m009a-clamav-1` exposing `3310/tcp, 7357/tcp` with no
host-port mapping, and all three `TestRealClamdBackend` tests passed
again for real (`test_ping`, `test_legitimate_xlsx_is_clean`,
`test_eicar_test_file_is_detected`).

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
  anything this Work Order's own code introduces).
  ~~are NOT currently covered by this repository's `security/container`
  CI job~~ **CORRECTED 2026-10-11 (Central Architecture independent
  review, Blocker 3):** this is now wired into `security/container` (see
  "Central Architecture independent-review corrections" above) - the gap
  is closed, not merely flagged, though the real consequence is that the
  job will now fail against these 15 pre-existing findings until
  Architecture resolves that separately (see Blocker 3 above for the full
  account; this struck-through sentence is left visible deliberately so
  the historical state - what this evidence said before the correction -
  remains legible rather than silently vanishing). The `postgres` image
  is still not scanned by this CI job, for the same unchanged "we don't
  rebuild this, upstream owns its own patch cadence" reasoning - that
  reasoning was never in question for `postgres`, only ClamAV's own
  scanning coverage was the finding.
  **Also re-evaluated 2026-10-11:** `1.4.6` (the current LTS patch) was
  pulled and scanned live - resolved digest `sha256:57deb108fc4c72778aa
  83eafbca7bb7153e28c3f57c005afd38d31f16da86f23` - scoring 0 CRITICAL / 1
  HIGH (`CVE-2026-103111`/`pcre2`, `Status: fixed`). Per this dispatch's
  own governing instruction, ANY fixable CRITICAL/HIGH on the real
  current official tag is a STOP condition, so the pin was NOT advanced
  to `1.4.6` despite it being a strict improvement over `1.4.4` (15 HIGH
  → 1 HIGH) - see "Central Architecture independent-review corrections"
  above for the full finding and the open question returned to Central
  Architecture/Delivery Controller. ~~The obligation to re-pin once ClamAV
  publishes a genuinely clean tag ... remains open and is now sharper:
  `1.4.6` is close but not yet clean.~~ **RESOLVED 2026-10-12:** the
  Architect ruled that a fresh re-resolution (never trusting a cached
  digest) must be done before building any overlay, and that a current
  official tag already at 0 CRITICAL/0 HIGH should be pinned directly. A
  fresh `docker pull clamav/clamav:1.4.6` on 2026-10-12 resolved to a
  DIFFERENT, newer digest than the one recorded immediately above —
  `sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`
  (the `1.4.6` tag is floating and had moved) — `clamscan --version`
  reports `ClamAV 1.4.6/28150/Sun Oct 11 06:26:01 2026`, Alpine
  `3.24.2`, and `apk policy pcre2` shows the installed `pcre2` is already
  `10.49-r0` from the image's own stable `v3.24/main` repo (the exact
  package/version that carried the sole HIGH finding above). A fresh
  Trivy scan of this exact new digest
  (`aquasec/trivy:0.70.0 image --severity CRITICAL,HIGH --ignore-unfixed`)
  reports **0 vulnerabilities total** — genuinely clean. Per the
  Architect's ruling this is pinned DIRECTLY, with no overlay:
  `docker-compose.yml`/`docker-compose.release.yml` now pin
  `clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`.
  No `Dockerfile.clamav` or any derived scanner image exists in this
  repository — none was needed. See "Blocker 2 — RESOLVED 2026-10-12"
  above for the full account and re-proof.
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

## Full test run output (original dispatch, 2026-10-10)

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

## Full test run output — correction pass (2026-10-11)

Built and verified on dell-debian inside the SAME disposable `m009a`
Compose stack discipline as the original dispatch (project name `m009a`,
`WEB_HOST_PORT=18900`, `POSTGRES_HOST_PORT=18901`) - never
`infosecurs-relocation` (port 8884) and never any other stack already
running on that host. Confirmed worktree `git rev-parse HEAD` ==
`a810a8f736a7ea82736eff1dcd9054dc9f911504` before any change was made.

```text
$ git rev-parse HEAD
a810a8f736a7ea82736eff1dcd9054dc9f911504   (confirmed BEFORE any change)
```

**New/changed tests, M009A-focused run** (Blocker 1's new
`TestSupersedesContract`, plus the rest of the service-layer suite that
exercises the same code path):

```text
$ docker compose -p m009a exec -T web pytest -q questionnaire/tests/test_m009a_import_services.py
15 passed in 16.10s
```

**New drift-guard test standalone:**

```text
$ docker compose -p m009a exec -T web pytest -q questionnaire/tests/test_m009a_clamav_image_pin.py
3 passed in 0.07s
```

**Full M009A evaluation corpus + M005 14-case golden corpus together**
(non-browser; the browser-dependent M009A acceptance tests are covered in
the full-suite run below, together with every other browser test in the
repository, for a single controlling browser-environment proof):

```text
$ docker compose -p m009a exec -T web pytest -q \
    questionnaire/tests/test_m009a_models.py \
    questionnaire/tests/test_m009a_storage.py \
    questionnaire/tests/test_m009a_security_gate.py \
    questionnaire/tests/test_m009a_extraction.py \
    questionnaire/tests/test_m009a_scanner.py \
    questionnaire/tests/test_m009a_import_services.py \
    questionnaire/tests/test_m009a_views.py \
    questionnaire/tests/test_m009a_entitlement.py \
    organisations/tests/test_m009a_reset_reconciliation.py \
    questionnaire/tests/test_eval_harness.py \
    questionnaire/tests/test_eval_golden_corpus.py \
    questionnaire/tests/test_eval_command.py
154 passed in 55.75s
```

(the last three files are the M005 14-case golden corpus - still
byte-for-byte untouched by this correction pass, still GREEN.)

**Real ClamAV scanner re-proof** (Blocker 2 STOPPED - pin unchanged -
re-run, not merely assumed, against the real, unchanged `clamav` 1.4.4
service):

```text
$ docker compose -p m009a exec -T web pytest questionnaire/tests/test_m009a_scanner.py -v
TestUnavailableScanner::test_always_returns_unavailable_never_clean PASSED
TestUnavailableScanner::test_ping_is_false PASSED
TestGetScannerFailsClosedOnAbsence::test_no_clamav_host_returns_unavailable_stub PASSED
TestClamdScannerConnectionFailure::test_unreachable_host_returns_unavailable_not_exception PASSED
TestRealClamdBackend::test_ping PASSED
TestRealClamdBackend::test_legitimate_xlsx_is_clean PASSED
TestRealClamdBackend::test_eicar_test_file_is_detected PASSED
7 passed in 0.31s
```

`docker compose -p m009a ps` at the time: `m009a-clamav-1` exposes
`3310/tcp, 7357/tcp` with NO host-port mapping - confirmed, not merely
unchanged by assumption.

**`makemigrations --check --dry-run`:**

```text
$ docker compose -p m009a exec -T web python manage.py makemigrations --check --dry-run
No changes detected
```

**`pip-audit`** (installed into this disposable container's writable
layer for this check - the repository's own application image never
bakes in pip-audit; no `requirements.txt`/`requirements.in` change was
made by this correction pass, so this re-confirms the existing-dependency
baseline rather than evaluating anything new):

```text
$ pip-audit -r requirements.txt
No known vulnerabilities found
```

**Application image Trivy scan** (re-built from this corrected worktree -
no dependency changed by this correction pass, confirming the existing
baseline is unaffected):

```text
$ docker build -t infosecurs:m009a-dispatch .
$ trivy image --severity CRITICAL,HIGH --ignore-unfixed infosecurs:m009a-dispatch
0 vulnerabilities   (matches the pre-correction baseline exactly)
```

**ClamAV runtime image Trivy scan** - see "Central Architecture
independent-review corrections" above for the full finding: the currently
-pinned `1.4.4` image (`clamav/clamav:1.4.4@sha256:a52f45e42753dca691b6c9f
d09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3`) scores **15 HIGH / 0
CRITICAL** (all `Status: fixed`); the evaluated-but-not-pinned `1.4.6`
candidate (`clamav/clamav:1.4.6@sha256:57deb108fc4c72778aa83eafbca7bb7153
e28c3f57c005afd38d31f16da86f23`) scores **1 HIGH / 0 CRITICAL**
(`CVE-2026-103111`/`pcre2`, `Status: fixed`) - a real, fixable finding on
the current official tag, which is this correction pass's own STOP
condition. Reported in full above, not summarised away.

**Full repository test suite** - the controlling, authoritative run for
this correction pass, against a freshly recreated `web` container (clean
`/dev/shm`, Chromium reinstalled fresh, mirroring the exact remediation
procedure the original dispatch's own "A verification-environment
flakiness finding" section above already documents for this same shared,
loaded host):

```text
$ docker compose -p m009a exec -T web pytest -q
2343 passed, 7 skipped, 1 xfailed, 788 warnings in 1633.40s (0:27:13)
[exit code 0]
```

**A verification-environment flakiness finding, disclosed, not hidden**
(this correction pass's own occurrence of the SAME class the original
dispatch's own evidence already documents above): the FIRST full-suite
run attempted during this correction pass, against the `m009a-web-1`
container that had already been up for a while (real backup/restore
proof, Trivy builds, and several preceding targeted test runs all ran in
it first), reported **49 failed, 2294 passed, 7 skipped, 1 xfailed** in
1462.19s - every single one of the 49 failures was a real-Chromium
browser test (this dispatch's own new/re-run `questionnaire/tests/
test_m009a_browser_acceptance.py` tests, PLUS pre-existing, unrelated
browser tests across `core`/`evidence`/`key_assets`/`organisations`/
`remediation`/`risk_register` - e.g. `test_wi6_sidebar_drawer_
acceptance.py`, `test_narrow_viewport_regression.py`). `free -h` at the
time showed swap 975Mi/975Mi (100%) full - the same symptom the original
dispatch's own flakiness finding names. Zero non-browser test failed in
that run, and zero of the 49 failing tests touch any file this correction
pass changed. Applying the SAME remediation the original dispatch's
evidence already documents for this exact failure class - `docker
compose -p m009a stop web && rm -f web && up -d web`, then `playwright
install --with-deps chromium` into the fresh container's writable layer -
and re-running the FULL suite produced the clean result above: **0
failed**. This is reported as a real, recurring characteristic of
sustained browser-test load on this shared, loaded host (54+ other
containers running concurrently), not a defect in any code this
correction pass touched.

**Controlling, authoritative result for this correction pass: 2343
passed, 7 skipped, 1 xfailed, 0 failed.** The skip/xfail counts and
reasons are identical to the original dispatch's own documented set
(6 in `core/tests/test_production_config.py`, 1 in `core/tests/
test_static_files.py`, 1 pre-existing xfail) - unaffected by this
correction pass. The pass count (2343) is 6 higher than the original
dispatch's own controlling run (2337): 3 new `TestSupersedesContract`
tests (Blocker 1) + 3 new `TestClamavImagePinDriftGuard` tests (Blocker
3) = 6, fully accounted for.

## Full test run output — Blocker 2 resolution correction pass (2026-10-12)

Architect ruling implemented: re-resolve upstream `clamav/clamav`
fresh, pin a current official tag directly if it is already 0
CRITICAL/0 HIGH, no overlay. Built and verified on dell-debian inside a
NEW disposable Compose stack, project name `m009ab2fix` (`WEB_HOST_PORT=
19000`, `POSTGRES_HOST_PORT=19534`) - distinct from the still-running
`m009a` project left up from the prior correction pass, and never
`infosecurs-relocation` (port 8884) or any other stack already running on
the host. Worktree `git rev-parse HEAD` confirmed at
`86d83bfa8f3218115ff926c7dd1d1bcac70e6649` before any change in this
pass was made.

**Fresh digest re-resolution (independently re-pulled and re-scanned by
this Implementer dispatch, not merely trusted from the Delivery
Controller's own immediately-preceding re-resolution):**

```text
$ docker pull clamav/clamav:1.4.6
Digest: sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469

$ docker image inspect clamav/clamav:1.4.6 --format '{{.RepoDigests}}'
[clamav/clamav@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469]

$ docker run --rm clamav/clamav:1.4.6@sha256:b5b910ce... clamscan --version
ClamAV 1.4.6/28150/Sun Oct 11 06:26:01 2026

$ cat /etc/alpine-release
3.24.2

$ cat /etc/apk/repositories
https://dl-cdn.alpinelinux.org/alpine/v3.24/main
https://dl-cdn.alpinelinux.org/alpine/v3.24/community

$ apk policy pcre2
pcre2 policy:
  10.49-r0:
    lib/apk/db/installed
    https://dl-cdn.alpinelinux.org/alpine/v3.24/main
```

**Fresh Trivy scan of the exact new digest**
(`aquasec/trivy:0.70.0 image --severity CRITICAL,HIGH --ignore-unfixed`):

```text
Report Summary
┌────────────────────────────────────────────────────────┬────────┬─────────────────┐
│ Target                                                  │  Type  │ Vulnerabilities │
├────────────────────────────────────────────────────────┼────────┼─────────────────┤
│ clamav/clamav:1.4.6@sha256:b5b910ce... (alpine 3.24.2)  │ alpine │        0        │
└────────────────────────────────────────────────────────┴────────┴─────────────────┘
0 vulnerabilities total - genuinely clean.
```

**Compose re-pin** (both topologies, no other line changed):

```diff
--- a/docker-compose.yml
+++ b/docker-compose.yml
-    image: clamav/clamav:1.4.4@sha256:a52f45e42753dca691b6c9fd09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3
+    image: clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469

--- a/docker-compose.release.yml
+++ b/docker-compose.release.yml
-    image: clamav/clamav:1.4.4@sha256:a52f45e42753dca691b6c9fd09fe68d6ca9ac22fa8cd6a8a45d9237e188049e3
+    image: clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469
```

**Disposable stack brought up against the new pin:**

```text
$ docker compose -p m009ab2fix -f docker-compose.yml up -d --build
...
Container m009ab2fix-db-1       Healthy
Container m009ab2fix-clamav-1   Healthy
Container m009ab2fix-web-1      Started

$ docker compose -p m009ab2fix ps
m009ab2fix-clamav-1   clamav/clamav:1.4.6@sha256:b5b910ce...   Up (healthy)   3310/tcp, 7357/tcp
m009ab2fix-db-1       postgres:16.6-alpine@sha256:1d04b9ba...  Up (healthy)   127.0.0.1:19534->5432/tcp
m009ab2fix-web-1      m009ab2fix-web                            Up            127.0.0.1:19000->8000/tcp
```

`m009ab2fix-clamav-1` exposes `3310/tcp, 7357/tcp` with NO host-port
mapping - confirmed directly via `docker inspect
--format '{{json .NetworkSettings.Ports}}'`, both values `null`.

**clamd ping, both directly and over the internal Compose network as the
application itself reaches it:**

```text
$ docker exec m009ab2fix-clamav-1 sh -c 'echo PING | nc -w 2 localhost 3310'
PONG

$ docker exec m009ab2fix-web-1 python -c "
import socket
s = socket.create_connection(('clamav', 3310), timeout=5)
s.sendall(b'PING\n'); print(s.recv(100)); s.close()"
b'PONG\n'
```

**Real scanner re-proof against the new image**
(`questionnaire/tests/test_m009a_scanner.py`):

```text
$ docker exec m009ab2fix-web-1 python -m pytest questionnaire/tests/test_m009a_scanner.py -v
TestUnavailableScanner::test_always_returns_unavailable_never_clean PASSED
TestUnavailableScanner::test_ping_is_false PASSED
TestGetScannerFailsClosedOnAbsence::test_no_clamav_host_returns_unavailable_stub PASSED
TestClamdScannerConnectionFailure::test_unreachable_host_returns_unavailable_not_exception PASSED
TestRealClamdBackend::test_ping PASSED
TestRealClamdBackend::test_legitimate_xlsx_is_clean PASSED
TestRealClamdBackend::test_eicar_test_file_is_detected PASSED
7 passed in 0.40s
```

All four scanner states are covered: `UNAVAILABLE` (no host set),
`UNAVAILABLE` on connection failure (fails closed, not an exception),
real `CLEAN` (legitimate XLSX against the real new clamd), and real
`INFECTED` (EICAR test string against the real new clamd) - each of
these is what `questionnaire/import_services.py`'s `security_gate_failed`
path depends on; that code is unchanged by this pass, and this re-run
proves it still behaves correctly against the new image, not merely
assumed.

**Drift guard re-run** (`questionnaire/tests/test_m009a_clamav_image_pin.py`):

```text
$ docker exec m009ab2fix-web-1 python -m pytest questionnaire/tests/test_m009a_clamav_image_pin.py -v
TestClamavImagePinDriftGuard::test_dev_and_release_compose_pin_the_identical_clamav_image PASSED
TestClamavImagePinDriftGuard::test_pinned_clamav_image_is_never_a_floating_tag[docker-compose.yml] PASSED
TestClamavImagePinDriftGuard::test_pinned_clamav_image_is_never_a_floating_tag[docker-compose.release.yml] PASSED
3 passed in 0.06s
```

Still passes unchanged, because both compose files still agree,
byte-for-byte, on one identical digest-pinned reference - now `1.4.6`/
`sha256:b5b910ce...` instead of `1.4.4`/`sha256:a52f45e4...`.

**`makemigrations --check --dry-run`** (rerun fresh for this final
candidate per the Architect's explicit requirement, not taken from any
earlier evidence document):

```text
$ docker exec m009ab2fix-web-1 python manage.py makemigrations --check --dry-run
No changes detected
```

**CI wiring re-confirmed, no code change needed:**
`.github/workflows/security.yml`'s `security/container` job's `Resolve
pinned ClamAV image reference` step runs `grep -oP
'clamav/clamav:\S+@sha256:[0-9a-f]{64}' docker-compose.yml` - a fully
generic pattern with no hand-copied tag/digest literal anywhere in the
workflow file. Rereading it against the new `docker-compose.yml` content
confirms it will resolve the new `1.4.6` pin automatically on its next
run; neither `.github/workflows/security.yml` nor `.github/workflows/
ci.yml` needed any change for this correction.

**Chromium pre-flight, done before the full suite** (this exact pitfall
is named in this document's own "A verification-environment flakiness
finding" above and bit this correction pass too, on the first check):

```text
$ docker exec m009ab2fix-web-1 python -c "from playwright.sync_api import sync_playwright; ..."
playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at
/root/.cache/ms-playwright/chromium_headless_shell-1243/.../chrome-headless-shell
[Playwright was just installed/updated; run `playwright install`]

$ docker exec m009ab2fix-web-1 python -m playwright install --with-deps chromium
Chrome for Testing 153.0.8010.12 (playwright chromium v1243) downloaded ...
Chrome Headless Shell 153.0.8010.12 (playwright chromium-headless-shell v1243) downloaded ...

$ docker exec m009ab2fix-web-1 python -c "from playwright.sync_api import sync_playwright; ..."
chromium-ok 153.0.8010.12
```

Host resource health checked at the same time: `free -h` showed `Mem:
62Gi total, 41Gi used, 2.5Gi free, 19Gi buff/cache, 20Gi available` and
`Swap: 975Mi total, 975Mi used, 0B free` (swap still fully saturated on
this shared, loaded host, the same symptom this document's existing
flakiness finding names), and the container's own `/dev/shm` was `64M,
0 used`. Despite swap being saturated, Chromium launched successfully
once genuinely installed - this pass's earlier Chromium failure was the
missing-binary pitfall, not the swap-saturation flakiness class.

**Full repository test suite, run once, no retry needed:**

```text
$ docker exec m009ab2fix-web-1 python -m pytest -q
2343 passed, 7 skipped, 1 xfailed, 1 warning in 1622.28s (0:27:02)
[exit code 0]
```

**Matches the controlling count exactly** (2343 passed, 0 failed, 7
skipped, 1 xfailed) - identical to the pre-existing controlling run on
this branch. No discrepancy to explain: unlike the prior correction
pass's own documented browser-flakiness occurrence (same class, "A
verification-environment flakiness finding" above), this run needed no
retry, because Chromium was proactively installed and confirmed
launchable before the full suite was started rather than after a failure
was first observed. The 1 warning (a `zipfile` `UserWarning: Duplicate
name: 'xl/workbook.xml'` from `TestRejectsHostileContainers::
test_duplicate_member_names_rejected`, a deliberately-crafted hostile
fixture exercising `security_gate.py`'s own duplicate-member-name
rejection) is pre-existing, expected, and unrelated to this correction.

**Controlling, authoritative result for the Blocker 2 resolution
correction pass: 2343 passed, 7 skipped, 1 xfailed, 0 failed** - identical
in every count to the pass/skip/xfail baseline this document already
established above; only the pinned ClamAV image changed.
