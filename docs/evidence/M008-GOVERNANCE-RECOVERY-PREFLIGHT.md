# M008 Governance Recovery — Implementer Preflight

**Work Order:** `docs/work-orders/WO-M008-GOV-RECOVERY-001.md`
**Amendment:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`
**Prepared by:** bounded Implementer, dispatched by the Delivery Controller (Gunnar)
**Date:** 2026-10-04
**Worktree:** `/srv/openclaw/worktrees/arch/m008-governance-recovery` on branch `arch/m008-governance-recovery` (dell-debian, `192.168.11.10`)

This document is **documentation/evidence only**. It records independently-verified facts in
preparation for the next, separately-dispatched phase of this Work Order (the fresh,
independent re-verification audit). It does not implement, repair, or test any product
behaviour, and it does not itself constitute that audit.

---

## 1. `origin/main` product SHA

Confirmed directly against the GitHub remote from this worktree:

```
$ git remote -v
origin  https://github.com/maff0000/infosecurs.git (fetch)
origin  https://github.com/maff0000/infosecurs.git (push)

$ git ls-remote origin main
6393912bc4f7a98e5d167a465369bf2a8ef26c57    refs/heads/main
```

This is identical to:
- the frozen product SHA named in `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md` and
  `docs/work-orders/WO-M008-GOV-RECOVERY-001.md` (`6393912bc4f7a98e5d167a465369bf2a8ef26c57`), and
- `HEAD~1` of this recovery branch (`git rev-parse HEAD~1` → `6393912bc4f7a98e5d167a465369bf2a8ef26c57`).

**`origin/main` = `6393912bc4f7a98e5d167a465369bf2a8ef26c57`.** Confirmed, not merely copied.

## 2. PR #86–#93 lineage (independently reconfirmed)

Reconfirmed via `gh api repos/maff0000/infosecurs/pulls/<n>` against the live GitHub history
(not copied from the Work Order without checking). Every merge SHA matched the Work Order's
table exactly:

| WI | PR | Title (from GitHub) | Merge SHA (from `gh api`) | Merged at |
|---|---|---|---|---|
| WI-ERRATA | #86 | [M008-WI-ERRATA] Add omitted Stage 1 facts, correct catalogue versioning, fix stale refs | `aa1048486f86f386333ea1ce2f1cbe1cc2b17cfd` | 2026-10-02T08:17:16Z |
| M008B-WI1 | #87 | [M008B-WI1] Structured methodology and canonical data spine | `ba571aaa087970f70e4580c1ae47bf41cb172d14` | 2026-10-02T09:27:31Z |
| M008C-WI2a | #88 | [M008C-WI2a] Guided Foundations journey, Stages 1-3 | `9a666eab3a6819f1e3e9e4f0025542b03206fb2a` | 2026-10-02T10:47:25Z |
| M008C-WI2b | #89 | [M008C-WI2b] Guided Foundations journey, Stage 4 | `a01c9ad3a4dc360caa0039169dbe2936d7cd7144` | 2026-10-02T11:27:26Z |
| M008C-WI3 | #90 | [M008C-WI3] Risks & Actions: confirmed/needing-confirmation split, free-text closure | `e6a0411e746b5acb9dbd60f86efb4d76ce7cc38d` | 2026-10-02T12:46:36Z |
| M008D-WI4 | #91 | [M008D-WI4] Deterministic Security Policy: normative/implementation-status split | `2dad84ebfc1af250af1241e3d465fb8ecccfbd88` | 2026-10-02T14:14:52Z |
| M008-WI5 | #92 | [M008-WI5] Home/navigation: guided-journey CTA, Needs Attention wording | `c23ec58e130be42da1327cc3127a8c4ccb2aedcd` | 2026-10-02T15:42:29Z |
| M008-WI6-REMEDIATION | #93 | [M008-WI6-REMEDIATION] Close 4 defects found by the M008 acceptance Auditor | `6393912bc4f7a98e5d167a465369bf2a8ef26c57` | 2026-10-02T18:31:56Z |

PR #93's merge SHA is identical to the frozen product SHA (`6393912...`) and to `origin/main`,
as expected — it is the final merge that produced the frozen base.

## 3. Parent PIDs and design artefacts this epic was built against

Confirmed by listing the actual repository contents at this worktree HEAD (not assumed):

**PIDs (`docs/pids/`):**
- `docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md` — master/parent PID for the epic
- `docs/pids/M008A-REPEATABLE-CUSTOMER-ZERO-RESET.md`
- `docs/pids/M008B-STRUCTURED-FOUNDATIONS-QUESTION-METHODOLOGY.md`
- `docs/pids/M008C-GUIDED-FOUNDATIONS-UX-AND-VISUAL-DESIGN.md`
- `docs/pids/M008D-INFORMATION-SECURITY-POLICY-QUALITY.md`

**Design artefacts (`docs/design/`):**
- `docs/design/M008-AI-COST-INVENTORY.md`
- `docs/design/M008-FREE-TEXT-REPLACEMENT-REGISTER.md`
- `docs/design/M008B-QUESTION-CATALOGUE.md`
- `docs/design/M008B-STAGES-1-3-CATALOGUE.md`
- `docs/design/M008C-UX-FLOW-DESIGN.md`
- `docs/design/M008D-POLICY-ARCHITECTURE.md`
- `docs/design/M008D-POLICY-TRUTH-MATRIX.md`
- `docs/design/M008D-SAMPLE-POLICIES.md`
- `docs/design/policies/M008D-implementation-status-a.pdf`
- `docs/design/policies/M008D-implementation-status-b.pdf`
- `docs/design/policies/M008D-implementation-status-c.pdf`
- `docs/design/policies/M008D-sample-policy-a.pdf`
- `docs/design/policies/M008D-sample-policy-b.pdf`
- `docs/design/policies/M008D-sample-policy-c.pdf`

No other `M008`-named PID or design artefact was found in `docs/pids/` or `docs/design/` at this
worktree HEAD.

## 4. This recovery Amendment and Work Order, by path

- `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`
- `docs/work-orders/WO-M008-GOV-RECOVERY-001.md`

Both are present in this worktree, committed in the single commit immediately preceding this
one (`a380e8c3c41fe9aa697a44a836e4599c309bba84`, parent `6393912bc4f7a98e5d167a465369bf2a8ef26c57`),
alongside `docs/architecture/DELIVERY-GOVERNANCE.md`.

## 5. Absence of historical Git-tracked M008 implementation Work Orders at recovery start

Checked directly:

```
$ git log --oneline --all -- docs/work-orders/
a380e8c [ARCH] M008 governance recovery: Phase 0 — record Architect authority
```

The only commit in the entire repository history (across all refs) that ever touches
`docs/work-orders/` is the recovery-authority commit itself, which added this Work Order. A
listing of the tree at the frozen SHA confirms the directory did not exist there:

```
$ git ls-tree -r 6393912bc4f7a98e5d167a465369bf2a8ef26c57 --name-only | grep -i work-order
(no output)
```

**Confirmed: no Git-tracked `docs/work-orders/` directory, and no WO-named document covering
PRs #86–#93, existed anywhere in this repository's history prior to this recovery.** This
matches the Amendment's expectation exactly.

## 6. Absence of durable pre-merge Project Architect acceptance for PRs #88–#93

Checked directly via `gh api repos/maff0000/infosecurs/pulls/<n>/reviews` and
`gh api repos/maff0000/infosecurs/issues/<n>/comments` for each of PRs #88, #89, #90, #91, #92,
and #93:

| PR | Reviews found | Issue comments found |
|---|---|---|
| #88 | none | none |
| #89 | none | none |
| #90 | none | none |
| #91 | none | none |
| #92 | none | none |
| #93 | none | none |

All six queries returned empty. **No recorded, durable, pre-merge Architect acceptance
artefact exists for PRs #88–#93.** This matches the Amendment's expectation exactly: these
merges occurred without a recorded acceptance step.

(PRs #86 and #87 were not checked for this purpose — the Amendment explicitly does not treat
them as governance violations, since they pre-date the point at which the new doctrine became
mandatory.)

## 7. Planned independent audit — commands/environments for the next phase

This section summarises, in my own words, the plan that `docs/work-orders/WO-M008-GOV-RECOVERY-001.md`
sets out for the next, separately-dispatched Independent Auditor. I am describing the plan only;
I have not executed any of it, and executing it is explicitly out of scope for this preflight.

- **Audit target:** the frozen product SHA `6393912bc4f7a98e5d167a465369bf2a8ef26c57`. If the
  recovery branch differs from that SHA only by the governance/evidence documents this Work
  Order names, the Auditor must first prove every non-document product path is byte-identical
  to the frozen SHA.
- **Independence requirement:** the Auditor must not inherit either of the two prior audits'
  conclusions — it re-derives every finding itself, from scratch, against the frozen SHA.
- **Real-Chromium install runbook:** `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md` exists in
  this repository and governs how real Chromium is installed at runtime for browser-acceptance
  testing — it must never be skipped or substituted with a stub/mocked browser.
- **Disposable-stack convention:** the repository's established pattern (visible across prior
  evidence records such as `docs/evidence/M007-BROWSER-ACCEPTANCE.md`,
  `docs/evidence/M007-AUDIT-0001.md`, `docs/evidence/M006-BACKUP-RESTORE.md`, and others) of
  standing up a disposable, isolated test/evaluation stack for a verification pass rather than
  running destructive or state-mutating checks against any persistent or shared environment.
  The next Auditor is expected to follow this same convention for its re-verification pass.
- **The 23-item checklist:** the Work Order's "Independent audit" section lists 23 specific,
  minimum proof points the Auditor must independently establish, spanning: the full test suite
  with real Chromium; a clean `manage.py makemigrations --check --dry-run`; a real-browser
  Customer Zero cycle (reset → login → Stages 1–4 → Risks & Actions → policy review/approval →
  policy PDF → reset again); tenant-isolation/adversarial reset proof; zero-LLM-call proof for
  the default Stages 1–6 path; GREEN bounded AI evaluation harnesses; UNKNOWN != NO holding
  throughout; `option_code`/methodology provenance round-tripping; distinct wording for
  materially different PARTIAL options; a normative-only distributable policy PDF; genuine
  absence (not merely unlinked) of the Foundation-tier free-text policy-edit path; no leakage of
  `review_warnings`/current-state gap language into the distributed PDF; the exact adopted
  "approval does not imply implementation or compliance" statement on the approval-confirmation
  screen; correct Customer Zero reset of the three-governance-role bootstrap contract across all
  prior-state scenarios; a keyboard-only real-browser walkthrough of at least one guided-journey
  stage; real-browser proof at 375px/768px/1280px; SHA-256 byte-equality backup/restore proof on
  a genuine evidence file; clean `gitleaks`; clean `pip-audit` with no unauthorised suppression;
  a clean Trivy CRITICAL/HIGH gate; green SAST/CodeQL and all other required CI checks; DARWIN
  (the unrelated product on this host, port 8000) left untouched; and the M006/M007 accepted
  release images left untouched. The Auditor may expand this set at its own discretion.
- **Required audit output:** a durable report at `docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md`
  containing the exact SHA audited, the exact branch/head tested, an explicit independence
  statement, the exact commands run and their results, how any failures were resolved (or why
  they were not product defects), the location of generated evidence, residual/open items, and
  an unequivocal GREEN or NOT GREEN verdict. Any product defect found means STOP — no repair is
  authorised under this Work Order; it returns to the Architect for a new Amendment and Work
  Order.

## 8. Explicit statement on PRODUCT_GREEN status

**This document does not claim M008 is already PRODUCT_GREEN.** Per
`docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md`, the product at the frozen SHA is
PROVISIONAL TECHNICAL GREEN / GOVERNANCE UNACCEPTED, and M008 remains open — not
PRODUCT_GREEN, not closed — until all seven closure conditions in that Amendment are met,
including a fresh, GREEN, independent re-verification audit (not yet performed as of this
document), a recovery PR, and a durable Project Architect Acceptance record issued only after
Central Architecture reviews the actual Git evidence. No actor other than the Project Architect
may declare M008 PRODUCT_GREEN.

---

## Scope confirmation

This Implementer created exactly one file —
`docs/evidence/M008-GOVERNANCE-RECOVERY-PREFLIGHT.md` — and made no other changes: no product
code, no tests, no migrations, no dependencies, no configuration, no runtime product data.
