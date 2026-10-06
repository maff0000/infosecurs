# M008 — Dev Schema Drift Recovery Amendment 003: Credential Exposure

**Parent:** `docs/pids/M008-DEV-SCHEMA-DRIFT-RECOVERY-AMENDMENT-002.md`
**Recovery branch/base:** `arch/m008-dev-schema-drift`, at `756d74dd95eceb4644e7455d33ef21f7d9f90880`
**Canonical source SHA:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** AUTHORISED — CONTAINED EXPOSURE, ROTATION DEFERRED UNTIL AFTER RECOVERY

## Classification

**CONTAINED OPERATIONAL CREDENTIAL EXPOSURE — POSTGRES PASSWORD.**

## What happened

During Phase B2 of `docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-002.md`, the bounded Implementer ran `COMPOSE_PROJECT_NAME=infosecurs-relocation docker compose config` exactly as that Work Order specified. That command fully resolves environment interpolation and renders the literal `POSTGRES_PASSWORD` value for both the `db` and `web` services — the Implementer did not anticipate this, and the value appeared in its own captured tool output.

**No secret value is copied into this Amendment, into any evidence document, into any PR, into any chat return, or into any audit report.** This document records that the exposure occurred and how it was handled, never the value itself.

## Containment

- The exposure was limited to captured Implementer tool output.
- No further action occurred after discovery — the Implementer stopped immediately on recognising what had happened.
- No secret value was copied into Git, into a file, into this Amendment, into the Delivery Controller's report, or restated anywhere after the initial exposure.
- Live `infosecurs-relocation` and DARWIN containers remained untouched throughout.
- `/srv/infosecurs/.env` remained mode `0600`.
- The database, any backup, and any migration all remained untouched — nothing had been mutated when the exposure occurred.

## Architect decision

The credential is now classified as requiring rotation. **Rotation is deliberately deferred until after the governed backup and schema recovery have completed** — rotating authentication state before a verified recovery point exists would itself be a risk, not a mitigation.

**Raw `docker compose config` is prohibited for the remainder of this incident.** See `docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-003.md` for the non-secret identity-proof methods that supersede it.

**M009 remains blocked.** No application/source-code repair is authorised by this Amendment.

## Supersession

`docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-003.md` **supersedes** `WO-M008-DEV-SCHEMA-DRIFT-002.md`'s unsafe Phase B2 identity-command detail specifically (the raw `docker compose config` invocation), but otherwise continues that Work Order's recovery intent — the backup, migration, verification, and browser-acceptance phases remain as previously authorised, now resumed under a secret-safe identity-proof method, followed by the credential-rotation phase this Amendment newly authorises.
