# M008D — Three Sample Policies (Revision 2)

**Status:** DESIGN ARTEFACT — supersedes `M008D-SAMPLE-POLICIES.md`
(Revision 1). Each scenario now produces **two** real rendered PDFs
(not one blended document): the distributable **policy** (normative
only) and the internal-only **implementation status** record. Personas
reused from the master PID §8, same mapping as Revision 1 (A ≈ Persona
B's shape, B ≈ Persona A's shape, C ≈ Persona C).

## Scenario A — Thornfield Bookkeeping Ltd (mature, office-first)

- `docs/design/policies/M008D-policy-a.pdf` — the distributable policy.
  Fixed normative commitments (same 8-section wording shape as every
  scenario), governance role-holders named (Maria Gonzalez — Security
  responsible/Policy authoriser; David Finch, Managing Director —
  Senior leadership).
- `docs/design/policies/M008D-status-a.pdf` — implementation status:
  9 of 12 controls Met, 3 Gap (backup restore untested, awareness
  informal-only, no incident reporting route), 0 Not yet confirmed.
  `remote_access_control` shows `REMOTE_ACCESS_NOT_APPLICABLE`
  (confirmed via the new dedicated `has_remote_or_offsite_access ==
  "no"` fact, Met).

## Scenario B — Harlow Digital Consulting Ltd (incomplete, remote-first)

- `docs/design/policies/M008D-policy-b.pdf` — same fixed normative
  structure, role-holders Tom Ridley (Security responsible), Priya
  Shah (Policy authoriser / Senior leadership).
- `docs/design/policies/M008D-status-b.pdf` — implementation status:
  2 of 12 Met (admin MFA, privileged access separation), 10 Gap, 0 Not
  yet confirmed. Demonstrates the distinct-option-same-state rule
  (`ENDPOINT_PROTECTION_COMPANY_ONLY`, `PATCHING_IRREGULAR`,
  `BACKUPS_RESTORE_UNTESTED`, each with its own wording).

## Scenario C — freshly reset / all-unknown

- `docs/design/policies/M008D-policy-c.pdf` — **the normative
  commitments still render**, because they are fixed regardless of
  current state (Revision 2's own key design point) — but the document
  is headed "Preview" with an explicit banner stating approval is
  blocked (business context unconfirmed, nothing yet reviewed).
  Role-holder names show `[name not yet confirmed]` since Stage 2
  (governance role assignment) has not yet been completed in this
  scenario's own narrative.
- `docs/design/policies/M008D-status-c.pdf` — all 12 controls
  `NOT_YET_CONFIRMED`, none silently treated as GAP.

## What changed from Revision 1

Revision 1 blended current-state language directly into one document
per scenario (e.g. "Multi-factor authentication is currently enabled
for some, but not all, staff accounts — extending this to every account
is an identified action," all in the one distributable PDF). Revision 2
splits this: the PDF says "Multi-factor authentication must be used for
all staff accounts" (true for every organisation, every scenario,
identical wording), and the separate, internal-only implementation
status record is where "required for some, not all" + "extend
enforcement" actually lives — never shown in the distributed artefact
by default, per Central Architecture's correction.
