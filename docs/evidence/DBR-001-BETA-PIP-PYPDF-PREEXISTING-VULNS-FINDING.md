# Finding — Pre-existing `pip` and `pypdf` vulnerabilities (Beta image)

**Status: OPEN. Not corrected as part of the PID-DBR-001 security-only
certifi/Pillow release.** Retained as its own artifact, per the same
scope discipline already applied to
`docs/evidence/DBR-001-BETA-DEVMODE-PLAINHTTP-FINDING.md` — a distinct
issue is recorded separately rather than folded into an unrelated,
narrowly-scoped dependency release.

## 1. What was found

An independent vulnerability scan (`pip-audit --strict`) run inside the
`wo/DBR-001-release-base-secdeps` candidate image
(`infosecurs-release:b39eee9244e56f17bc4aa32904dd1b8def6286ac`), performed
as part of the security verification for that release
(`docs/evidence/DBR-001-NEXT-RELEASE-SEC-DEPS-PREP.md` §4), surfaced:

| Package | Version | Issue IDs | Fix version |
|---|---|---|---|
| `pip` | `25.0.1` | PYSEC-2026-1795, PYSEC-2026-1796, PYSEC-2026-2875, PYSEC-2026-2876, PYSEC-2026-196, PYSEC-2026-3721 | 26.2+ |
| `pypdf` | `6.19.0` | CVE-2026-113786, CVE-2026-113792, CVE-2026-113793, CVE-2026-113794, CVE-2026-113795 | 6.20.0/6.20.1/6.21.1 |

`certifi` and `pillow` themselves returned **zero** findings from the same
scan — confirming the targeted fix is effective.

## 2. Why this is out of scope for the current release

- `pip` 25.0.1 is the version bundled by the base image
  (`python:3.12.14-slim-trixie`) — it is not pinned or managed by this
  project's `requirements*.txt` at all. Bumping it is a Dockerfile
  base-image concern, unrelated to the certifi/Pillow dependency bump.
- `pypdf` 6.19.0 is pinned in `requirements-dev.txt`, confirmed present
  **unchanged** at the historical pre-cutover baseline (`ad996bf`) —
  i.e. it predates PID-DBR-001 entirely and was never touched by any
  commit in this release's scope.

Neither package is introduced, upgraded, downgraded, or otherwise altered
by this release. They are pre-existing conditions of the Beta image as it
already stands.

## 3. Disposition

No action taken. This finding is handed to Central Architecture as a
distinct backlog item, to be scoped and authorised as its own
remediation (likely: a base-image bump for `pip`, and a `pypdf` version
bump following the same hash-pin/evidence discipline already applied to
certifi and Pillow) — not bundled into the current dependency-only
release.
