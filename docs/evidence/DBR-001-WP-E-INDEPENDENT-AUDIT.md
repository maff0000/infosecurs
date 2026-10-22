# PID-DBR-001 Work Package E — Independent Audit of the WP-D Disposable Rehearsal (WO §3.4)

**Status: GREEN. Closes WO-DEPLOYMENT-BOUNDARY-REMEDIATION.md §3.4.**

This record was not committed at the time the audit ran (the audit itself
produced no PR comment, only a verbal report back to the PL) — written
retroactively, before §3.5 cutover-authorisation evidence is requested, so
the final GO/NO-GO package has a durable, in-repository citation for this
gate rather than relying on conversation history.

## Scope

A fresh, from-scratch independent auditor — no memory of the WP-D
Engineer's own reasoning, instructed explicitly not to trust the WP-D
evidence document's prose on its own — was dispatched to re-verify every
load-bearing claim in `docs/evidence/DBR-001-WP-D-DISPOSABLE-REHEARSAL.md`
against the repository and live Docker state directly, not against that
document's narrative.

## What was independently reproduced

- **Release-candidate source correctness**: confirmed the WP-D rehearsal
  ran against `wo/DBR-001-release-base-ad996bf` @ `c47c4c4c2beb779abb49152912dadda4c0a4b1b2`
  (`ad996bf` + WP-A/B/C only) — not current `main` — satisfying the WO's
  own "zero new migrations, no M010" requirement for the initial release.
- **§3.2 negative git-isolation test**: re-run from scratch in the
  auditor's own fresh clone and own disposable stack. An ordinary `git
  checkout` touching 188 files, including `questionnaire/upload_handler.py`
  (the exact file implicated in the 2026-10-19 incident), confirmed to
  have zero effect on the running rehearsal stack — independently
  reproduced, not merely re-read from the WP-D document.
- **Build/swap mechanics**: re-verified directly via raw `docker inspect`
  / `docker top` output (not the WP-D Engineer's own summarised figures) —
  refusal on non-empty migration plan, clean swap, gunicorn confirmed as
  the actual running process, no `/app` bind mount present.
- **Backup/restore cycle**: re-run with the auditor's own independent
  checksums, against the existing, unmodified `scripts/backup.sh` /
  `scripts/restore.sh`.
- **Rollback-bootstrap judgement**: confirmed sound on independent
  grounds — the legacy `web` image genuinely predates gunicorn being added
  to the dependency set (PID-DBR-001 WP-A/B/C), and `docker-compose.release.yml`'s
  `command:` is genuinely unconditional (no fallback path for a
  non-gunicorn image), so an automatic rollback seeding a `previous.json`
  from the pre-existing legacy container would genuinely have produced a
  crash-on-start rather than a working rollback. The WP-D decision to
  document this as a required manual step rather than "fix" it
  automatically was independently judged correct, not merely accepted.
- **Scope discipline**: the real `infosecurs-relocation` stack's
  `web`/`db`/`clamav` containers' `StartedAt` / `RestartCount` were
  confirmed unchanged across the entire rehearsal window — nothing in
  WP-D's disposable testing touched the persistent stack.

## Findings

Two notes, neither a defect in the rehearsal itself:

1. PR #121 (carrying the WP-D evidence document and the two documentation
   fixes) was still unmerged at the moment the audit ran. Resolved
   immediately after the audit returned its verdict, by merging PR #121 —
   merge SHA `453b0dfed1b6964c955f7ebff59f5a1db1a89c89`.
2. A stray leftover Docker image, `dbr001-bkrestore-src-web:latest`, left
   over from WP-D's own backup/restore testing, was found and removed
   (`docker rmi`) — housekeeping only, no evidentiary impact.

## Verdict

**GREEN.** WO §3.4 is satisfied. No repair dispatch was required. This
closes the independent-audit gate that WO §3.5 names as one of the four
required release-plan components ("the independent WP-E audit verdict").
