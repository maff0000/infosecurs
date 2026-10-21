# WO — Security Maintenance: certifi GHSA-6q48-6c7w-9gw2

**Classification:** Isolated, expedited security-maintenance correction. **Separate from PID-DBR-001** — does not touch deployment-boundary scope, does not alter Rogue's implementation authority.

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

**In scope:** upgrade `certifi` to `2026.10.19` (the verified fixed version), regenerate `requirements.txt` and `requirements-dev.txt` via the project's existing `pip-compile --generate-hashes` process, validate integrity/hashes, verify and minimise any unrelated resolver-driven changes, run dependency audit + reproducible install/build tests + all applicable CI/security checks, independent audit of the final candidate, one bounded PR.

**Explicit exclusions:** no other package upgrade beyond what the resolver requires as a direct consequence of the `certifi` bump; no M010 deployment; no persistent Beta change of any kind; no credential rotation; no CI suppression or advisory ignore; no alteration of Rogue's PID-DBR-001 authority or scope.

## Acceptance criteria

- `certifi==2026.10.19` present in both regenerated requirement files, with valid `--generate-hashes` hash entries.
- `pip-audit -r requirements.txt` clean (0 known vulnerabilities).
- Dependency diff reviewed line-by-line; every change beyond the `certifi` bump itself explained or reverted/minimised.
- All seven GitHub checks pass on the exact final head.
- Independent audit (fresh reviewer, no memory of this WO's own implementation) confirms the vulnerability is resolved and no unrelated change was introduced.
- Read-only assessment recorded of whether the persistent Beta's existing image contains the affected `certifi` version, and any TLS-client exposure implication — without inferring compromise from the advisory alone.

## Tests

`pip-audit` (both requirement files), `pip-compile --generate-hashes` regeneration + hash verification, a real `pip install --require-hashes -r requirements.txt` into a clean venv/disposable stack, the full existing CI suite (`ci/unit`, `ci/integration`) to confirm no behavioural regression from the dependency bump, and `security/sast`/`security/secrets`/`security/container` as already wired.
