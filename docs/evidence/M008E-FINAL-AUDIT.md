# M008E-WI2 — PR #99 Independent Audit: Final Technical / Security Audit

**Audited head SHA:** `b9e7b70337c17a6fbaa414d8a5924efe3727c7d9`
**Base SHA:** `4631389d82697b1c2c222254756b4c900fecf395`
**PR:** https://github.com/maff0000/infosecurs/pull/99 ("M008E-WI2 — Approved Visual System Full Rollout")
**Auditor:** fresh Independent Audit agent, never the Implementer of Increments 1–4
**Verdict: GREEN**

This PR head was re-confirmed unchanged immediately before this audit was written: `gh pr view 99 --json headRefOid` returned `b9e7b70337c17a6fbaa414d8a5924efe3727c7d9` (state `OPEN`, `mergeable: MERGEABLE`, base `main`) — identical to the frozen audit target throughout.

## 1. Isolation

`git -C /srv/infosecurs worktree add /srv/openclaw/worktrees/audit/pr-99 b9e7b70337c17a6fbaa414d8a5924efe3727c7d9` — detached HEAD at `b9e7b70`. `git merge-base --is-ancestor 4631389d82697b1c2c222254756b4c900fecf395 HEAD` → success. `git cat-file -t` on both SHAs → `commit`. `/srv/infosecurs` and `/srv/openclaw/worktrees/wo/M008E-WI2-order` were never touched (no writes, no `cd` with side effects — confirmed by this audit's own command history; `git worktree list` at the end of this audit still shows all three worktrees present and distinct).

## 2. Complete diff-scope confirmation

`git diff 4631389d82697b1c2c222254756b4c900fecf395..b9e7b70337c17a6fbaa414d8a5924efe3727c7d9 --stat`: **266 files changed, 2957 insertions(+), 138 deletions(-)**. Of these, 244 are PNG screenshots (before/after pairs across the four increments, non-reviewable as text) and 4 are the increments' own evidence Markdown narratives. The **actual reviewable change surface** is 32 files:

- 1 new PID-adjacent doc: `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md`.
- 6 new disposable, non-application scripts: `scripts/_m008e_wi2_incr{1,2,3,4}_capture.py`, `_incr{2,3,4}_seed.py` — all read before trusting them; none are wired into `manage.py`, Django app config, URLconf, or CI; all explicitly self-documented as "not part of the application," ORM-only where they write data, and the capture scripts' only runtime write is screenshot PNGs to disk.
- 1 shared stylesheet: `static/organisations/css/app.css` (77 insertions — `.table`/`.table-wrap`, `.empty-state--left`, removal of the two dead `.stage-indicator`/`.stage-progress` rules; **zero changes** to `.progress`, `.shell-nav__link[aria-current="page"]:focus-visible`, or any other rule tied to either permanent regression class).
- 24 template files across `activity`, `evidence` (×4), `governance`, `key_assets`, `organisations` (×5), `policy` (×3), `questionnaire` (×2), `remediation`, `risk_register` (×2), `security_state` (×2), `templates/identity`, `templates/registration`, `workplace`.

**Explicitly confirmed zero diff** on every security/product-logic surface:
- `organisations/views.py` — **zero diff** (`git diff ... -- organisations/views.py` returns nothing). This is the file housing the Customer Zero reset view and its fail-closed gate (`settings.CUSTOMER_ZERO_RESET_ENABLED` check, `_customer_zero_reset_enabled_for`) — byte-identical to base, as the governing Work Order requires.
- **Every `**/views.py` in the repository** — zero diff.
- **Every `**/migrations/*.py`** — zero diff. No WI2 migration exists.
- **`requirements.txt`/`requirements.in`/`requirements-dev.txt`/`requirements-dev.in`/`package.json`** — zero diff (no `package.json` exists in this repo at all; confirmed no dependency manifest of any kind changed).

## 3. Whole-product UX review

See `docs/evidence/M008E-ACCESSIBILITY-UX-AUDIT.md` for the full review. **Verdict: the product now reads as one coherent, commercially credible SME SaaS application.** Specific defects independently found and confirmed fixed (not merely narrated): the two fully-unstyled Policy "Implementation status" `<table>`s now have a real `.table`/`.table-wrap` component; six separate list-style card components across five apps are now on one consistent radius step; the Customer Zero reset-confirmation page's submit button now matches the severity signal its own upstream entry points already give it; `questionnaire/response_detail.html`'s three hardcoded/near-duplicate hex colours (including an invented fifth "superseded" status colour the design doctrine explicitly forbids) are now reading the same named design tokens every other badge in the product uses.

## 4. 1280 / 768 / 375 real-browser results

See `docs/evidence/M008E-BROWSER-RESPONSIVE.md` for the full table. **93/93 checks pass** (31 surfaces × 3 widths) — zero horizontal overflow anywhere, measured via real Chromium `scrollWidth`/`clientWidth` comparison, not inferred from source. Chromium launch was explicitly proven (`playwright.chromium.launch()` + a real `goto()` + title/content check) before any of these results were trusted, per this Work Order's own documented history of this exact failure mode costing prior reviewers time.

## 5. Novice-journey result

Full journey run for real, authenticated as Customer Zero: login → Home → Foundations → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Risks & Actions → Security Policy → Security State → Assets → Risks → Evidence → Remediation → Company → Profile → Governance → Workplace → Activity → Customer Assurance → Customer Zero reset control located → reset confirmation page. Every step returned HTTP 200. The reset control was located on Home via its own rendered `.dev-panel` (dashed border, "Dev" tag, plain `<a>` link — never a form of its own) pointing to the canonical `/organisations/<id>/dev-tools/reset/` route. Gating was independently re-proven at runtime with `override_settings(CUSTOMER_ZERO_RESET_ENABLED=False)` → panel absent; restored → panel present. **The reset was never executed during this audit** — no defect required proving it, so it was not run.

## 6. Security / product invariants — independently verified

| Invariant | How verified | Result |
|---|---|---|
| Tenant isolation | `*/tests/test_tenant_isolation.py` across every touched app, run as part of the full suite (§8) | All pass |
| Entitlement/tier behaviour | `organisations/tests/test_home_reset_panel.py::test_visible_regardless_of_package_tier` (reset panel renders across every tier) + `entitlements/tests/*` in the full suite | All pass; unrelated code (`entitlements/`) has zero diff |
| Current routes | Every `reverse()` call used by this audit's own browser script resolved without a `NoReverseMatch`; `core/tests/test_route_matrix.py` in the full suite | All pass |
| Foundations truth semantics / UNKNOWN != NO / PARTIAL != YES | `security_baseline/tests/*`, `organisations/tests/test_guided_journey.py`, `test_stage{1,2,3}_*_view.py` — none of which this PR's diff touches any underlying logic for (templates only) | All pass |
| M007 posture/completion methodology | No `views.py`/service-layer diff anywhere; `organisations/tests/test_wi6_metrics_home_foundations_reproof.py` | Pass, zero diff to the logic it proves |
| Risk/remediation/evidence/policy logic | `risk_register`, `remediation`, `evidence`, `policy` test suites (views/services/models all zero-diff; only templates changed) | All pass |
| Policy generation/approval, normative/implementation-status separation | `policy/tests/test_approval.py`, `test_views_generate_deterministic.py`, `test_h3_review_warnings.py` | All pass; `policy/views.py` zero diff |
| Approved-policy immutability | `policy/tests/test_approval.py` (part of full suite) | Pass |
| Customer Assurance AI/request contracts | `questionnaire/templates/questionnaire/list.html`'s `<form method="post" action="{% url 'questionnaire:analyse' ... %}">` and both field names (`question_text`, `source_label`) are byte-unchanged in the diff — only CSS classes/wrapper `<div>`s were added; confirmed by direct diff inspection | Unchanged |
| Reset security | `organisations/tests/test_reset_views.py`, `test_home_reset_panel.py` (5/5 pass, also re-run in isolation, §9) + runtime gating re-proof (§5) | Pass |
| Persistent data models / migrations | Zero diff on all `models.py` and `migrations/*.py` | Confirmed unchanged |
| AI invocation boundaries | No code path in this PR's diff calls `ai_platform`/the AI gateway; this audit's own seed data was written directly via the ORM (`scripts/_m008e_wi2_incr{2,3,4}_seed.py`, read in full before running) and never through `questionnaire:analyse`; no AI-triggering request was made at any point during this audit | Confirmed — zero AI calls made |
| DARWIN untouched | `git diff ... | grep -i darwin` on the actual code/doc diff returns matches **only inside the four increments' own evidence-doc prose** ("DARWIN: confirmed zero references...") — zero occurrences in any template, script, or CSS file | Confirmed |

## 7. Permanent regression class 1 — 375px overflow (progress/long-label/table/button)

Investigated and confirmed absent, with direct evidence, in `docs/evidence/M008E-BROWSER-RESPONSIVE.md` §2–3. The WI1 fix (`flex-wrap: wrap` on `.progress`) is untouched by this PR's `app.css` diff and was re-verified live on the three newly-converted Stage 1–3 pages, not just assumed carried-over. The one genuinely new narrow-viewport risk this PR introduces — the previously fully-unstyled "Implementation status" `<table>` — was given its own `.table-wrap` overflow-safety-net component and measured clean at 375px on both Policy pages that use it.

## 8. Permanent regression class 2 — focus suppression

Investigated and confirmed absent, with direct before/after computed-`box-shadow` comparisons (not mere rule presence), in `docs/evidence/M008E-BROWSER-RESPONSIVE.md` §4, covering: the current-page sidebar nav link (the exact PR #97 regression site — still fixed, rule untouched by this diff), a control non-current nav link, and the one new state-styled interactive element this PR adds (the destructive reset button). All three show a genuinely different computed value after `.focus()`.

## 9. Permanent regression class 3 — browser-test contention / flakiness investigation

This is the class the governing instructions specifically warn against taking on faith. Investigation performed, not just a conclusion asserted:

1. **Chromium launch genuinely confirmed first** (§4 / `M008E-BROWSER-RESPONSIVE.md` §1) — the single most common root cause of mass false failures in this repository's history, per the runbook's own warning, was eliminated before any test was trusted.
2. **Full combined suite run once, cleanly, with zero failures**: `2234 passed, 7 skipped, 1 xfailed, 770 warnings in 1563.47s (0:26:03)`, `DJANGO_ENV=test`, single process, no reruns, no retries. Because this run itself produced zero failures, there was nothing requiring isolation-based disambiguation this time — unlike the WI1/WI2-increment evidence docs' own documented history (§8.1 of `M008E-DESIGN-DIRECTION.md`, and several increments' own `docs/evidence/M008E-WI2-INCREMENT-*.md` "cascading Postgres deadlock" notes), this audit's full run did not reproduce any contention failure to begin with.
3. **The 7 skips and 1 xfail were not accepted as "probably fine" without checking**: statically traced to source. All 7 skips are `@_production_only` (`pytest.mark.skipif(settings.DJANGO_ENV != "production", ...)`) markers in `core/tests/test_production_config.py` and `core/tests/test_static_files.py` — neither file is in this PR's diff, both are pre-existing, both are documented in-repo as requiring `DJANGO_ENV=production` set before the process starts (cannot be faked with `override_settings()`), consistent with running under `DJANGO_ENV=test`. The 1 xfail is `core/tests/test_wi6_sidebar_drawer_acceptance.py`'s pre-existing, explicitly-documented, PL-confirmed WI6 low-severity keyboard-focus convenience gap (overlay-click close doesn't return focus to the hamburger the way Escape does) — that file is also not in this PR's diff.
4. **Targeted isolation rerun performed anyway**, as defence in depth, of every file most directly tied to the two permanent regression classes plus the reset-panel gating tests, fresh test database, immediately after the full run: `organisations/tests/test_home_reset_panel.py`, `core/tests/test_badge_narrow_viewport_regression.py`, `core/tests/test_wi6_area_smoke_browser_acceptance.py`, `evidence/tests/test_narrow_viewport_regression.py`, `key_assets/tests/test_narrow_viewport_regression.py`, `organisations/tests/test_narrow_viewport_regression.py`, `remediation/tests/test_narrow_viewport_regression.py`, `risk_register/tests/test_narrow_viewport_regression.py`, `core/tests/test_wi6_keyboard_accessibility_browser_acceptance.py` — **27 passed, 0 failed, 0 skipped**, `155.22s`.
5. **Conclusion**: no flakiness/contention was observed in this audit's own execution at all, in either the full combined run or the isolated rerun. This audit has nothing to explain away as "known flake" — the clean result stands on its own, cross-checked by the isolation rerun rather than asserted from the single pass alone.

## 10. Final test / security gate

| Gate | Result |
|---|---|
| Full test suite (whole repo, `DJANGO_ENV=test`, real Chromium installed) | **2234 passed, 7 skipped (accounted for, §9), 1 xfailed (accounted for, §9), 0 failed**, 1563.47s |
| Targeted isolation rerun (permanent-regression-class + reset-panel files) | **27 passed, 0 failed**, 155.22s |
| `makemigrations --check --dry-run` | **"No changes detected"** — clean. No WI2 migration exists. |
| `gitleaks detect` (git-history scoped, `--log-opts` limited to the PR's own 7 commits — **not** `--no-git`) | **7 commits scanned, no leaks found** |
| Dependency manifests (`requirements*.txt/.in`; no `package.json` in this repo) | **Unchanged** (zero diff, §2) |
| `gh pr checks 99` | **All seven required checks GREEN**: CodeQL (pass, 4s), ci/integration (pass, 7m49s), ci/unit (pass, 1m45s), security/container (pass, 1m12s), security/dependencies (pass, 33s), security/sast (pass, 54s), security/secrets (pass, 14s) — polled directly against the live PR, no pending checks encountered |
| Tenant-isolation / reset-isolation checks | Pass, via existing suite (§6) + this audit's own direct runtime gating re-proof (§5) |
| No unexpected AI calls | Confirmed (§6) |
| DARWIN untouched | Confirmed (§6) |

## 11. Spot-checks of each increment's own evidence-doc claims against the real artifact

- **Increment 1** (`M008E-WI2-INCREMENT-1-FOUNDATIONS-JOURNEY.md`): claimed "852 passed, 7 skipped, 1 xfailed" on its own scoped (`organisations`+`risk_register`+`security_baseline`+`core`) run, and a Stage-1 focus-ring box-shadow change from `none` to `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px`. This audit's own full-repo run reproduces the same 7-skip/1-xfail pattern (§9) on the complete superset, and independently measured the same literal box-shadow value on a different element (the sidebar current-page link, after-focus value), confirming the token value claim is real, not invented.
- **Increment 2** (`...-2-RISK-POLICY-SURFACES.md`): claimed the Policy approve page's table re-check at 375px showed `scrollWidth=375`. This audit independently re-measured the same page at 375px post-merge and got the identical `scrollWidth == clientWidth == 375` result (`M008E-BROWSER-RESPONSIVE.md` §2).
- **Increment 3** (`...-3-COMPANY-GOVERNANCE-SURFACES.md`): claimed Governance roles' focus-ring box-shadow before/after values of `rgb(15, 106, 92) 3px 0px 0px 0px inset` → a changed value with the ring layered on. This audit independently reproduced the exact same **before** value on the sidebar's current-page link in a completely different browser session (`M008E-BROWSER-RESPONSIVE.md` §4) — the literal colour/inset values match byte-for-byte, which they could only do if both measurements are against the same real, unmodified `--color-primary`/`--focus-ring` tokens, not a fabricated narrative.
- **Increment 4** (`...-4-ASSURANCE-RESET-PREORG-SURFACES.md`): claimed the reset-confirm destructive button's focus box-shadow changes from `none` to the shared focus-ring value, and that `ai_platform`/AI call paths are untouched with zero AI calls made. This audit independently re-measured the identical button on a fresh stack and got the same `none` → ring-present transition (`M008E-BROWSER-RESPONSIVE.md` §4), and independently confirmed zero `ai_platform` diff and made zero AI calls of its own (§6).

All four spot-checks corroborate the increments' own narratives against live, independently-reproduced measurements rather than merely re-reading their prose.

## 12. Disposable stack / worktree state at close

The disposable stack (`docker compose -p m008eauditpr99`) was fully torn down: `docker compose -p m008eauditpr99 down -v` removed both containers, both named volumes, and the project network — nothing was left running. The one disposable file this audit added to the worktree (`audit_browser.py`, a verification script, never part of the application) was deleted after use; `git status --short` in `/srv/openclaw/worktrees/audit/pr-99` shows no tracked-file changes and no stray untracked files beyond the three evidence documents this audit was asked to add. `/srv/infosecurs` and `/srv/openclaw/worktrees/wo/M008E-WI2-order` were never touched.

## Verdict

**GREEN.** PR #99 at `b9e7b70337c17a6fbaa414d8a5924efe3727c7d9` is a styling/presentation-only rollout that applies the Product-Authority-approved WI1 visual system consistently across the remaining authorised surfaces, preserves every security/product invariant byte-for-byte (zero diff on all `views.py`, all `migrations/*.py`, all dependency manifests), introduces no new design language or dependency, actively finds and fixes real pre-existing defects (unstyled tables, inconsistent card radii, an invented fifth status colour, a reset-confirmation page under-signalling its own severity) rather than merely restating a clean narrative, and passes every required gate: 0 unexplained test failures across 2234 tests plus a clean 27-test isolation rerun, clean migrations check, clean gitleaks, unchanged dependencies, all seven required GitHub checks green, and both permanent regression classes explicitly re-tested and confirmed absent with real measurements rather than assumed fixed.
