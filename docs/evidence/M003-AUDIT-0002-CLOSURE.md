# M003 Audit Evidence — AUDIT-0002 (closure audit, tied to merged `main`)

**PID:** `docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md` §20, §27 + `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`
**Commit audited:** `9a37d599bd84e962fde9f0c07a4048d3ea484e78` (`main`, exactly — after PR #15's repair)
**Auditor:** fresh Claude Code `Agent` dispatch (general-purpose), zero inherited context — including no reliance on AUDIT-0001's transcript, a genuine independent re-drive of the full sequence.
**Verdict:** **GREEN**
**Trigger:** re-audit required after PR #15 repaired AUDIT-0001's PRODUCT RED finding.

## Why this audit exists

`M003-AUDIT-0001.md` found `PRODUCT_RED`: 5 of 9 required activity-event
types were never emitted. PR #15 (merged `9a37d599`) wired the 5 missing
`record_event()` calls into `evidence/services.py` and
`remediation/views.py`. Per this project's post-audit closure discipline,
a repair to product/runtime source requires a fresh Auditor before the
module can be considered closed — this is that audit, run as a full
re-drive of PID §20's 18-step sequence against the repaired commit, not
merely a check that the 5 event types now exist.

## Evidence block

```
AUDIT_VERDICT: GREEN
commit_sha: 9a37d599bd84e962fde9f0c07a4048d3ea484e78
server_fingerprint_verified: yes
port_released_verified: yes
non_vacuity_established: yes
real_browser_reproduction_completed: yes
root_cause_identified: n/a (verifying a fix, not diagnosing a new defect)
step1_fresh_docker_start_verified: yes
step2_customer_zero_login_verified: yes
step3_profile_baseline_assets_risk_verified: yes
step4_security_state_truthful_verified: yes
step5_upload_evidence_verified: yes
step6_supporting_evidence_label_verified: yes
step7_download_bytes_hash_headers_verified: yes
step8_external_reference_verified: yes
step9_contradiction_evidence_conflict_verified: yes
step10_stale_evidence_verified: yes
step11_supersede_withdraw_history_retained_verified: yes
step12_action_from_risk_verified: yes
step13_action_lifecycle_and_completion_evidence_verified: yes
step14_baseline_answer_non_mutation_verified: yes
step15_explicit_baseline_change_verified: yes
step16_activity_timeline_all_9_event_types_verified: yes
step17_cross_tenant_isolation_verified: yes
step18_console_errors_verified: yes
console_errors: 5, all tagged from the intentional cross-tenant 404 checks in step 17; zero in the primary sequence
findings: none
confidence: high
```

## Step 16 — the load-bearing check, verified two independent ways

All 5 previously-missing event types now fire, with counts matching the
number of times each operation was actually performed, confirmed both via
the rendered Activity page and a direct DB query (independent, agreeing
exactly):

| event_type | performed | rendered page | DB query |
|---|---|---|---|
| evidence_created | 6 | 6 | 6 |
| evidence_superseded | 1 | 1 | 1 |
| evidence_withdrawn | 1 | 1 | 1 |
| action_created | 1 | 1 | 1 |
| action_status_changed | 2 | 2 | 2 |
| control_answer_changed | 3 | 3 | 3 |
| evidence_linked / unlinked / action_evidence_linked | 5 / 1 / 1 | 5/1/1 | 5/1/1 |

Total 21 rows, exact match. Non-vacuity established properly: the Auditor
confirmed all 9 event-type counts were genuinely 0 on the fresh
organisation before driving any interaction, so the post-sequence counts
carry real information rather than being pre-seeded.

## Fingerprinting (repair-specific)

`git rev-parse HEAD` in the worktree matched the audited SHA.
`sha256sum evidence/services.py remediation/views.py` identical between
the host worktree and the running container, checked before and after a
full `down -v && up -d` rebuild. `grep` for the new emitter calls
(`EVENT_EVIDENCE_CREATED`/`SUPERSEDED`/`WITHDRAWN`,
`EVENT_ACTION_CREATED`/`STATUS_CHANGED`) inside the running container's
copies of both files confirmed the repair is actually what is running,
not a stale image.

## Other PID §20 criteria — independently re-driven, not assumed clean from AUDIT-0001

- Assurance-label precedence non-vacuity re-driven on the same control
  through the full cycle: Customer stated → Supporting evidence attached
  → Evidence conflict (contradiction outranks support) → back to
  Supporting evidence attached after superseding the support and
  withdrawing the contradiction. The Auditor caught and corrected its own
  measurement artifact mid-run (`innerText()` CSS-uppercasing the badge
  text vs. `textContent()`) rather than reporting a false result.
- Stale evidence, download integrity, history retention (superseded/
  withdrawn items remain reachable and listed, not 404), `BaselineAnswer`
  non-mutation (exactly 3 non-default rows after the full sequence,
  matching exactly the 3 explicit baseline-form submissions made),
  `unknown != no`, and cross-tenant isolation (second synthetic tenant,
  five surfaces checked, all ordinary 404s, zero leakage) all re-verified
  independently.
- No new or recurring defect found anywhere in the sequence.

## PL adjudication

Accepted as GREEN. The PL independently reviewed the repair diff itself
(not only the Auditor's characterisation of it) before this audit was
even dispatched — see PR #15's commit message and the PL's own `git diff`
review preceding merge — and independently re-ran the full test suite in
a separate throwaway stack before merging, rather than relying solely on
the repair Engineer's report. This audit is the required fresh-Auditor
confirmation on top of that, tied explicitly to the exact merged SHA.

## Closing status

M003 is `PRODUCT_GREEN` per PID §27:
1–14, 16–18 confirmed across AUDIT-0001 (unchanged, not re-litigated
where AUDIT-0001 already found them clean and no touched file could have
affected them) and this audit's full independent re-drive; §27.15 (all
required GitHub checks GREEN on the closing head) and §27.19 (GUNNAR
verifies GitHub truth) are confirmed separately by the PL against the
GitHub API directly, not delegated to the Auditor; §27.17 (closure obeys
the post-audit delta doctrine) is satisfied by this document's own
existence — the repair triggered exactly the fresh-Auditor requirement
the doctrine calls for, rather than being waved through; §27.18 (merged
`main` reproduces the accepted result from a fresh clone) is what this
audit's fresh-Docker-data, fresh-worktree run demonstrates directly.
