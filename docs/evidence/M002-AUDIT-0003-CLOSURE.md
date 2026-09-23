# M002 Audit Evidence — AUDIT-0003 (closure audit, tied to merged `main`)

**PID:** `docs/pids/M002-SECURITY-BASELINE-AND-INITIAL-RISK.md` §0 + `docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`'s post-audit closure-delta doctrine
**Commit audited:** `86dd495a059fa0de0864437c12662a7b1085edcb` (`main`, exactly)
**Auditor:** fresh Claude Code `Agent` dispatch (general-purpose), zero inherited context — including no reliance on AUDIT-0002's verdict.
**Verdict:** **GREEN**
**Trigger:** Central Architecture closure review, 2026-09-23.

## Why this audit exists

`docs/evidence/M002-AUDIT-0002.md` audited commit `7348ecf`. The PR that
merged M002 to `main` (`d87b487` → `86dd495`) included one further commit
that touched a product source file, `risk_register/interpretation_views.py`
— a docstring correction, made alongside landing the AUDIT-0002 evidence
itself. Per this project's own post-audit closure-delta doctrine
(`docs/delivery/GITHUB-EVIDENCE-CONTRACT.md`): **any delta to a
product/runtime source file after an audit means the prior audit no longer
closes the new head, regardless of how small the delta looks.** That rule
was applied, not waived, even though Central Architecture's own inspection
of the diff (and this audit's independent confirmation of it) found it to
be comment-only. The PL should have run this audit before merging and did
not — a process gap, corrected here before M002 is recorded closed.

## Evidence block

```
AUDIT_VERDICT: GREEN
commit_sha: 86dd495a059fa0de0864437c12662a7b1085edcb
server_fingerprint_verified: yes
port_released_verified: yes
non_vacuity_established: yes
real_browser_reproduction_completed: yes
root_cause_identified: n/a (closure re-audit of a comment-only delta; no defect found)
full_automated_test_suite_verified: yes (484 passed, 0 failed, reproduced twice)
tenant_isolation_verified: yes (11/11 manipulated URL shapes -> 404, zero 403, zero real data)
single_canonical_answer_bidirectional_verified: yes
deterministic_generation_and_regeneration_safety_verified: yes (DB-level)
ai_interpretation_suggestion_only_verified: yes
docstring_only_change_confirmed_no_behavioural_difference_verified: yes
console_errors: none unexplained (11 total entries, all the browser's own report of the deliberate cross-tenant 404 probes)
findings: none
confidence: high
```

## Requirement 9 — docstring-only delta, confirmed both ways

**Statically**, spot-checked directly by the PL (not only asserted by the
Auditor): `git diff 7348ecf 86dd495 -- risk_register/interpretation_views.py`
shows the entire diff falls inside the module's triple-quoted docstring —
no code line, no whitespace-significant change, no import change.

**Behaviourally**, the Auditor drove the view this file defines through a
genuine failure path (killed its own stub gateway mid-session, confirmed
by socket-connect that the port was actually closed, then clicked "Ask AI
to review drafts" for real and confirmed every risk's rationale was
byte-for-byte unchanged) and a genuine success path (restarted the stub,
clicked again, confirmed exactly one risk's rationale changed and the
`Risk` count stayed identical before/after — no new row). Both paths
behave exactly as the unchanged code declares.

## The ten required verification points (Central Architecture's exact list)

1. **Started from the exact SHA**, own worktree, fresh build — confirmed via content-hash fingerprint of three key files (`interpretation_views.py`, `scenario_engine.py`, `interpretation_contracts.py`), checked twice (after initial build, again after a container recreate for env vars).
2. **App builds and starts cleanly** — yes.
3. **Full automated suite** — 484/484, run twice (before and after the browser session), identical both times.
4. **Real-browser acceptance flow** — driven in full: profile → baseline (all 5 answer states, verified persisted) → assets (starter suggestions, confirm/edit/dismiss, DB-verified editing never silently confirms) → asset-detail protection checks → risk generation → AI interpretation → edit/confirm/dismiss → reload → regeneration → cross-tenant probing → console-error check.
5. **Tenant isolation** — 11 manipulated-URL shapes across organisation, asset, baseline and risk resources; all 404; zero 403; zero real data.
6. **Single-canonical-answer, bidirectional** — `device_encryption` changed from the asset page → visible on the general baseline page; changed back from the general baseline page → visible on the asset page. A genuine round trip in both directions, not an initial-load match.
7. **Deterministic generation + regeneration safety** — a second "Find candidate risks" click correctly proposed nothing new; confirmed at the database level (not the UI's own message) that the row count stayed at 4, the confirmed risk's edited values were intact, the dismissed risk's status was untouched, and every `(scenario_id, key_asset_id)` dedup key stayed unique.
8. **AI interpretation is suggestion-only** — updates existing draft fields, status stays "AI suggested — not yet confirmed," `Risk.objects.count()` unchanged before/after a successful interpretation call.
9. **Docstring-only change confirmed** — see above.
10. **Verdict tied explicitly to `86dd495`** — recorded throughout this document and the evidence block.

## Live AI evaluation — not re-run, per explicit Central Architecture ruling

`docs/evidence/M002-LIVE-EVALUATION-CORRECTED.md` (against real `trinity-core`,
8/8 green) remains valid evidence for this closure: the AI implementation,
prompt, and evaluation path did not change between that run and this
commit — only a docstring did. This audit's own AI-interpretation step used
a disposable local stub (not the live gateway), matching AUDIT-0002's
approach, to verify application wiring/behaviour, not AI response quality.

## Additional non-vacuity: the `unknown != no` invariant, observed live

Not one of the ten required points, but recorded because it's a direct,
unprompted confirmation of PID §0.4a operating correctly on a real
generated risk: with `patching=unknown` in the baseline, the resulting
risk's vulnerability text read *"It is not confirmed whether operating
system and application security patches are applied..."* — hedged, not an
assertive absence claim — with a matching assumption
(`baseline.patching: control state not confirmed`). This is the
architecture's own central invariant, observed in the running product, not
only in a unit test.

## Mechanical cross-tenant-AI-payload coverage (code-level, backs the live proof)

Confirmed present and passing among the 484:
`ai_platform/tests/test_interpretation_prompts.py::test_organisation_id_never_appears_in_the_outbound_wire_payload`,
`::test_wire_payload_never_contains_an_identifier_shaped_field_name`,
`risk_register/tests/test_tenant_isolation.py::test_org_as_generation_ignores_org_bs_answer_to_the_same_control`,
`::test_org_as_generation_never_creates_a_risk_referencing_org_bs_asset` —
directly targeting PID §16's "critical" cross-tenant AI-payload rule.

## PL adjudication

Accepted as GREEN. Spot-checked directly (routine per SKILL.md §7, and
specifically warranted here since this audit exists because of a PL
process gap in the first place): confirmed the Auditor's worktree was
clean at `86dd495`, and independently re-ran
`git diff 7348ecf 86dd495 -- risk_register/interpretation_views.py` myself
rather than accepting the Auditor's characterisation of it — the diff is
exactly what was claimed.

## Process correction, for the record

The docstring fix should have triggered its own audit before merge — it
didn't, because the PL (Gunnar) treated a comment-only change to a
product/runtime file as obviously safe and folded it into the evidence
commit instead of routing it through the doctrine that already existed for
exactly this case. Central Architecture caught it on independent GitHub
review. No repair was needed because the change was genuinely inert, but
the doctrine was correct to require checking that, not assuming it. This
audit is that check, run after the fact rather than before merge, which is
the gap being corrected going forward: any future product-file touch after
an audit, however small, gets a fresh Auditor dispatch before merge, not
after.
