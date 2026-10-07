# M008 — Dev Schema Drift Incident Closure

**Architect:** Central Architecture / Project Architect
**Closure date:** 2026-10-07
**Recovery PR:** #95
**Accepted PR head:** `468706b87eae5d009d13e37105dc7f1be90dba20`
**Recovery merge SHA:** `6cd2740df2e861f8cfd24074a8056644d573d32c`
**Canonical main at closure decision:** `6cd2740df2e861f8cfd24074a8056644d573d32c`
**Decision:** **CLOSED GREEN**

## Incident

The persistent INFOSECURS development deployment became unusable after canonical source advanced to M008 code while its persistent PostgreSQL schema remained behind the canonical Django migration graph.

The customer-visible symptom was a Django `ProgrammingError` because application code queried `OrganisationProfile.sector` while the live database did not yet contain that column.

During governed recovery, a second operational incident occurred when captured output from raw `docker compose config` exposed the interpolated PostgreSQL password to Implementer tooling.

Both issues are closed.

## Root cause accepted

The Project Architect accepts the independently audited root-cause record:

1. `/srv/infosecurs` advanced to canonical M008 source.
2. The running development web service bind-mounted that source.
3. Django development reload consumed the new Python/model definitions.
4. The existing web container was not recreated/restarted through its Compose startup command.
5. Therefore `manage.py migrate --noinput` did not rerun.
6. Persistent PostgreSQL remained behind the source migration graph.
7. `/healthz/` continued returning 200 because it proved database reachability, not ORM/schema compatibility.
8. Real authenticated application traffic exposed the mismatch.
9. `/srv/infosecurs/.env` was also absent, making governed backup/recreation non-recoverable from host configuration.
10. Raw `docker compose config` subsequently rendered an interpolated database credential into captured tooling output.

## Recovery accepted

A governed backup was taken before schema mutation.

Exactly three canonical migrations were pending and were applied:

- `organisations/0004_organisationprofile_has_remote_or_offsite_access_and_more`
- `policy/0003_alter_policyversion_generation_source`
- `security_baseline/0003_answerselectiondetail`

Post-recovery:

- `showmigrations` is current;
- `migrate --plan` is empty;
- `makemigrations --check --dry-run` is clean;
- the physical database schema matches canonical migration state;
- Customer Zero identity/membership/governance data is preserved;
- database and evidence volumes are preserved;
- authenticated real application pages render successfully;
- `/healthz/` remains 200.

## Credential exposure closure

The credential exposed through captured `docker compose config` output was treated as compromised within the execution/tooling boundary.

It was rotated under explicit Architect authority after a valid recovery backup existed.

The replacement credential functions through the recreated web service.

The previous credential is no longer authoritative.

No credential appears in Git/evidence.

No second exposure occurred.

## Operator configuration

`/srv/infosecurs/.env` now exists as the local development deployment's operator configuration.

It is:

- mode `0600`;
- Git-ignored;
- not committed;
- required for repeatable backup/recovery/container recreation.

Its secret values are not durable project documentation and must never be copied into Git or evidence.

## Prevention

The merged Beta Operations runbook now requires:

- secret-safe deployment identity checks;
- no captured raw `docker compose config`;
- no `.Config.Env` inspection;
- migration status verification after persistent source advances;
- canonical migration application where required;
- post-migration `migrate --plan` and `makemigrations --check`;
- authenticated model-backed application smoke.

A successful `/healthz/` result alone is explicitly insufficient evidence that a schema-bearing release is usable.

## Governance

The incident followed the governed recovery chain:

Architecture decision
→ Amendments
→ Git-tracked Work Orders
→ Delivery Controller
→ Implementer
→ Independent Audit
→ PR
→ Architect Acceptance
→ Merge
→ Closure

The historical operational failure is not reclassified as a product-code defect.

M008 remains **CLOSED PRODUCT_GREEN**.

## M009

The Project Architect explicitly removes the operational block on the next product milestone.

**M009 architecture/PID work is AUTHORISED TO BEGIN.**

This does not authorise M009 implementation.

M009 must begin at:

`Architecture decision → PID`

and subsequently follow the full mandatory delivery chain.
