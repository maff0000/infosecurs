# M008 — Dev Schema Drift Recovery Amendment

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Incident date:** 2026-10-06
**Canonical source SHA:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Status:** AUTHORISED INCIDENT RECOVERY

## Live symptom

A Django `ProgrammingError` is observed on the Customer Zero organisation page: `column organisations_organisationprofile.sector does not exist`. The canonical source at the SHA above already contains `OrganisationProfile.sector`, and the canonical migration `organisations/migrations/0004_organisationprofile_has_remote_or_offsite_access_and_more.py` already exists in that source. The persistent development database's actual schema does not yet reflect it.

## What this Amendment records

- **M008 remains CLOSED PRODUCT_GREEN.** This incident does not reopen or revisit that closure.
- This is a **DEV operational/schema-reconciliation incident**, not presently evidence of a source-code defect. The canonical source and the canonical migration already exist and are correct; the live symptom is a persistent development database that has not yet had those migrations applied against it.
- **M009 remains blocked** until this recovery closes.
- **No manual schema editing.** No `ALTER TABLE`, no hand-written SQL against this schema.
- **No database recreation.** The persistent development database is reconciled in place, never dropped or rebuilt from scratch.
- **Preserve all Customer Zero data and evidence.** Nothing authorised under this Amendment may delete or alter Customer Zero's organisation, user, membership, governance-role assignments, or evidence files/records.
- **DARWIN untouched.** Nothing authorised under this Amendment may interact with the unrelated DARWIN product or its containers in any way.

## What this Amendment authorises

Exactly the bounded diagnosis, safe canonical-migration application, verification, and prevention-evidence work named in `docs/work-orders/WO-M008-DEV-SCHEMA-DRIFT-001.md`. Nothing else.

## What happens if the evidence disproves the expected narrative

If investigation shows migration history is inconsistent, faked, divergent, or otherwise abnormal, or if `makemigrations --check` proposes any new source migration, or if the evidence does not support the "running code ahead of persistent dev schema" root cause: **STOP**, and return to the Architect for a new Amendment and Work Order. No repair is authorised beyond what this Amendment and its Work Order explicitly permit.
