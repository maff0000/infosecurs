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

## Branch/merge control

After bootstrap, `main` should normally receive product changes through PRs
with required checks where GitHub plan/features permit.

Do not invent a competing workflow engine to compensate for a missing premium
GitHub feature.

## Closure evidence

Important module/release closure records should identify:
- PID;
- PR;
- exact accepted SHA;
- applicable checks;
- Auditor verdict;
- accepted risks/exceptions.

Avoid storing huge agent transcripts or chain-of-thought as evidence.
