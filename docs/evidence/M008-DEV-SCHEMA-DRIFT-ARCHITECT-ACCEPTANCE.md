# M008 — Project Architect Acceptance of PR #95

**Architect:** Central Architecture / Project Architect
**Date:** 2026-10-06
**PR:** #95
**Accepted reviewed head:** `510f708d028c8ac0bd20235b006e4f2fd5bf3f16`
**Canonical base:** `bd6235bc309a470483cae74afcbf663a9dc8da16`
**Decision:** **ACCEPTED FOR MERGE**

This acceptance covers the M008 Dev Schema Drift / contained credential-exposure recovery only.

## Architect verification

The Architect independently verified:

* PR #95 is open and mergeable;
* current PR head is exactly `510f708d028c8ac0bd20235b006e4f2fd5bf3f16`;
* canonical main remains `bd6235bc309a470483cae74afcbf663a9dc8da16`;
* PR #95 currently changes exactly nine authorised documentation/evidence/runbook paths and zero product paths;
* all seven required GitHub checks are GREEN;
* fresh Independent Auditor verdict is GREEN;
* the Auditor tested `0b054e291f1749d3e35e557fc5d361cc97fb9eda`;
* the only delta from that audited SHA to current PR head is the Auditor's own report: `docs/evidence/M008-DEV-SCHEMA-DRIFT-AUDIT.md`;
* no product/configuration source changed after audit.

## Recovery accepted

The Architect accepts the evidence that:

1. the original outage was caused by persistent-dev database schema drift after source advanced without canonical migrations being reapplied;
2. exactly these three migrations were pending:
   * organisations/0004
   * policy/0003
   * security_baseline/0003
3. a governed logical DB + evidence backup was successfully taken before mutation;
4. backup checksums independently matched;
5. the backup's own SQL schema proves it predates migration;
6. all three canonical migrations are now applied;
7. migrate --plan is empty;
8. makemigrations --check is clean;
9. physical database schema independently matches the expected migrated state;
10. authenticated real-browser application surfaces work;
11. Customer Zero state survived;
12. database/evidence volumes survived;
13. the database credential exposed through captured `docker compose config` output was subsequently rotated under explicit Architect authority;
14. the replacement credential is functioning through the recreated web service;
15. `.env` is mode 0600, gitignored, retained as the local deployment's recoverable operator configuration;
16. no credential appears in the proposed Git diff/evidence;
17. no second secret exposure occurred;
18. DARWIN remained untouched;
19. BETA-OPERATIONS now explicitly prohibits captured raw `docker compose config` / `.Config.Env` use and provides secret-safe identity checks;
20. the runbook now requires migration reconciliation and authenticated application smoke after persistent-dev source advances;
21. `/healthz/ == 200` alone is no longer accepted as application-ready evidence after schema-bearing changes.

The pre-existing untracked `docker-compose.override.yml` is outside this incident and is not authorised for inclusion.

## Merge condition

After adding this exact acceptance record:

1. prove the delta from `510f708d028c8ac0bd20235b006e4f2fd5bf3f16` to the new PR head contains exactly this one acceptance file;
2. prove no product path changed;
3. allow all required CI/security checks to rerun;
4. require all seven GREEN;
5. verify PR #95 remains mergeable/clean.

No further Independent Audit is required for the acceptance-record-only commit.

If anything else changes: **STOP. DO NOT MERGE.**

## Merge authority

If and only if the acceptance-file-only delta and all seven GREEN checks are proven: **MERGE PR #95.**

Then fast-forward canonical `/srv/infosecurs` main and prove: the GitHub merge SHA; the canonical local main SHA; exact equality between them; dev GUI `/healthz/` remains 200; authenticated Home and Foundations still render; `.env` remains mode 0600 and gitignored; DARWIN remains unchanged.

**Do not delete the recovery backup yet. Do not begin M009 yet.**

## Mandatory return after merge

STOP and return to the Project Architect with: the acceptance-record commit/head SHA; proof its only delta was the acceptance file; the seven post-acceptance CI conclusions; the PR #95 merge SHA; the canonical main SHA; the post-merge authenticated application smoke; `.env` status; DARWIN status.

**The Project Architect will then issue the final incident closure and explicitly unblock M009. No other actor declares the incident closed.**
