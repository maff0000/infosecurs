# Build Reproducibility — accepted control-input state

**Status:** ACCEPTED, 2026-09-22 — Central Architecture governance closure amendment.
**Critical invariant:** A build must not change because time passed.
**Governing invariant:** PROJECT TRUTH == GITHUB.

This is a durable record of the control inputs a build depends on: base
image digests, the dependency lock, pinned CI tooling and the runner
generation. It exists so that "what did M001 actually build against" is a
question this file (and GitHub's own state) answers directly, not something
reconstructed from memory or from whatever tags currently resolve to.

No M001 application behaviour changed in this hardening pass — see the diff
identity proof in this PR's evidence trail / commit history
(`Dockerfile`, `docker-compose.yml`, `.github/workflows/**`,
`requirements*.txt`/`.in` only).

## Accepted image digests

| Component | Explicit version | Immutable digest | Used in |
|---|---|---|---|
| Python base image | `3.12.14-slim-trixie` | `sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9` | `Dockerfile` |
| PostgreSQL | `16.6-alpine` | `sha256:1d04b9ba1d4996401f2552b51beda8187f175c0645c091e4781134fc9c9a3eef` | `docker-compose.yml`, `.github/workflows/ci.yml` (both `ci/unit` and `ci/integration` service containers) |

Both digests were resolved directly from the registry
(`docker buildx imagetools inspect <image>:<tag>`) at the time of this
change, confirmed to match the explicit version tag they claim (not a
floating `latest`/`3.12-slim`/`16.6-alpine` alias resolved separately from
the digest).

### Why `apt-get upgrade -y` was removed, not just deleted

M001 originally ran `apt-get upgrade -y` at build time specifically to clear
CRITICAL/HIGH CVEs Trivy found in the floating `python:3.12-slim` base. That
is exactly the kind of build-that-changes-because-time-passed this hardening
pass exists to remove: the upgrade's actual effect depended on whatever
Debian security packages happened to be live on the day the image built.

Removing it was verified safe, not assumed: a Trivy scan
(`aquasec/trivy:0.70.0`, `--severity CRITICAL,HIGH --ignore-unfixed`) against
an image built from the pinned digest above, with `apt-get upgrade` already
removed, returned **zero vulnerabilities** — 0 OS packages (debian 13.7), 0
across every Python package layer. The pinned digest is current enough on
its own. If a future CVE appears in this exact digest, the fix is a
deliberate re-pin (new tag, new digest, this file updated) — never an
uncontrolled upgrade baked back into the build.

### Temporary exact-version security overlay (Central Architecture amendment, 2026-10-01)

The prohibition above remains the rule. This is the one narrow, authorised
exception to it, not a reopening of it:

> When the immutable upstream base-image digest lags a published security
> fix, Central Architecture may authorise a bounded exact-version-pinned
> security overlay for explicitly named packages. This is not a general apt
> upgrade. The selected versions must be explicit and fail closed if
> unavailable. The overlay is temporary and should be removed when a newly
> accepted upstream base-image digest incorporates the fixes.

**Why a base-image re-pin was not possible this time:** on 2026-09-30/10-01,
Trivy found 7 HIGH findings across 3 CVEs (CVE-2026-75804, CVE-2026-84782,
CVE-2026-103111) against the pinned digest's OS packages (`openssl`,
`libssl3t64`, `openssl-provider-legacy` at `3.5.7-1~deb13u2`; `libpcre2-8-0`
at `10.46-1~deb13u2`). Debian's `trixie-security` apt repository already
carries every fixed version, but a fresh `docker pull
python:3.12.14-slim-trixie` on the same dates still resolved to an image
shipping the unpatched builds — upstream has not yet rebuilt this tag
against the patched Debian packages, so there was no new digest to re-pin
to. (CVE-2026-103111/`libpcre2-8-0` was found by a second, later Trivy
rescan during the same remediation dispatch, after the first three packages
were already fixed — not present in the initial 2026-09-30 scan.)

**The overlay:** `Dockerfile`'s `FROM` line is unchanged
(`sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`,
same as the table above). Immediately after it, one `RUN apt-get update &&
apt-get install --only-upgrade <pkg>=<exact-version> ... && rm -rf
/var/lib/apt/lists/*` step names exactly four packages and exactly one
target version each:

| Package | Was | Now (exact pin) |
|---|---|---|
| `openssl` | `3.5.7-1~deb13u2` | `3.5.7-1~deb13u3` |
| `libssl3t64` | `3.5.7-1~deb13u2` | `3.5.7-1~deb13u3` |
| `openssl-provider-legacy` | `3.5.7-1~deb13u2` | `3.5.7-1~deb13u3` |
| `libpcre2-8-0` | `10.46-1~deb13u2` | `10.46-1~deb13u3` |

`apt-get install pkg=version` fails the build closed if any exact version
is not resolvable in the configured repositories — there is no silent
fallback to "whatever's current." No other OS package is touched.

**Before/after Trivy (`aquasec/trivy:0.70.0`, `--severity CRITICAL,HIGH
--ignore-unfixed`):**

- Before (pinned digest, no overlay): 6 HIGH, 0 CRITICAL (`openssl`,
  `libssl3t64`, `openssl-provider-legacy` × {CVE-2026-75804,
  CVE-2026-84782}).
- After openssl/libssl3t64/openssl-provider-legacy fixed, before
  `libpcre2-8-0` fixed: 1 HIGH (`libpcre2-8-0`, CVE-2026-103111).
- After all four packages fixed: **0 CRITICAL/HIGH.**

**Obligation:** remove this overlay entirely the next time this
`Dockerfile`'s base-image digest is deliberately re-pinned to one that
already carries `openssl 3.5.7-1~deb13u3`, `libpcre2-8-0 10.46-1~deb13u3`,
or later — re-check at that time whether the overlay is still necessary
before keeping it. See `docs/evidence/SECURITY-REMEDIATION-2026-10-01.md`
for the full dispatch evidence (build log, package-version proof, CVE
detail).

## Python dependency lock

Mechanism: `pip-tools` (`pip-compile`, `--generate-hashes`), run inside a
container built from the exact pinned Python digest above (transitive
resolution and wheel hashes are platform/interpreter-specific, so the lock
is generated in the same environment the build will actually install into).

```text
requirements.in       -> requirements.txt       (pip-compile --generate-hashes)
requirements-dev.in   -> requirements-dev.txt    (pip-compile --generate-hashes)
```

- `requirements.in` / `requirements-dev.in` declare only the direct,
  version-pinned dependencies (unchanged from before this hardening:
  `Django==6.1.1`, `psycopg[binary]==3.3.6`, plus `pytest==9.1.1` /
  `pytest-django==4.14.0` for dev).
- The generated `.txt` files are the accepted lock: full transitive closure
  (`asgiref`, `psycopg-binary`, `sqlparse`, `typing-extensions` for the
  production graph; additionally `iniconfig`, `packaging`, `pluggy`,
  `pygments` for the dev/test graph), every entry with `--hash=sha256:...`
  integrity hashes for every distributed wheel/sdist.
- Docker and CI both install with `pip install --require-hashes -r
  requirements-dev.txt` — `--require-hashes` refuses to install anything
  (including transitively) that isn't hash-verified against this exact lock.
  There is no path in the accepted build that installs an unlocked package.
- To change a dependency: edit the relevant `.in` file, regenerate the
  matching `.txt` with `pip-compile --generate-hashes` inside a container
  built from the currently-accepted Python digest, commit both.

### Dependency security bump: `pyjwt` (2026-10-01 remediation)

`pyjwt` is not a direct dependency in either `.in` file — it arrives
transitively via `django-allauth[socialaccount]`'s own
`pyjwt[crypto]>=2.0,<3` constraint. CVE-2026-101918 (GHSA-42vr-xj54-vc7v, an
unauthenticated `RecursionError` DoS in `PyJWKClient.get_signing_key_
from_jwt`'s pre-verification payload parse) affected the then-locked
`2.14.0`, fixed upstream at `2.15.0`.

No `.in` file edit was needed or made: `pip-compile --generate-hashes
--upgrade-package pyjwt` (same pinned-digest container the lock is always
generated in) was run against both `requirements.in` and
`requirements-dev.in` and the resolver naturally selected `pyjwt[crypto]
==2.15.1` — the actual current PyPI release (not `2.15.0` exactly), still
within `django-allauth==65.19.4`'s `>=2.0,<3` range. Independently confirmed
via the OSV advisory database that `2.15.1` carries zero known
vulnerabilities. Exactly 3 lines changed in each of `requirements.txt` and
`requirements-dev.txt` (the one `pyjwt[crypto]==...` entry and its two
hashes) — no other package moved.

### Pip-audit suppression discipline

`security/dependencies` (`.github/workflows/security.yml`) runs `pip-audit
-r requirements.txt --ignore-vuln CVE-2026-49265` — exactly one advisory
ignored, matching `pip-audit`'s own reported `id` field for that finding
(oauthlib's PKCE `code_verifier` timing-comparison issue, GHSA-xpv3-w29h-
x7cv). This is a temporary, reachability-based risk acceptance, not a
statement that the finding is safe in general — see
`docs/evidence/SECURITY-REMEDIATION-2026-10-01.md` for the full reachability
evidence and review triggers. **Note (corrected by independent audit,
2026-10-01):** `oauthlib`'s only fixed release, `4.0.0`, was outside
`django-allauth`'s own `oauthlib<4,>=3.3.0` constraint at the version
installed here (`65.19.4`) and still at `65.19.5` — but `django-
allauth==65.19.6` (released 2026-09-30) already *requires*
`oauthlib>=4.0.0`. A compatible upgrade path now exists; this remediation
does not adopt it (that is a separate, untested dependency upgrade, out of
this bounded dispatch's scope) but the evidence document's review-trigger
condition for it has already fired and is flagged there rather than
deferred to the 30-day window. No other advisory is, or should be, ignored
by this flag.

## GitHub Actions — pinned to commit SHA, version kept as a comment

| Action | Pinned commit | Version (comment only, not what's trusted) |
|---|---|---|
| `actions/checkout` | `11d5960a326750d5838078e36cf38b85af677262` | v4.4.0 |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | v5.6.0 |
| `gitleaks/gitleaks-action` | `ff98106e4c7b2bc287b24eaf42907196329070c7` | v2.3.9 |
| `github/codeql-action/init`, `.../analyze` | `3ea06614dafe36dec890db3446326e0d40ce53d4` | v3.38.1 |
| `aquasecurity/trivy-action` | `ed142fd0673e97e23eac54620cfb913e5ce36c25` | v0.36.0 |

A tag (even a major-version tag like `v4`) can move to point at a different
commit at any time; a commit SHA cannot. Every `uses:` line in
`.github/workflows/*.yml` is pinned this way — no floating tags anywhere in
this repository's workflows as of this change.

### Security-tooling version governance ("where practical" per the directive)

- **Trivy** — the action's own `version:` input is set explicitly
  (`v0.70.0`) rather than relying on the action's bundled default, so the
  actual scanner binary version is visible and controlled in this repo's own
  config, independent of the action release cadence.
- **pip-audit** — installed with an explicit pin (`pip install
  pip-audit==2.10.1`), not `pip install pip-audit` against whatever is
  currently latest on PyPI.
- **gitleaks** (via `gitleaks-action`) and **CodeQL** (via `codeql-action`)
  do not expose an independent tool-version input in the way Trivy does —
  each action bundles its own tool version internally, tied to the action's
  own release. Pinning the action to an exact commit SHA (table above) is
  therefore the correct and sufficient governance lever for both; there is
  no separate "tool version" floating underneath a pinned action commit for
  either of these two.

## Runner generation

`ubuntu-latest` replaced with `ubuntu-24.04` (explicit generation) on every
job in `.github/workflows/ci.yml` and `.github/workflows/security.yml`.
`ubuntu-latest` is GitHub's own floating alias and has moved to a new OS
generation before without repository opt-in; `ubuntu-24.04` does not move
under a repository until GitHub deprecates that image generation entirely
(a deliberate, announced event, not silent drift).

The application build itself does not depend on anything installed on the
runner host beyond what the pinned actions above provide — `docker build`
runs against the pinned base-image digest inside a container, and
`pip install --require-hashes` runs inside that same container against the
locked graph. No host-installed system Python, host `pip`, or host package
version is load-bearing for the application build.

## Verification performed before this was accepted

- `docker compose build --no-cache` — clean build from the pinned digest,
  `--require-hashes` install succeeded against the full lock.
- `docker compose up` (digest-pinned postgres) + `manage.py migrate
  --noinput` — clean bootstrap, no pending migrations.
- `pytest -v` inside the hardened container — **38/38 passed** (same suite
  as M001's own evidence; zero application-behaviour change was the point).
- `trivy image --severity CRITICAL,HIGH --ignore-unfixed` against the
  hardened image, `apt-get upgrade` already removed — **0 vulnerabilities**.
- Full PR-based delivery through the GitHub-enforced `main-governance`
  ruleset: all six required checks (`ci/unit`, `ci/integration`,
  `security/secrets`, `security/dependencies`, `security/sast`,
  `security/container`) green on the merged head.
