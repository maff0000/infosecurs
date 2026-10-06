# M008 — Dev Schema Drift Recovery Amendment 002

**Parent:** `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT.md`
**Canonical source SHA:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** AUTHORISED — BOUNDED OPERATIONAL CONTINUATION

## What this Amendment records

**Phase A result (from the Implementer's pre-mutation diagnostic gate):** exactly three canonical migrations are pending against the live `infosecurs-relocation` development stack:

- `organisations/0004_organisationprofile_has_remote_or_offsite_access_and_more`
- `policy/0003_alter_policyversion_generation_source`
- `security_baseline/0003_answerselectiondetail`

`makemigrations --check --dry-run` is clean. Migration history is ordinary and consistent. No database mutation has occurred.

**The governed backup is blocked solely because `/srv/infosecurs/.env` is absent** from this host's filesystem. The already-running `infosecurs-relocation-web-1`/`infosecurs-relocation-db-1` containers continue to run because their environment was captured at container creation time — they do not need this file to keep running. The documented backup script (`scripts/backup.sh`) does need it, as a hard precondition, and the Implementer correctly stopped rather than create it without explicit authorisation.

## What this Amendment authorises

A **temporary operational `.env`** at `/srv/infosecurs/.env`, authorised **solely** to permit the governed backup/recovery procedure to run against the already-running `infosecurs-relocation` stack. This file:

- recovers its values from the existing running stack (never invented, never rotated);
- is **not** authority to establish a new permanent host configuration;
- must be removed once this incident's recovery is complete (see `docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-002.md`'s Phase G).

## What this Amendment explicitly does NOT authorise

- **No source/product code repair** is presently authorised.
- **No permanent runtime configuration.** This is a bounded recovery shim, not a reconstructed canonical `.env`.
- **No searching for an old `.env`.**
- **No manual PostgreSQL modification.**
- **No M009.**

## Secret handling — binding on every actor under this Amendment

`POSTGRES_PASSWORD` is a secret. It is recovered silently from the already-running `db` container's own environment and written directly into the temporary `.env` file. It must **never** be printed to any terminal output that is captured, logged, quoted, or placed into any evidence document, report, or chat message, by any actor operating under this Amendment or its Work Order. The temporary `.env` file itself must be mode `0600`, must never be added to Git, and must never be copied into any evidence artefact.

## Closure condition

This Amendment's own closure condition is satisfied once `docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-002.md`'s full sequence (backup → migration → verification → browser acceptance → temporary `.env` removal → root-cause/prevention documentation → independent audit) completes GREEN and is returned to the Project Architect, exactly as that Work Order specifies. Only the Project Architect closes this incident.
