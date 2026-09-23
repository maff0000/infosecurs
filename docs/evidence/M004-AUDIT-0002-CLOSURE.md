# M004 Audit Evidence — AUDIT-0002 (closure audit, tied to merged `main`)

**PID:** `docs/pids/M004-POLICY-FOUNDATION.md` §27, §30 + `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`
**Commit audited:** `bcc4641741c4cc44b1e2f60f272f560edc871189` (`main`, exactly — after PR #23's repair)
**Auditor:** fresh Claude Code `Agent` dispatch (general-purpose), zero inherited context — including no reliance on AUDIT-0001's transcript, a genuine independent re-drive of the full 20-step sequence.
**Verdict:** **GREEN**
**Trigger:** re-audit required after PR #23 repaired AUDIT-0001's PRODUCT RED finding and two secondary findings.

## Why this audit exists

`M004-AUDIT-0001.md` found `PRODUCT_RED` (blank date pickers) plus two
secondary findings (duplicate form ids; no Account-Holder self-edit path).
PR #23 (merged `bcc4641`) fixed all three. Per this project's post-audit
closure discipline, a repair to product/runtime source requires a fresh
Auditor before the module can be considered closed — this is that audit,
run as a full re-drive of all 20 PID §27 steps against the repaired
commit, not merely a check that the three fixes work in isolation.

## Evidence block

```
AUDIT_VERDICT: GREEN
commit_sha: bcc4641741c4cc44b1e2f60f272f560edc871189
server_fingerprint_verified: yes
port_released_verified: yes
non_vacuity_established: yes
real_browser_reproduction_completed: yes
root_cause_identified: n/a (repair verification, not a new defect investigation)
step2_returning_identity_verified: yes
step3_create_organisation_verified: yes
step4_edit_my_details_finding3_verified: yes
step5_default_roles_verified: yes
step6_reassign_role_finding2_verified: yes
step7_8_hybrid_workplace_derivation_verified: yes
step9_baseline_data_verified: yes
step10_generate_draft_verified: yes
step11_pdf_2to4_pages_verified: yes
step12_no_unsupported_claims_verified: yes
step13_edit_section_finding1_edit_page_verified: yes
step14_external_approval_finding1_approve_page_verified: yes
step14b_direct_approval_verified: yes
step15_download_approved_artefact_verified: yes
step16_direct_vs_external_wording_verified: yes
step17_new_draft_previous_version_immutable_verified: yes
step18_cross_tenant_isolation_verified: yes
step19_activity_events_verified: yes
step20_console_clean_and_date_warnings_absent_verified: yes
console_errors: none
findings: none
confidence: high
```

## Fingerprinting (repair-specific)

Before driving any interaction, asserted the loaded `policy.forms`/
`governance.views` module source (`inspect.getsource`, same Python process
serving `live_server`) contains `format="%Y-%m-%d"`, `prefix=role_key`/
`prefix=submitted_role_key`, and `governance.views.edit_my_details` — all
three repaired symbols present and genuinely running, not a stale
environment. Worktree `git rev-parse HEAD` matched the audited SHA
throughout.

## The three findings — re-verified with genuine round-trips, not just "looks fixed"

**Finding 1 (blank date pickers).** Filled the edit page's date field,
submitted, **reloaded from scratch**, re-read the computed DOM `.value`
(Playwright's `input_value()`, not the raw HTML attribute) — exact value
round-tripped correctly. Repeated on both the external- and
direct-approval pages, additionally proving the field is genuinely
*editable* (changed the value, confirmed the changed value — not the
default — persisted to the DB).

**Non-vacuity, positively proven, not assumed**: built an isolated
negative control reproducing the exact pre-fix widget shape (`DateInput`
with no `format=` kwarg) under this project's real `LANGUAGE_CODE="en-gb"`,
rendered it, loaded it in a real browser: raw HTML `value="15/06/2027"`
present, but computed DOM `.value` = `""` — reproducing Finding 1 exactly.
The fixed shape's computed value was `"2027-06-15"`. This proves the check
used throughout the run is genuinely capable of failing, and fails
specifically the way AUDIT-0001 found and specifically stops failing after
this repair. Console corroboration: the prior audit's exact `"does not
conform to the required format, yyyy-MM-dd"` warnings are absent; the
console-listener mechanism itself independently proven capable of
capturing real warnings (a synthetic test), so "zero captured" is not a
silently-broken listener.

**Finding 2 (duplicate ids).** Checked `document.querySelectorAll('[id]')`
across the whole role-assignments page both before and after a real
reassignment (to a newly-created "Nadia Farouk, Office Manager") — zero
duplicate ids either time, and each row's `label[for="id_<role>-person"]`
resolved to that row's own `<select>`.

**Finding 3 (no self-edit path).** Filled and submitted the real form,
**reloaded from scratch**, re-read the persisted values from the DOM —
correct. Adversarial scope test: a second synthetic organisation/user
attempted `GET` on organisation A's `edit_my_details` URL from organisation
B's own session — ordinary 404, no leakage — exactly the failure mode a
wrong-scope implementation would have exposed.

## Everything else in the 20-step sequence — full independent re-run, not assumed from AUDIT-0001

Federated login/returning-identity, organisation creation, default role
assignment, hybrid workplace onboarding and `working_model` derivation,
baseline completion, draft generation, content inspection, direct vs.
external approval (wording confirmed genuinely different side by side:
*"Approved directly by Alice Adams (Policy Authoriser)."* vs. *"External
approval recorded by Alice Adams; authoriser: Nadia Farouk, Office
Manager."*), PDF download with an independent page-count cross-check
(`pypdf`, against both the downloaded bytes and a freshly-rendered
in-process copy) agreeing at 2 pages, new-draft-from-approved proven to
leave the prior version's content byte-identical even after heavy edits to
the new draft, full cross-tenant probe suite (six surfaces including the
new `edit_my_details` endpoint) all correctly 404 with non-vacuity
established first, and all expected M004 activity event types present.

No new or recurring defect found anywhere in the sequence.

## PL adjudication

Accepted as GREEN. The PL independently reviewed the repair diff itself
(not only the Auditor's characterisation) before this audit was dispatched
— see PR #23's commit message and the PL's own `git diff` review and
direct rendered-HTML spot-check preceding merge — and independently
re-ran the full test suite in a separate throwaway stack before merging,
rather than relying solely on the repair Engineer's report. This audit is
the required fresh-Auditor confirmation on top of that, tied explicitly to
the exact merged SHA.

## Closing status

M004 is `PRODUCT_GREEN` per PID §30: all functional criteria (1-23)
satisfied across AUDIT-0001 (unchanged, not re-litigated where AUDIT-0001
already found them clean and no touched file could have affected them) and
this audit's full independent re-drive; §30.24 (live policy-generation AI
evaluation GREEN) satisfied separately by `docs/evidence/
M004-LIVE-EVALUATION.md`; §30.25 (all M001-M003 regressions remain GREEN)
satisfied by the full test suite passing throughout every integration in
this delivery; §30.26 (all required GitHub checks GREEN on the closing
head) and confirmed directly against the GitHub API, not delegated to the
Auditor; §30.27 (fresh FORGE Auditor GREEN on the exact audited SHA) is
this document; §30.28 (closure obeys the post-audit delta doctrine) is
satisfied by this document's own existence — the repair triggered exactly
the fresh-Auditor requirement the doctrine calls for; §30.29 (merged `main`
reproduces the accepted result from a fresh clone) is what this audit's
fresh-Docker-data, fresh-worktree run demonstrates directly.
