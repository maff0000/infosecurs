# Infosecurs — GitHub Evidence Contract

## Governing invariant

> **PROJECT TRUTH == GITHUB**

A delivery claim is not authoritative until tied to GitHub state for the exact
implementation under consideration.

## Initial evidence classes

Establish native GitHub checks approximately equivalent to:

```text
ci/unit
ci/integration
security/secrets
security/dependencies
security/sast
security/container
```

FORGE audit remains an independent gate and must be durably tied to the exact
audited SHA/PR.

Later add only when corresponding behaviour exists:

```text
qa/acceptance
ai-eval/risk
ai-eval/questionnaire
ai-eval/prompt-injection
```

## SHA rule

A GREEN on SHA A is not evidence for SHA B.

### Post-audit closure-delta rule

Added 2026-09-22, Central Architecture governance closure amendment (carried
in `docs/evidence/M001-AUDIT-0001.md`'s correction section). Applies whenever
GitHub's tree moves after an Auditor verdict but before a module is treated
as closed:

- **Evidence-only delta after audit.** Only evidence artefacts changed
  (e.g. `docs/evidence/**`). No product re-audit required, provided
  product/runtime tree identity against the audited SHA is proven — not
  assumed — e.g. `git diff --stat <audited_sha> <new_head> -- . ':!docs/evidence'`
  returns empty.
- **CI/control-plane-only delta.** Only CI/workflow/tooling configuration
  changed (e.g. `.github/workflows/**`), with product/runtime tree identity
  against the audited SHA proven the same way. No product re-audit required,
  but every affected GitHub check must actually rerun and pass on the new
  head — a config change is not self-certifying.
- **Any product/runtime delta after audit.** If anything outside the two
  categories above changed, the previous product audit no longer closes the
  new head. A fresh Auditor dispatch against the new head is required before
  the module can be treated as closed.

Closure evidence for a module affected by any post-audit delta must record
**both** the audited product SHA and the final closure/merge SHA, with the
diff-identity proof (or the fresh re-audit) linking them — not merely the
final SHA on its own.

## Branch protection

`main` is governed by GitHub repository ruleset `main-governance`
(id `23843330`, created 2026-09-22): PR required (no direct push),
`ci/unit` / `ci/integration` / `security/secrets` / `security/dependencies` /
`security/sast` / `security/container` required as merge-blocking status
checks, force-push/history-rewrite blocked (`non_fast_forward`), branch
deletion blocked. `current_user_can_bypass: never` for the operating
identity — live-verified by a rejected direct-push attempt at creation time,
not just read back from the API. M001 (PR #1) merged **before** this
ruleset existed — see the correction in `docs/evidence/M001-AUDIT-0001.md`
for what that means for M001's own checks' enforcement status at the time.

## Tool direction

Prefer established tools:
- pytest / Django test tooling;
- gitleaks;
- dependency audit tooling;
- Semgrep and/or CodeQL where available;
- Trivy or equivalent;
- GitHub Actions;
- SARIF upload where supported.

Do not build custom scanners.

Accepted base-image digests, the dependency lock mechanism, pinned Actions
commit SHAs and the runner generation are recorded durably in
`docs/delivery/BUILD-REPRODUCIBILITY.md` — that file, not this one, is where
"what exactly does the accepted build depend on" is answered.

## Branch/merge control

After bootstrap, `main` should normally receive product changes through PRs
with required checks where GitHub plan/features permit.

Do not invent a competing workflow engine to compensate for a missing premium
GitHub feature.

## Closure evidence

Important module/release closure records should identify:
- PID;
- PR;
- exact audited product SHA, and the final closure/merge SHA if it differs
  (per the post-audit closure-delta rule above);
- applicable checks;
- Auditor verdict;
- accepted risks/exceptions.

Avoid storing huge agent transcripts or chain-of-thought as evidence.
