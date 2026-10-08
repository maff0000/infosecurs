# M008E-WI1 — Independent Audit Record

**PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Work Order:** `docs/work-orders/WO-M008E-WI1.md`
**Audited PR:** #97 (`wo/M008E-WI1-design-checkpoint` → `main`)
**Canonical base:** `186a3e6de7d5aee16840de9e3ddb10b81b002487`
**Final audited head:** `381fbac00c1336e135795968404181c4a1480493`
**Final verdict:** **GREEN**

## Independence statement

Two Independent Auditors reviewed this PR, each a genuinely fresh dispatch with no memory of the Implementer's own reasoning and no inherited conclusion from any prior round — neither was a fork of the Delivery Controller's own session or of each other. Each built its own isolated git worktree from the canonical repository at the exact commit under review, confirmed that worktree's history genuinely descended from canonical `main` before trusting anything in it, and ran its own disposable Docker Compose stack (distinct project name/ports from every other stack on the host) for all live verification. The Delivery Controller independently spot-checked at least one consequential claim from each audit round directly against the real artifact (source, running container, or GitHub API) before accepting it, rather than forwarding either report on trust alone.

## Round 1 — first fresh Independent Audit (head `43f37851699db0e1ff44b7cda5c4c7e85efb5bbe`)

**Verdict: RED.**

One verified, reproducible finding: in `static/organisations/css/app.css`, the new `.shell-nav__link[aria-current="page"]` rule (added by this Work Order, specificity (0,2,0)) sets `box-shadow` for the sidebar "accent bar" treatment of the current page, and this unconditionally overrode the sitewide `:focus-visible` rule (specificity (0,1,0)), which also sets `box-shadow` for the visible keyboard-focus ring. No `!important` was present on either rule, so the higher-specificity accent-bar declaration always won. Effect: the current-page sidebar nav link never showed a visible focus indicator when it received keyboard focus — indistinguishable focused vs. unfocused. Because `.shell-nav`/`.shell-nav__link` is the shared sidebar used on every page, this was a sitewide regression via shared CSS, not limited to the three surfaces this Work Order redesigned.

The Auditor reproduced this live via Playwright against its own disposable stack (logged in as the real Customer Zero fixture user): computed `box-shadow` on the Home nav link (current page there) was identical before and after calling `.focus()`; a control non-current nav link showed the ordinary focus ring appearing correctly, confirming the general focus mechanism was intact everywhere except this one collision.

This contradicted `.claude/skills/infosecurs-ui-design/SKILL.md` §6 ("Visible focus on every interactive element... never `outline: none` without a real replacement indicator") and an inaccurate claim then present in `docs/evidence/M008E-DESIGN-DIRECTION.md` §7 ("focus order unchanged... visible focus ring present throughout, no keyboard traps").

Everything else this round audited was GREEN: Customer Zero reset security (the `_customer_zero_reset_enabled_for()` helper confirmed a byte-for-byte pure extraction of the pre-existing gate expression, zero changes to the real `customer_zero_reset` view), scope/changed-path review, dependency/migration check, `gitleaks`, full `organisations`+`security_baseline`+`core` suite (610 passed / 0 failed / 7 skipped / 1 xfailed), all seven required CI checks, the 375px overflow fix from an earlier commit in this same Work Order, and badge status-label semantics.

The Delivery Controller independently re-verified the round 1 finding before accepting it: read both CSS rules directly at their source line numbers, confirmed the specificity count by hand, and confirmed no combining/overriding rule existed elsewhere in the file.

## Bounded repair (commit `381fbac00c1336e135795968404181c4a1480493`)

A narrowly-scoped repair Implementer, dispatched only against this one finding, added:

```css
.shell-nav__link[aria-current="page"]:focus-visible {
  box-shadow: var(--focus-ring), inset 3px 0 0 var(--color-primary);
}
```

Specificity (0,3,0) — genuinely higher than both the sitewide `:focus-visible` rule (0,1,0) and the plain accent-bar rule (0,2,0), with no `!important` required. The declaration is a comma-separated layering of both shadow values (the standard focus ring plus the existing inset accent bar), not a replacement of either. The repair also corrected the false claim in `docs/evidence/M008E-DESIGN-DIRECTION.md` §7 and added an honest §8.2 account of the finding, root cause, and fix.

Only two files changed in this commit: `static/organisations/css/app.css` (10 insertions) and `docs/evidence/M008E-DESIGN-DIRECTION.md` (77 insertions, 3 deletions) — independently confirmed by the Delivery Controller via `git diff --stat`.

The repair Implementer verified the fix live, before/after `.focus()`, against its own disposable stack; the Delivery Controller independently re-verified the mechanism (specificity count, layered-declaration syntax) directly against the committed source and confirmed the running dev stack was actually serving the fixed CSS content (not a stale cached copy) before accepting the repair as resolved.

## Round 2 — second fresh Independent Audit (head `381fbac00c1336e135795968404181c4a1480493`)

**Verdict: GREEN.**

A different fresh Auditor (never the round 1 Auditor, never a fork) re-verified the entire PR from scratch at the repaired head — not only the fix. Findings:

- **Focus-ring fix, independently re-verified**: specificity counted again independently ((0,3,0) beats both (0,1,0) and (0,2,0)); the layered `box-shadow` declaration confirmed by direct source read; live Playwright verification in a fresh disposable stack showed the Home nav link's computed `box-shadow` genuinely differs before vs. after focus (`rgb(15,106,92) 3px 0px 0px 0px inset` at rest → `rgba(15,106,92,0.35) 0px 0px 0px 3px, rgb(15,106,92) 3px 0px 0px 0px inset` when focused); a control non-current link's ordinary focus ring was unaffected; a genuine keyboard `Tab` traversal (not only scripted `.focus()`) reached the current-page link and showed the same layered value on real keyboard focus.
- **Changed-path/scope review**: every non-screenshot diff read in full (`organisations/views.py`, the three touched templates, `foundations_question.html`, the full `app.css` diff, `test_home_reset_panel.py`). Nothing outside WO-M008E-WI1's authorised scope changed; no `settings.py`/`urls.py`/migration/entitlements/other-app-view change anywhere.
- **Reset-control gating, re-verified**: `_customer_zero_reset_enabled_for()` confirmed a pure, read-only extraction; the real `customer_zero_reset` view confirmed untouched; the Home panel confirmed link-only (zero `<form>` elements inside `.dev-panel` in live DOM inspection); PID §E2's exact copy confirmed via live-extracted `outerHTML`; dashed-border styling confirmed via computed style.
- **375px responsive regression history and fix**: the `.progress`/`.progress__label` overflow regression (found by an earlier full-suite run, fixed in commit `d4aa165` before round 1's audit even began) re-confirmed holding — live `scrollWidth == clientWidth == 375` on Home, Foundations, Company hub, and the Stage 4/baseline question page, no overflow.
- **Dependency/migration check**: `requirements*.txt/.in`, `package.json` diffs confirmed empty; `makemigrations --check --dry-run` clean.
- **`gitleaks detect`**: clean, both full git-history scan (135 commits) and PR-commit-scoped scan.
- **Full test suite**: `organisations` + `security_baseline` + `core`, fresh disposable stack, `DJANGO_ENV=test`: **610 passed, 0 failed, 7 skipped, 1 xfailed.**
- **Badge semantics**: live-checked, all status badges carry real text labels, none colour-only.
- **CI checks**: `gh pr checks 97` at head `381fbac0` — all seven required checks (CodeQL, ci/integration, ci/unit, security/container, security/dependencies, security/sast, security/secrets) pass.

The Delivery Controller independently spot-checked this round's two most load-bearing procedural claims directly before accepting the verdict: re-ran `gh pr view 97` / `gh pr checks 97` itself (confirmed head `381fbac0`, `MERGEABLE`, all seven green) and re-ran `git diff --name-only` against the canonical base itself (confirmed the non-screenshot changed-path list matched exactly, no scope drift).

## Final independent verdict

**GREEN.**
