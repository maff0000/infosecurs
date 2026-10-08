# M008E-WI2-INCREMENT-2 — Risk & Policy Surfaces

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Governing Work Order:** `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md` (this is ONE
bounded increment under that Work Order, not a separate Work Order — the second, following
`docs/evidence/M008E-WI2-INCREMENT-1-FOUNDATIONS-JOURNEY.md`).
**Base SHA:** `06eda4373b73ecbdc7c3a7e4501b927fc3fc1c7e` (Increment 1's own evidence commit,
confirmed via `git rev-parse HEAD` before any change — already independently verified
clean by the Delivery Controller).
**Design authority:** `.claude/skills/infosecurs-ui-design/SKILL.md` (durable doctrine) and
`docs/evidence/M008E-DESIGN-DIRECTION.md` (WI1's already-approved visual system) — this
increment introduces no new visual language, only applies/extends the existing one.

## Scope executed

Apply the already-approved M008E visual system consistently across the Risk & Policy
surfaces named in this increment's dispatch:

- Security Policy (`policy/templates/policy/{detail,version_detail,approve}.html`)
- Security State (`security_state/templates/security_state/{list,detail}.html`)
- Baseline (`security_baseline/templates/security_baseline/foundations_question.html`) —
  reviewed, **no uncovered template found**. `security_baseline/urls.py`'s own
  `security_baseline:baseline` route (the "Baseline" entry point named in this dispatch)
  is a legacy redirect-only view (`views.baseline_view`, see its own docstring) into the
  Stage 4 guided journey, already fully restyled under WI1
  (`security_baseline/templates/security_baseline/foundations_question.html`). There is no
  second "Baseline" page/template anywhere in the app — confirmed by listing every
  template under `security_baseline/templates/`. Left unchanged, same judgement Increment 1
  recorded for Stage 4 itself.
- Assets (`key_assets/templates/key_assets/{list,detail,form}.html`) — `detail.html`/
  `form.html` already matched the established vocabulary; only `list.html` needed a change
  (radius harmonisation below).
- Risks (`risk_register/templates/risk_register/{list,detail,form}.html`) — `detail.html`/
  `form.html` already matched the established vocabulary; `list.html` needed two changes
  (radius harmonisation + the inline-style migration Increment 1 explicitly deferred here).
- Evidence (`evidence/templates/evidence/{list,detail,upload,add_reference,link_control}.html`)
  — `link_control.html` already matched the established vocabulary unchanged.
- Remediation (`remediation/templates/remediation/{list,detail,form,_action_card}.html`) —
  `detail.html`/`form.html`/`_action_card.html` already matched the established vocabulary;
  only `list.html` needed a change (radius harmonisation).

`policy/templates/policy/edit.html` exists on disk but is **dead code** — confirmed via
grep that `policy/urls.py` deliberately removed the `policy:version_edit` route and
`policy.views.policy_edit` (M008-WI6 Finding A; `policy/tests/test_edit.py` asserts both no
longer exist). No URL anywhere reaches this template. Left untouched: styling an
unreachable template would be wasted effort and outside this increment's own "apply to
surfaces customers actually reach" purpose; deleting the stray file is a housekeeping
matter outside a visual-rollout mandate, not raised here as a blocker.

## Method — browser-led, not blind-from-source

A disposable Docker Compose stack (`docker compose -p m008ewi2incr2`, `WEB_HOST_PORT=8997`,
`POSTGRES_HOST_PORT=15534`, both loopback-only) was brought up from this worktree —
`docker ps` was checked first and confirmed no related stack running (the live
`infosecurs-relocation` dev stack on port 8884, and the now-torn-down Increment 1 stack,
were both absent/untouched). Chromium was installed at runtime into the running `web`
container (`playwright install --with-deps chromium`), per
`docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`.

Representative data was seeded into the real Customer Zero organisation via the ORM
(`scripts/_m008e_wi2_incr2_seed.py`, evidence-generation tooling, not product code — governance
roles/profile/workplace for policy readiness, all structured baseline answers, one draft
policy version, evidence items (active/superseded/withdrawn), key assets
(suggested/confirmed/dismissed, one long name), risks (draft/confirmed/dismissed), and
remediation actions (open/in_progress/done/accepted)) — the same technique Increment 1
used, extended to cover every surface in this increment's own scope, including a real
policy draft that satisfies `policy.readiness.policy_readiness`'s full gate (confirmed
legal name/sector, an active workplace, all three governance roles, all structured
controls reviewed) so the **Approve policy directly** page (`policy/approve.html`) — the
one page in this whole increment carrying a `<table>` — was itself reachable and captured,
not just version_detail's own copy of the same table.

Before touching any file, real-Chromium screenshots of every in-scope, reachable surface
were captured at 1280/768/375px (`scripts/_m008e_wi2_incr2_capture.py`, modelled directly
on Increment 1's own `scripts/_m008e_wi2_incr1_capture.py`) via `git stash`/`git stash pop`
around the capture pass (so the exact same seeded data and running stack served both the
pre-change and post-change DOM — no rebuild/restart needed, since `DJANGO_ENV=development`
serves templates/static files live from disk with no `collectstatic` step). This "before"
pass is what actually confirmed the real page-header structural defect fixed below — not a
source-code read alone (see finding 1).

17 pages were captured both before and after (51 screenshots per pass): policy detail/
version-detail/approve-direct; security-state list/detail; key-assets list/detail/
form(new); risk-register list/detail; evidence list/detail/upload/add-reference/
link-control; remediation list/detail.

## What the before-pass found, and what was fixed

### 1. Evidence upload/add-reference: broken page-header structure (page hierarchy defect)

`evidence/templates/evidence/add_reference.html` and `evidence/templates/evidence/
upload.html` rendered their `<h1>` and `.page-header__subtitle` as **direct children** of
`.page-header` (`display: flex; justify-content: space-between; align-items: center`) with
no wrapping `<div>` around them — every other page-header in the entire product (including
these same two apps' own sibling templates, e.g. `evidence/templates/evidence/
link_control.html`) wraps the title+subtitle pair in one child `<div>` so the flex row has
at most two items: the title block, and (optionally) an actions block. Without that
wrapper, `<h1>` and `<p class="page-header__subtitle">` became two SEPARATE flex items,
which `justify-content: space-between` pushed to opposite ends of the row — the real
rendered result (confirmed in the "before" 1280px screenshot) is the organisation name
floating to the top-right of the page, vertically centred beside the title, instead of
appearing as a muted subtitle line directly beneath it. This is exactly the "page
hierarchy" defect class this increment's own objective names, on two of the seven
surfaces in scope.

**Fix:** wrapped `<h1>` + `<p class="page-header__subtitle">` in a single child `<div>` in
both templates, matching every other page-header in the product. No wording, no new
markup beyond the one wrapping element, no behaviour change.

### 2. `.table`/`.table-wrap` — a genuinely missing shared component

`policy/templates/policy/approve.html` and `policy/templates/policy/version_detail.html`
both already used `class="table"` on their "Implementation status" tables — with **no
corresponding CSS rule anywhere in the stylesheet** (confirmed by a repo-wide grep before
touching anything). An unstyled browser-default table reads nothing like the rest of this
design system and is exactly the "tables/lists" gap this increment's own objective names.

**Fix:** added `.table`/`.table-wrap` to `static/organisations/css/app.css` — header-row
shading (`--color-surface-sunken`), consistent cell padding on the `--space-*` scale, a
bottom border between rows (no border under the last row), left-aligned text, and a
`.table-wrap { overflow-x: auto; }` wrapper as a narrow-viewport safety net (belt-and-
suspenders on top of `body`'s own inherited `overflow-wrap: anywhere`, which already
protects table-cell text from forcing the table wider than its container — confirmed: the
"before" page at 375px did **not** overflow either, for that reason; the change here is
visual consistency, not an overflow fix). Applied by wrapping the existing `<table
class="table">` markup in `<div class="table-wrap">` in both templates — no column, no
row, no data-cell markup changed.

### 3. Card-radius inconsistency across five list-style card grids

Five page-local "card" components — `.risk-card` (risk_register/list.html), `.asset-card`
(key_assets/list.html), `.evidence-card` (evidence/list.html), `.action-card`
(remediation/list.html), `.state-card` (security_state/list.html) — were all still on the
small `border-radius: var(--radius)` step (6px, meant for controls/chips/inputs per
`.claude/skills/infosecurs-ui-design/SKILL.md` §8's own documented two-step scale), while
every other full-width list-style card already established across the product
(`.card-list__link`, `.foundations-row`, `.stage-tile`, `.summary-card` — all in
`static/organisations/css/app.css`) uses the larger `--radius-lg` (12px) panel/card step.
This is a real, direct "page hierarchy"/visual-consistency gap this increment's own
objective explicitly names ("These surfaces should feel like part of the same product as
Home / Foundations / Company").

**Fix:** changed all five to `border-radius: var(--radius-lg)`, each with a short comment
cross-referencing the others and the skill doctrine. CSS-value-only change (no layout
dimension, no markup change) — confirmed not to affect any overflow/structural real-browser
assertion (see Verification below).

### 4. Inline `style="text-align: left;"` → the existing `.empty-state--left` modifier

Increment 1 added `.empty-state--left` (static/organisations/css/app.css) and explicitly
left three occurrences of the identical `style="text-align: left;"` idiom for a future
increment covering their own apps: `risk_register/templates/risk_register/list.html`
("Find candidate risks" explainer). This increment also found the same idiom, not
previously flagged, on `evidence/templates/evidence/detail.html` (×2: the
"superseded by"/"replaces" notices) and on `evidence/templates/evidence/
{add_reference,upload}.html` (×1 each, with an additional one-off `margin-bottom:
var(--space-4);` alongside it).

**Fix:** all six replaced with the existing `.empty-state--left` modifier class, no new
CSS. The `add_reference.html`/`upload.html` occurrences also had the inline
`margin-bottom` fully removed (not partially retained) — the same "no inline style left
behind" outcome Increment 1's own risks_actions fix achieved, and visually inconsequential
(confirmed in the after-screenshots: the notice box sits directly above the form with the
same spacing Increment 1's own precedent already established as acceptable).

### 5. Missing `.empty-state` treatment for genuine empty sub-sections

Three bare `<p>No … yet.</p>` messages inside already-existing `.summary-card` panels on
`security_state/templates/security_state/detail.html` ("No evidence linked to this control
yet.", "No remediation actions reference this control yet.", "No recorded activity for
this control yet."), one on `evidence/templates/evidence/detail.html` ("Not yet linked to
any control."), and the page-level "No policy draft has been generated yet." on
`policy/templates/policy/detail.html` were real empty-collection states with no visual
treatment at all — every comparable case elsewhere in the product (e.g.
`key_assets/templates/key_assets/detail.html`'s own "Risks for this asset" section, already
established under WI1) nests a real `.empty-state` box inside the surrounding
`.summary-card`/page for exactly this situation.

**Fix:** wrapped each bare message in `<div class="empty-state">…</div>`, matching the
`key_assets/detail.html` precedent exactly. No wording changed anywhere (`policy/tests/
test_http_ui.py::test_no_draft_yet_shows_empty_state` asserts the literal text
`"No policy draft has been generated yet."` is present — confirmed still passing, since
only the wrapper changed, not the text).

## What was deliberately left unchanged (considered, not a defect)

- **`policy/templates/policy/edit.html`** — dead code, unreachable (see Scope above).
- **Field-level "no value" text** (e.g. remediation/detail.html's "Not linked to a risk.",
  "Not linked to a specific control/asset."; risk_register/detail.html's "No grounding
  references recorded…", "None recorded."). These describe the absence of a single field's
  value, not an empty collection/list — stacking several heavyweight dashed `.empty-state`
  boxes for individual field values (as opposed to "this whole list is empty") would read
  as visual noise, not a real empty-state. `.empty-state` is reserved for genuine
  empty-collection messaging, matching how the product already uses it everywhere else.
- **`.evidence-link-list li`/`.action-list li`/`.control-link-list li`/`.risk-detail__rating`/
  `.action-detail__field`/`.asset-protection-options label`/`.provenance-note`/
  `.accepted-note`** — these are compact inline sub-rows nested inside an existing
  `.summary-card`, not independent full-width list cards; the small `--radius` step remains
  correct for them under the SKILL.md §8 two-step scale (controls/chips/inner rows vs.
  panels/cards) — only the five outer "list-style card" components named in finding 3 were
  harmonised.
- **`risk_register/detail.html`'s remaining one-off inline `style="margin-top: …"` /
  `style="margin: 0;"` attributes** across evidence/security_state/key_assets/remediation
  detail pages — single-purpose, harmless spacing resets, not the same recurring,
  previously-named regression class `.empty-state--left` addresses. Left alone, consistent
  with Increment 1's own judgement on comparably minor, non-recurring inline styles (e.g.
  its own "`.risk-action-card`'s radius left alone" decision).
- **Badge colour/status semantics** across all seven surfaces — reviewed, found already
  fully compliant (every status badge already carries a real text label alongside its
  colour; green/amber/red/neutral meanings unchanged; `.badge`'s shared geometry already
  centralised under M006-AUDIT-0004 J1). No change needed or made.

## Component vocabulary used — one genuinely new component, one new modifier reused

Every change reuses WI1/Increment-1's existing vocabulary (`.page-header`/
`.page-header__subtitle`, `.summary-card`, `.empty-state`/`.empty-state--left`, `.badge`,
`.button--primary`/`--secondary`). One genuinely new shared component was added —
`.table`/`.table-wrap` (finding 2 above) — because the existing vocabulary had no table
component at all, not because an existing one needed a variant. No new design language,
no new colour, no new radius/spacing token.

## Verification

### Real-browser overflow check (Playwright `scrollWidth`/`clientWidth`), all 17 surfaces, 375px

Every one of the 17 captured surfaces (policy detail/version-detail/approve-direct;
security-state list/detail; key-assets list/detail/form-new; risk-register list/detail;
evidence list/detail/upload/add-reference/link-control; remediation list/detail) measured
`scrollWidth == clientWidth == 375` at 375px after this increment's changes — no horizontal
overflow anywhere, including the new `.table`/`.table-wrap` component on the policy approve
page (12 implementation-status rows, re-checked explicitly: `scrollWidth=375
clientWidth=375`, `.table-wrap > .table` count = 1).

### Keyboard/focus-visible spot check (the second permanent regression class)

No new active/current-state styling was introduced by this increment (the radius change is
a value-only edit to an existing rule; the new `.table`/`.empty-state` usage is plain
content styling, not a state/active indicator). As a regression check, computed
`box-shadow` was measured before/after `.focus()` on a representative changed-adjacent
element (`security_state/templates/security_state/list.html`'s `.state-card__title a`,
whose containing card's radius this increment changed):

- Before focus: `box-shadow: none`
- After `.focus()`: `box-shadow: rgba(15, 106, 92, 0.35) 0px 0px 0px 3px`

The shared `:focus-visible` rule is confirmed still fully in effect, unaffected by this
increment's changes. The sidebar's `[aria-current="page"]` accent-bar/focus-ring
combination (the original WI1 regression) was not re-triggered — this increment adds no new
`aria-current`/active-state CSS anywhere.

### Test suite

Run inside the disposable `m008ewi2incr2` stack, `DJANGO_ENV=test` (not the stack's own
development-mode `.env`), full `policy`, `security_state`, `key_assets`, `evidence`,
`remediation`, `risk_register`, and `core` suites (every app whose templates this increment
touched, plus `core` for its shared cross-app browser-acceptance/regression coverage,
including `core/tests/test_badge_narrow_viewport_regression.py`'s own real-browser
Evidence/Key-Assets/Risk/Remediation/Security-State/Policy coverage and
`core/tests/test_wi6_area_smoke_browser_acceptance.py`'s Baseline-reachability smoke):

```
916 passed, 7 skipped, 1 xfailed, 365 warnings in 942.59s (0:15:42)
```

(Increment 1's own equivalent full run was `852 passed, 7 skipped, 1 xfailed` — the same 7
skips/1 xfail recur unchanged here, confirming they are pre-existing and unrelated to this
increment's own files; the extra passes are this increment's own apps' tests now included
in the combined run.)

A targeted, verbose re-run (`-v -rs`) of exactly the files this increment's own changes
touch or could affect — `policy/tests/{test_http_ui,test_approval,
test_implementation_status}.py`, `security_state/tests/test_views.py`,
`key_assets/tests/{test_http_ui,test_narrow_viewport_regression,test_detail_view}.py`,
`evidence/tests/{test_views,test_narrow_viewport_regression}.py`,
`remediation/tests/{test_http_ui,test_narrow_viewport_regression}.py`,
`risk_register/tests/{test_http_ui,test_narrow_viewport_regression,
test_foundations_risks_actions}.py`, `core/tests/{test_badge_narrow_viewport_regression,
test_wi6_area_smoke_browser_acceptance}.py` — passed with zero failures and zero skips
among the targeted files.

**Bulk-run contention note (same class Increment 1's own evidence doc documented, carried
forward transparently per this dispatch's instruction):** while preparing this evidence,
three `pytest` invocations against the same disposable stack were briefly launched
concurrently by operator error (a background-shell detachment mistake, not a test-suite
defect) and were killed before completing; the shared `test_infosecurs` database was
dropped and a single clean full run was then executed (the `916 passed` run quoted above).
This was caught and corrected before relying on any of its output — nothing from the
contended runs is used as evidence anywhere in this document. Unlike Increment 1's own
narrow-viewport-overflow flakiness finding, this was not a product/test defect at all, so
no isolation-rerun-and-compare was needed beyond discarding the contended output and
re-running cleanly once.

- `python manage.py check`: no issues (implied by every view above returning 200/expected
  status through the full test run).
- `python manage.py makemigrations --check --dry-run`: "No changes detected" — this
  increment needed no migration.
- `gitleaks detect` (git-history-scoped, not `--no-git`): "no leaks found" (140 commits
  scanned) — run against the pre-existing history before this increment's own commit; this
  increment adds no secrets.
- Dependency manifests confirmed byte-identical: `git diff --stat -- requirements.txt
  requirements.in requirements-dev.txt requirements-dev.in package.json` — empty.
- `ai_platform` / AI call paths: confirmed untouched — `git diff | grep -i ai_platform`
  returns no match.
- DARWIN: confirmed zero references anywhere in this increment's diff (`git diff | grep -i
  darwin` — no match).

## Complete changed-paths list

New:
- `docs/evidence/M008E-WI2-INCREMENT-2-RISK-POLICY-SURFACES.md` (this file)
- `docs/evidence/m008e-wi2-screenshots/increment-2/before/*.png` (17 pages × 3 widths = 51
  files)
- `docs/evidence/m008e-wi2-screenshots/increment-2/after/*.png` (17 pages × 3 widths = 51
  files)
- `scripts/_m008e_wi2_incr2_seed.py` (evidence-generation tooling, not product code)
- `scripts/_m008e_wi2_incr2_capture.py` (evidence-generation tooling, not product code)

Changed:
- `static/organisations/css/app.css` — new `.table`/`.table-wrap` component.
- `policy/templates/policy/approve.html` — implementation-status table wrapped in
  `.table-wrap`.
- `policy/templates/policy/version_detail.html` — same table wrap.
- `policy/templates/policy/detail.html` — "no draft yet" now a real `.empty-state`.
- `security_state/templates/security_state/detail.html` — three bare "nothing yet"
  messages now real `.empty-state`s.
- `security_state/templates/security_state/list.html` — `.state-card` radius
  harmonised to `--radius-lg`.
- `key_assets/templates/key_assets/list.html` — `.asset-card` radius harmonised.
- `evidence/templates/evidence/list.html` — `.evidence-card` radius harmonised.
- `evidence/templates/evidence/detail.html` — two `text-align: left` inline styles
  migrated to `.empty-state--left`; "not yet linked to any control" now a real
  `.empty-state`.
- `evidence/templates/evidence/add_reference.html` — page-header structural fix (title +
  subtitle now correctly wrapped); inline style migrated to `.empty-state--left`.
- `evidence/templates/evidence/upload.html` — same two fixes.
- `remediation/templates/remediation/list.html` — `.action-card` radius harmonised.
- `risk_register/templates/risk_register/list.html` — `.risk-card` radius harmonised;
  inline style migrated to `.empty-state--left` (the occurrence Increment 1 explicitly
  deferred to this increment).

Unchanged (confirmed): every dependency manifest in the repository;
`security_baseline/templates/security_baseline/foundations_question.html` (Stage 4, already
WI1 work); `policy/templates/policy/edit.html` (dead code, unreachable — see Scope);
`key_assets/templates/key_assets/{detail,form}.html`; `risk_register/templates/
risk_register/{detail,form}.html`; `evidence/templates/evidence/link_control.html`;
`remediation/templates/remediation/{detail,form,_action_card}.html`; every migration; every
route; every answer-semantics/posture/risk-generation/policy-generation/policy-approval
code path; policy immutability; the normative-policy/implementation-status separation;
baseline methodology; asset semantics; evidence semantics; tenant isolation; entitlements;
AI behaviour.

## Hard-boundary STOP conditions encountered

None. Every change in this increment is presentation-only: a page-header structural fix
restoring the product's own already-established layout pattern, one new shared CSS
component for an already-used-but-unstyled class name, five CSS radius-value changes, and
inline-style-to-existing-class migrations plus empty-state wrapper markup. No question
catalogue, answer value, mapping, UNKNOWN/PARTIAL semantics, save behaviour, route, policy
generation/approval/immutability logic, baseline methodology, asset/evidence semantics,
tenant isolation, entitlement logic, AI behaviour, or data model/migration was touched.
