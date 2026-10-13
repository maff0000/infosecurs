# M009A — Closure

**Milestone:** M009A — Secure Questionnaire Artifact Ingestion + XLSX Normalisation/Provenance
**Parent PID:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md`
**Work Order:** `docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md`
**PR:** #102
**Merge SHA:** `ad996bfa4527623d095862199b46db6e0ea94fd0`
**Canonical main at closure:** `ad996bfa4527623d095862199b46db6e0ea94fd0`
**Architect decision:** **M009A — CLOSED GREEN** (2026-10-13)

This is the durable closure record for M009A, written and merged under normal governance after Central Architecture's `CLOSED GREEN` determination. It does not introduce or alter any product behaviour — it is a documentation-only record consolidating the chain of evidence below.

## Delivery chain

1. **Architecture:** `docs/pids/M009-CUSTOMER-ASSURANCE-QUESTIONNAIRE-COMPLETION.md` — merged PR #101, canonical base `93acc86405597641c46b050dd603ab335ebb60d1`.
2. **Work Order:** `docs/work-orders/WO-M009A-SECURE-INGESTION-XLSX.md` — Architect-accepted after a draft, 20 bounded corrections, and 10 Final Corrections.
3. **Implementation:** six original commits on `wo/M009A-work-order`, independently reviewed by the Delivery Controller and a fresh Independent Auditor (GREEN, with one disclosed non-blocking gap re: `supersedes`). PR #102 opened.
4. **Central Architecture's first PR #102 review:** NOT YET ACCEPTED FOR MERGE — three numbered Blockers (supersedes tenant-safety, ClamAV image version, ClamAV CI-gate coverage) plus a governance and an evidence correction.
5. **Correction round:** all three Blockers resolved —
   - **Blocker 1** (`supersedes` tenant-safety): `_validate_supersedes_target` added as the first statement of `ingest_questionnaire_import`, proven by `TestSupersedesContract` (3 tests) and independently re-run.
   - **Blocker 2** (ClamAV version): the real, current official `clamav/clamav:1.4.6` image was re-resolved fresh (never trusting a cached digest) and found genuinely clean — `sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`, `pcre2 10.49-r0` from the image's own stable Alpine repository, **0 CRITICAL / 0 HIGH** (independently reproduced via Trivy three times across this delivery) — pinned directly, no derived overlay required.
   - **Blocker 3** (ClamAV CI coverage): `security/container` extended to scan the pinned ClamAV image (resolved live from `docker-compose.yml`), with a drift guard (`test_m009a_clamav_image_pin.py`) proving both Compose topologies agree.
   - Governance and evidence documents corrected with visible, non-destructive corrections (struck-through superseded text, not deleted).
6. **Fresh Independent Audit:** `docs/evidence/M009A-INDEPENDENT-AUDIT.md` — a genuinely fresh Auditor (no inherited context) independently re-derived every WO-M009A acceptance item against the real running system. **Verdict: GREEN.**
7. **Architect Acceptance:** `docs/evidence/M009A-ARCHITECT-ACCEPTANCE.md` — **ACCEPTED FOR MERGE**, subject to one documentation correction (`docs/delivery/BUILD-REPRODUCIBILITY.md`'s ClamAV ledger, reconciled in the same commit).
8. **Merge:** PR #102 merged via a normal merge commit (not squash, not rebase) — `ad996bfa4527623d095862199b46db6e0ea94fd0` — preserving the complete governance and correction history.
9. **Post-merge reconciliation:** the persistent `infosecurs-relocation` deployment fast-forwarded to `ad996bf`; a full pre-reconciliation backup taken; the new `clamav` service and `questionnaire` storage volume brought up without touching the existing `postgres`/`evidence` volumes (confirmed by volume-creation timestamps); migrations applied cleanly; `/healthz/` 200; a real, authenticated (non-test-fixture) Chromium smoke test against synthetic Customer Zero proved a genuine upload → security-gate-pass → extraction → provenance-display round trip, with the stored file's SHA-256 (re-read from disk) matching the uploaded bytes exactly, zero new `AIInvocationRecord` rows created, and no horizontal overflow at 375px.

## Final verification summary

| Item | Result |
|---|---|
| Fresh Independent Audit | GREEN |
| Full repository test suite | 2343 passed, 0 failed, 7 skipped, 1 xfailed |
| M009A evaluation corpus | GREEN |
| Existing M005 golden corpus | Unchanged / GREEN |
| Tenant isolation | GREEN |
| Supersedes tenant safety | GREEN |
| Customer Zero reset reconciliation | GREEN |
| Backup/restore | GREEN |
| Immutable-original proof | GREEN (upload / DB / on-disk SHA-256 all identical, including live post-merge proof) |
| Real-browser / XSS / responsive acceptance | GREEN |
| ClamAV runtime | `clamav/clamav:1.4.6@sha256:b5b910ce43d595bf8a2fe401e34db56434602b2c755b7c2b07f00c917d04d469`, 0 CRITICAL / 0 HIGH |
| `security/container` | GREEN (scans both the application image and the ClamAV image) |
| Migrations | Clean |
| `gitleaks` | Clean |
| `pip-audit` | Clean |
| All seven GitHub CI checks | GREEN |
| AI boundary | Clean — zero AI invocations in any M009A path |
| DARWIN | Untouched throughout |

## Known, disclosed residue — routine-reset disposition

The real post-merge smoke test against synthetic Customer Zero (`customerzero` / "Infosecurs Limited") created one genuine, benign `QuestionnaireImport` row (and its 3 extracted questions) in that organisation's data, as the real, expected product behaviour of a real upload. Per Central Architecture's explicit instruction, **no Customer Zero reset was executed during this reconciliation or this closure**, so this row remains in place. It carries no security or product risk — it is ordinary synthetic data in the designated synthetic test organisation — and will be removed by the next routine Customer Zero reset cycle, exactly like any other Customer Zero fixture data accumulated between resets. No action is required before or because of this closure record.

## Scope discipline maintained throughout

- M005 (`QuestionnaireQuestion`, `QuestionnaireResponse`, grounding, outcome derivation, AI orchestration) was never touched.
- No re-upload/supersession UI was added.
- No DOCX/PDF/OCR, bulk AI generation, review UX, or export/write-back capability was added — all explicitly out of M009A's bounded scope.
- No M009B implementation work was started under this milestone.

## Decision

**M009A is CLOSED GREEN.** This record is documentation-only and introduces no technical change. Preparation of the M009B Work Order (under the existing M009 master PID) may now begin for architectural review, per Central Architecture's authorisation — implementation remains gated on that Work Order's own acceptance.
