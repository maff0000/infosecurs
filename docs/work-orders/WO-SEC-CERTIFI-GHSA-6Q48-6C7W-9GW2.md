# WO — Security Maintenance: certifi GHSA-6q48-6c7w-9gw2 + pillow (amended)

**Amendment (2026-10-21, Central Architecture):** this WO's scope is explicitly extended to cover `pillow==12.3.0`'s 8 disclosed CVEs (CVE-2026-112895/112400/112397/112896/112897/112395/112404/112899), fixed in `13.0.0`, alongside the original `certifi` fix. Governing reason: the WO's own mandatory "all seven GitHub checks pass" acceptance criterion is binding and not waivable by a pre-existing-vulnerability disclosure alone — `security/dependencies` and `security/container` cannot go GREEN while `pillow==12.3.0` remains pinned, so remediating it is now in scope. This amendment is recorded here, in Git, before any `pillow` implementation work began.

**Classification:** Isolated, expedited security-maintenance correction (now covering two packages: `certifi`, `pillow`). **Separate from PID-DBR-001** — does not touch deployment-boundary scope, does not alter Rogue's implementation authority.

**Governing authority:** INFOSECURS existing security architecture (`PID.md` — dependency pinning, `security/dependencies` CI gate) and the existing hash-locked build-reproducibility doctrine (`docs/delivery/BUILD-REPRODUCIBILITY.md`). Not a new feature or infrastructure campaign.

**Canonical starting `main`:** `49ca43a9416c2c3426ea3b9b270cd80b30f086bd`.

## Trigger

`security/dependencies` (`pip-audit -r requirements.txt`) failed on the post-merge check for `main` @ `49ca43a9...`, independent of and unrelated to that commit's own content (a documentation-only PR). Finding:

```
Found 1 known vulnerability in 1 package
Name    Version   ID                  Fix Versions
certifi 2026.7.22 GHSA-6q48-6c7w-9gw2 2026.10.19
```

`requirements.txt:13` pins `certifi==2026.7.22`.

## Scope

**In scope:** upgrade `certifi` to `2026.10.19` and `pillow` to `13.0.0` (both verified fixed versions), regenerate `requirements.txt` and `requirements-dev.txt` via the project's existing `pip-compile --generate-hashes` process, validate integrity/hashes, verify and minimise any unrelated resolver-driven changes, validate `pillow` 13's compatibility with `reportlab==5.0.1` (policy PDF generation — `policy/pdf.py`), run dependency audit + reproducible install/build tests + all applicable CI/security checks, independent audit of the final combined candidate, one bounded PR.

**Explicit exclusions:** no other package upgrade beyond what the resolver requires as a direct consequence of the `certifi`/`pillow` bumps and explicitly justifies; no M010 deployment; no persistent Beta change of any kind; no credential rotation; no CI suppression or advisory ignore; no alteration of Rogue's PID-DBR-001 authority or scope.

## Acceptance criteria

- `certifi==2026.10.19` present in both regenerated requirement files, with valid `--generate-hashes` hash entries.
- `pip-audit -r requirements.txt` clean (0 known vulnerabilities).
- Dependency diff reviewed line-by-line; every change beyond the `certifi` bump itself explained or reverted/minimised.
- All seven GitHub checks pass on the exact final head.
- Independent audit (fresh reviewer, no memory of this WO's own implementation) confirms the vulnerability is resolved and no unrelated change was introduced.
- Read-only assessment recorded of whether the persistent Beta's existing image contains the affected `certifi` version, and any TLS-client exposure implication — without inferring compromise from the advisory alone.
- `pillow==13.0.0` present in both regenerated requirement files with valid hashes; `pip-audit -r requirements.txt` fully clean (0 known vulnerabilities, both `certifi` and `pillow` resolved).
- Real `reportlab==5.0.1` PDF generation (policy PDF rendering, including the existing escaped-text/review-warnings test coverage) proven to still work correctly against `pillow==13.0.0` — Pillow 13's own backwards-incompatible changes checked against this codebase's actual Pillow usage, not assumed compatible.
- All seven GitHub checks (CodeQL, ci/unit, ci/integration, security/secrets, security/dependencies, security/sast, security/container) GREEN on the exact final combined head — the WO's binding acceptance criterion, not waived.

## Tests

`pip-audit` (both requirement files), `pip-compile --generate-hashes` regeneration + hash verification, a real `pip install --require-hashes -r requirements.txt` into a clean venv/disposable stack, the full existing CI suite (`ci/unit`, `ci/integration`) to confirm no behavioural regression from the dependency bump, and `security/sast`/`security/secrets`/`security/container` as already wired.
