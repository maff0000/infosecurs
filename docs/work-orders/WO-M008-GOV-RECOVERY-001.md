# WO-M008-GOV-RECOVERY-001 — M008 Governance Recovery

**Parent PID:** `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
**Applicable Amendment:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`
**Exact product base:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Status:** APPROVED FOR DELIVERY CONTROLLER DISPATCH

## Purpose

Recover M008 governance without pretending the historical implementation sequence followed the new delivery-governance doctrine (`docs/architecture/DELIVERY-GOVERNANCE.md`). This Work Order is **documentation/evidence/re-verification work only**. It does **NOT** authorise product repair.

## Historical implementation lineage (verify independently)

| WI | PR | Merge SHA |
|---|---|---|
| WI-ERRATA | #86 | `aa1048486f86f386333ea1ce2f1cbe1cc2b17cfd` |
| M008B-WI1 | #87 | `ba571aaa087970f70e4580c1ae47bf41cb172d14` |
| M008C-WI2a | #88 | `9a666eab3a6819f1e3e9e4f0025542b03206fb2a` |
| M008C-WI2b | #89 | `a01c9ad3a4dc360caa0039169dbe2936d7cd7144` |
| M008C-WI3 | #90 | `e6a0411e746b5acb9dbd60f86efb4d76ce7cc38d` |
| M008D-WI4 | #91 | `2dad84ebfc1af250af1241e3d465fb8ecccfbd88` |
| M008-WI5 | #92 | `c23ec58e130be42da1327cc3127a8c4ccb2aedcd` |
| M008-WI6-REMEDIATION | #93 | `6393912bc4f7a98e5d167a465369bf2a8ef26c57` |

## Implementer scope

Dispatch one bounded Implementer. It may create **only**:

```
docs/evidence/M008-GOVERNANCE-RECOVERY-PREFLIGHT.md
```

That document must record:

- the `origin/main` product SHA;
- the exact PR #86–#93 lineage (the table above, independently reconfirmed against `git`/`gh`, not merely copied);
- the parent PIDs/design artefacts this epic was built against;
- the recovery Amendment and this Work Order, by path;
- the absence of historical Git-tracked M008 implementation Work Orders at recovery start;
- the absence of durable pre-merge Project Architect acceptance for the post-doctrine merges (PRs #88–#93);
- the planned independent audit commands/environments the next phase of this Work Order will use;
- an explicit statement that this document does **not** claim M008 is already PRODUCT_GREEN.

**Non-negotiable boundaries for the Implementer:**
- No product code.
- No tests changed.
- No migrations.
- No dependencies.
- No configuration.
- No runtime product data.

After committing the preflight document, the Implementer **STOPS**. It does not proceed to the audit phase, does not open a PR, and does not touch anything outside the one file named above.

## Independent audit

Dispatch a genuinely fresh Independent Auditor. It receives this Work Order and the governing M008 PIDs/design documents, but **must not inherit either previous Auditor's conclusion** — it independently re-derives everything itself.

**Audit target:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`.

If the recovery branch differs from that SHA only by authorised governance/evidence documentation (the files this Work Order names), the Auditor must prove that every non-document product path remains byte-identical to the frozen product SHA.

The Auditor must independently prove, at minimum:

1. full repository test suite with real Chromium (installed at runtime per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`, never skipped);
2. `manage.py makemigrations --check --dry-run` is clean;
3. a real-browser Customer Zero cycle: reset → login → Stages 1–4 → Risks & Actions → policy review/approval → policy PDF → reset again;
4. tenant-isolation / adversarial reset proof;
5. the default Stages 1–6 path generates zero LLM calls;
6. the bounded AI evaluation harnesses all remain GREEN;
7. UNKNOWN != NO holds throughout (risk presentation, implementation status, approval gating);
8. `option_code`/methodology provenance round-trips correctly;
9. materially different PARTIAL options produce distinct status/action wording (not a shared generic sentence);
10. the distributable policy PDF remains normative-only;
11. the Foundation-tier free-text policy-edit path is genuinely absent (not merely unlinked);
12. `review_warnings`/current-state gap language does not leak into the distributed PDF;
13. policy approval does not imply implementation or compliance (the exact adopted statement is present and persistent on the approval-confirmation screen);
14. the Customer Zero reset restores the governed three-governance-role bootstrap contract, in every prior-state scenario (already correct, fully reassigned away, partially reassigned);
15. a keyboard-only real-browser walkthrough of at least one full guided-journey stage;
16. real-browser proof at 375px / 768px / 1280px viewport widths;
17. backup/restore with SHA-256 equality of a genuine, real evidence file's bytes before and after restore;
18. `gitleaks` clean;
19. `pip-audit` clean, with no unauthorised suppression/ignore in effect;
20. Trivy CRITICAL/HIGH gate clean;
21. SAST / CodeQL and every other required CI check green;
22. DARWIN (the unrelated product on this host, port 8000) is untouched;
23. the M006/M007 accepted release images are untouched.

The Auditor may expand this test set at its own discretion if it judges additional verification necessary.

### Audit output

The Auditor must create a durable report at:

```
docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md
```

containing, at minimum:

- the exact product SHA audited;
- the exact recovery branch/head tested;
- an explicit independence statement (confirming it did not inherit either prior audit's conclusion);
- the exact commands run;
- the results of each;
- any failures encountered, and how each was resolved or why it was not a product defect;
- the location of all evidence it generated;
- any residual/open items;
- an unequivocal **GREEN** or **NOT GREEN** verdict.

**If the Auditor identifies ANY product defect: STOP.** No repair is authorised by this Work Order. The defect returns to the Project Architect for a new Amendment and a new Work Order.

## PR

Only after a GREEN independent audit report is committed may the recovery PR be opened.

**Permitted paths only** — this PR may touch nothing else:

```
docs/architecture/DELIVERY-GOVERNANCE.md
docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md
docs/work-orders/WO-M008-GOV-RECOVERY-001.md
docs/evidence/M008-GOVERNANCE-RECOVERY-PREFLIGHT.md
docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md
```

No product paths. All repository-required CI checks must be green before the stop gate below is reached.

The eventual Project Architect acceptance record is **not** created by this Work Order — it is added only after this PR is returned to Central Architecture and the Architect has reviewed the actual Git evidence.

## Mandatory Architect stop gate

Once the recovery PR exists, the independent audit is GREEN, and all required CI checks are GREEN:

**STOP. DO NOT MERGE.**

Return to Central Architecture with:

1. the recovery branch/head SHA;
2. the audited frozen product SHA;
3. the preflight document's path;
4. the independent audit's path and verdict;
5. the test/security/browser/AI results summary;
6. the PR number;
7. the complete changed-path list for that PR;
8. every CI/check conclusion;
9. any residuals.

The Project Architect will then review the actual Git evidence. If accepted, Central Architecture will issue the durable Architect Acceptance record and only then authorise merge.

**No other actor may declare M008 PRODUCT_GREEN.**
