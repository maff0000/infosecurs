# Security remediation and ruleset exception — 2026-11-19

**Prepared by:** Hermes, Project Architect.
**Base:** `main` at `aa52155e866514ff95fff46c0d28646d4ef0c063`.

## 1. Authority

Development stopped abruptly at the October office move. When it resumed on
2026-11-19, advisories published in the gap had turned two required checks
red for every pull request.

Matt Scott, Product Owner, authorised two things on 2026-11-19 to recover
the project:

1. A one-off exception to the `main-governance` ruleset, to merge the
   documentation-only pull request #129 (section 5).
2. This dependency update, implemented directly by the Project Architect.

Item 2 departs from `docs/architecture/DELIVERY-GOVERNANCE.md`: there is no
Work Order, no Implementer run and no independent audit. Matt accepted that
for this recovery only. Delivery returns to FOUNDRY and ForgeV2 after it.
The gate for this change is the six required checks on its own pull
request, with the ruleset unmodified.

## 2. Findings

From the Security workflow on pull request #129 (run `44501918414`, head
`fad2c2f4d4758889845b979b13532efe6aa56998`), which changed four Markdown
files and no dependency:

| Check | Component | Finding | Fixed in |
| --- | --- | --- | --- |
| `security/dependencies` | `oauthlib 4.0.0` | CVE-2026-49272, authentication bypass | `4.0.1` |
| `security/container` | `oauthlib 4.0.0` | CVE-2026-49272 | `4.0.1` |
| `security/container` | `pypdf 6.19.0` (test-only) | ten denial-of-service advisories | `6.21.4` |
| `security/container` | `apt 3.0.3` | CVE-2026-109518 | `3.0.4` |
| `security/container` | `zlib1g 1:1.3.dfsg+really1.3.1-1+b1` | CVE-2026-85091 | `1:1.3.dfsg+really1.3.1-1+deb13u1` |

Whether Infosecurs' own use of `oauthlib` (federated sign-in through
`django-allauth`) is exploitable through CVE-2026-49272 was not assessed.
The package was updated on the advisory alone.

## 3. Changes

- `requirements.txt`, `requirements-dev.txt`: `oauthlib 4.0.0` to `4.0.1`.
- `requirements-dev.in`, `requirements-dev.txt`: `pypdf 6.19.0` to `6.21.4`.
- `Dockerfile`: the existing exact-version security overlay gains `apt`,
  `libapt-pkg7.0` and `zlib1g`. The base-image digest is unchanged.
- `docs/delivery/BUILD-REPRODUCIBILITY.md`: both changes recorded, with the
  method and the re-pin check.

No application code changed.

## 4. Verification

Run on `dell-debian` on 2026-11-19, on an image built from this change:

- Installed versions in the built image: `apt 3.0.4`, `libapt-pkg7.0 3.0.4`,
  `zlib1g 1:1.3.dfsg+really1.3.1-1+deb13u1`, `openssl 3.5.7-1~deb13u3`,
  `libssl3t64 3.5.7-1~deb13u3`, `libpcre2-8-0 10.46-1~deb13u3`,
  `oauthlib 4.0.1`, `pypdf 6.21.4`.
- Trivy `v0.70.0` with the workflow's flags (`--severity CRITICAL,HIGH
  --ignore-unfixed --exit-code 1`): exit 0.
- `pip-audit 2.10.1` on `requirements.txt` and on `requirements-dev.txt`:
  no known vulnerabilities.
- Lock diff: only the `oauthlib` and `pypdf` entries and their hashes moved.

Not run locally: the test suites. `ci/unit` and `ci/integration` on the
pull request are the evidence that `pypdf 6.21.4` and `oauthlib 4.0.1` do
not break the tests. The ClamAV image scan is a later step of the same
`security/container` job, which stopped at the first failure on #129, so
its current result is only known from this pull request's own run.

## 5. Ruleset exception for pull request #129

`docs/delivery/GITHUB-EVIDENCE-CONTRACT.md` records that `main-governance`
(id `23843330`) has no bypass. That remains true. The exception was a
temporary edit of the ruleset itself, made with repository administration
rights, approved by Matt.

- **Change:** `security/dependencies` and `security/container` were removed
  from the required status checks. Nothing else in the ruleset changed.
- **First window, 10:24:58 to 10:26:08 UTC:** nothing merged. The script
  waited for merge state `CLEAN`; GitHub reported `UNSTABLE`, which is the
  correct state when a non-required check is failing. The ruleset was
  restored.
- **Second window, 10:27:04 to 10:27:15 UTC:** pull request #129 merged at
  head `fad2c2f4d4758889845b979b13532efe6aa56998`, merge commit
  `aa52155e866514ff95fff46c0d28646d4ef0c063`. The ruleset was restored.
- **After each window** the ruleset was read back and compared with the
  copy saved beforehand: identical rules, `enforcement: active`, no bypass
  actors, all six checks required.
- No other commit reached `main` in either window.

On 2026-10-01 the same situation (pull request #78) was handled the other
way round: the remediation merged first and the documentation pull request
after it, with no exception. That order needs no exception and is the
better default. It was not used here because the record in #129 is what
gives the new delivery arrangement its authority.

## 6. Not covered

- **The persistent Beta.** Its containers are stopped. Its release image was
  built from `b39eee9244e56f17bc4aa32904dd1b8def6286ac`, which carries
  `oauthlib 4.0.0` and the unpatched `apt` and `zlib1g`. It needs a new
  release under `PID.md` section 6.1 before it is exposed again.
- **A base-image re-pin.** Still not possible; see
  `docs/delivery/BUILD-REPRODUCIBILITY.md`. The overlay stays until one is.
