# Infosecurs — Product Backlog

**Status:** candidate for approval, recorded as for `PRODUCT-VISION.md`.
**Author:** Hermes (Project Architect), 2026-11-19.

This backlog was built from the repository's own records on 2026-11-19. It
lists what is unfinished or anticipated, not what is already delivered;
delivered modules are in `docs/ROADMAP.md`. Items are capabilities and
outcomes, not tasks. Inclusion here authorises no implementation: every
piece of delivery needs its own approved Work Order.

States: **DEFINED** (understood well enough to refine into Work Orders),
**PROVISIONAL** (intent understood, significant uncertainty remains),
**PLACEHOLDER** (anticipated; defining it now would be premature and no
requirements may be invented for it).

Order is the Architect's suggested sequence for recovery. Product priority
is Matt's.

| ID | Capability or outcome | Value | State |
| --- | --- | --- | --- |
| PBI-001 | Delivery works again under Rogue and ForgeV2 | Nothing else can be delivered until one Work Order has gone through the new chain on `dell-debian` | DEFINED |
| PBI-002 | ForgeV2 specialists can run this project's tests | Engineer, Tester and reviewers can verify code changes themselves, not only by inspection | PROVISIONAL |
| PBI-003 | IRENE reusable question engine, Stage 3 pilot, closed out | Customers can answer and save the Stage 3 "Your Technology & Data" questions inside IRENE, with on-demand explanation; proves the formula for further sections | DEFINED |
| PBI-004 | A current Beta release | The persistent Beta can be restarted on an image that carries the 2026-11-19 security fixes and the IRENE work already on `main` | DEFINED |
| PBI-005 | Known security findings assessed and dispositioned | Findings already recorded in the repository are either fixed or explicitly accepted | PROVISIONAL |
| PBI-006 | Repository records tell a fresh agent the truth | A new session is not misdirected by superseded instructions or stale status | DEFINED |
| PBI-007 | Customer Assurance bulk orchestration and claim ledger (M009 increments 3–4) | Completes questionnaire handling at volume | PROVISIONAL |
| PBI-008 | IRENE guides further sections | Extends the Stage 3 formula to other question journeys | PLACEHOLDER |
| PBI-009 | Live Adviser Mode and the scheduled review job on a persistent environment | IRENE's generative clarification and proactive review tasks work for real users | PLACEHOLDER |
| PBI-010 | Tenant export and DSAR readiness | A tenant's data can be exported or erased on request | PLACEHOLDER |
| PBI-011 | Production readiness | Real customer data, production-grade authentication, production deployment | PLACEHOLDER |

## Notes on each item

**PBI-001 — Delivery works again.** First Work Order:
`work-orders/WO-INFOSECURS-001.md`, deliberately small and
documentation-only, to prove the Project Lead path as root on
`dell-debian`. Depends on nothing. Done when one Work Order has returned a
valid ForgeV2 result and its branch has been reviewed.

**PBI-002 — Specialists can run the tests.** ForgeV2 specialists have no
network from commands. The project's tests need PostgreSQL over TCP, the
pinned Python dependencies and, for browser tests, Chromium. The host has
none of these outside containers (VERIFIED: no PostgreSQL binaries; host
Python is 3.11, the project pins 3.12). How to close the gap is an
architecture question for the Architect and may need a ForgeV2 change,
which would be a separate engine Work Order, not an application one.
Open question: is CI on the pull request an acceptable substitute for
specialist-run tests on low-risk changes. Blocks PBI-003.

**PBI-003 — IRENE Stage 3 pilot.** Authority: `docs/pids/PID-IRENE-STAGE3-QUESTION-ENGINE-AMENDMENT.md`
and `docs/work-orders/WO-IRENE-001-STAGE3-QUESTION-ENGINE-PILOT.md`.
Disposition and what remains: `docs/delivery/WO-IRENE-001-DISPOSITION-2026-11-19.md`.
Depends on PBI-002 and on a reachable AI gateway.

**PBI-004 — A current Beta release.** Building and verifying a release
image is engineering. Restarting or exposing the Beta is a material-risk
decision and stays with Matt. The release mechanism is the one delivered
under PID-DBR-001 (`scripts/release.sh`, `docker-compose.release.yml`).

**PBI-005 — Known findings.** Recorded in the repository and not
re-assessed in this pass:
- `docs/evidence/DBR-001-BETA-DEVMODE-PLAINHTTP-FINDING.md`;
- `docs/evidence/DBR-001-BETA-PIP-PYPDF-PREEXISTING-VULNS-FINDING.md`;
- plain HTTP between the Beta container and the internal AI gateway
  (recorded on the IRENE pilot branch);
- the manual Stage 3 page saves the whole profile row and is not
  concurrency-safe (recorded in WO-IRENE-001);
- the image build installs the development lock file, so test tooling is
  present in the image (observed by the Architect in `Dockerfile` on
  2026-11-19; whether this is intended is UNKNOWN).

**PBI-006 — Truthful records.** Known cases: `GUNNAR-START.md` and
`INFOSECURS-GUNNAR-START.md` still instruct a session to start as GUNNAR
with `/srv/infosecurs` as its working root (WO-INFOSECURS-001 retires
them); `docs/ROADMAP.md` rows for M002 and M003 are stale; about 150 other
branches remain on GitHub, and which of them are merged has not been
checked. Deleting branches is not authorised by this item.

**PBI-007.** `docs/ROADMAP.md` records these increments as "not yet
authorised for implementation". Existing document:
`docs/work-orders/WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md`.

**PBI-008 to PBI-011.** Named in `docs/ROADMAP.md` or `PID.md` as separately
governed and not authorised. Each needs Matt's direction before it is
defined.
