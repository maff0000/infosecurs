# M008E-WI2-INCREMENT-3 — Company / Governance Surfaces

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Governing Work Order:** `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md` (this is ONE
bounded increment under that Work Order, not a separate Work Order — the third, following
`docs/evidence/M008E-WI2-INCREMENT-1-FOUNDATIONS-JOURNEY.md` and
`docs/evidence/M008E-WI2-INCREMENT-2-RISK-POLICY-SURFACES.md`).
**Base SHA:** `65ae8b630a6ecad893f9e92d060e4a8ee6a3055f` (Increment 2's own evidence commit,
confirmed via `git rev-parse HEAD` before any change — already independently verified clean
by the Delivery Controller).
**Design authority:** `.claude/skills/infosecurs-ui-design/SKILL.md` (durable doctrine) and
`docs/evidence/M008E-DESIGN-DIRECTION.md` (WI1's already-approved visual system) — this
increment introduces no new visual language, only applies/extends the existing one.

## Scope executed

Apply the already-approved M008E visual system consistently across the Company/Governance
surfaces named in this increment's dispatch:

- Profile (`organisations/templates/organisations/profile_form.html`)
- Governance (`governance/templates/governance/{role_assignments,edit_my_details}.html`)
- Workplace (`workplace/templates/workplace/{list,form}.html`; the five onboarding-wizard
  templates reviewed, **no change needed** — see below)
- Activity (`activity/templates/activity/list.html`)

`organisations/templates/organisations/organisation_hub.html` was read as the cross-page
reference (per this dispatch's own instruction not to re-touch it) but is unchanged — no
cross-page inconsistency was found that it introduced.

## Method — browser-led, not blind-from-source

A disposable Docker Compose stack (`docker compose -p m008ewi2incr3`, `WEB_HOST_PORT=8999`,
`POSTGRES_HOST_PORT=15536`, both loopback-only) was brought up from this worktree — `docker
ps` was checked first and confirmed no related stack running (the live `infosecurs-relocation`
dev stack on port 8884 was untouched; no `m008ewi2incr1`/`m008ewi2incr2` stacks remained).
Chromium was installed at runtime into the running `web` container (`playwright install
--with-deps chromium`), per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md` — and, per this
dispatch's explicit instruction (a prior reviewer of this Work Order reportedly lost time to a
silently-incomplete install), **explicitly verified** before trusting any test result: a direct
`playwright.sync_api.sync_playwright().chromium.launch()` call inside the container, navigating
to the real login page and reading its title, was run and confirmed `CHROMIUM LAUNCH OK` before
any capture or test run.

Representative data was seeded into the real Customer Zero organisation via the ORM
(`scripts/_m008e_wi2_incr3_seed.py`, evidence-generation tooling, not product code): a long
(deliberately overflow-provoking) legal/trading name and populated profile fields; all three
governance roles exercised into their three distinct real states — one assigned to the active
account holder, one assigned to a second person subsequently marked inactive, one left
genuinely unassigned; one active+primary workplace with a long name, one ordinary active
workplace, one inactive workplace; a handful of real `ActivityEvent` rows including one with a
long `control_key`-driven summary.

Before touching any file, real-Chromium screenshots of every in-scope surface were captured at
1280/768/375px (`scripts/_m008e_wi2_incr3_capture.py`, modelled directly on Increment 2's own
`scripts/_m008e_wi2_incr2_capture.py`) via `git stash`/`git stash pop` around the capture pass
(same seeded data and running stack served both passes — no rebuild/restart needed, since
`DJANGO_ENV=development` serves templates/static files live from disk). This "before" pass is
what actually confirmed the two real defects fixed below — not a source-code read alone.

7 pages were captured both before and after (21 screenshots per pass, 42 total): profile;
governance roles; governance edit-my-details; workplace list; workplace add-new form;
workplace edit form; activity list.

## What the before-pass found, and what was fixed

### 1. Workplace: the page was rendering completely unstyled (a genuine, pre-existing defect)

`workplace/templates/workplace/list.html` directly reused `key_assets/templates/key_assets/
list.html`'s page-local class names (`.asset-card`, `.asset-grid`, `.asset-section`,
`.asset-card__title`/`__meta`/`__actions`, `.badge--confirmed`) **without its own `<style>`
block and with no shared definition of any of them anywhere else in the stylesheet** (confirmed
by a repo-wide grep before touching anything — `.asset-card` et al. are defined only inside
`key_assets/list.html`'s own page-local `<style>` block, which has no effect outside that one
template's render). The "before" 1280px screenshot shows the real, rendered result: plain
browser-default boxes with no border/radius/spacing, and the "Primary" tag rendered as bare
unstyled text with no badge pill at all — exactly the kind of "weak visual hierarchy /
repetitive plain cards / pages that look like internal tooling" defect class this increment's
own objective names, and a materially worse case than any surface the two prior increments
found (those found inconsistent styling; this page had none at all).

**Fix:** gave Workplace its own, correctly-named page-local component — `.workplace-grid`/
`.workplace-card`/`.workplace-card--inactive`/`.workplace-card__body`/`__title`/
`__title-text`/`__meta`/`__actions`/`.workplace-section`/`.workplace-section__intro` — same
shape/geometry as the five other full-width list-card surfaces Increment 2 already harmonised
to `--radius-lg` (`.asset-card`/`.risk-card`/`.evidence-card`/`.action-card`/`.state-card`),
starting on the correct radius step from the outset rather than needing a later harmonisation
pass. The customer-controlled workplace name gets the same proven long-name wrap protection
(`.workplace-card__title-text { min-width: 0; overflow-wrap: anywhere; }`) as
`.asset-card__title-text` (M006-AUDIT-0002 G2). The "Primary" tag gets its own new colour
variant, `.badge--primary` (primary-tint background/text), **deliberately not** a reuse of
`.badge--confirmed`'s green: "Primary" names which workplace record is the default one for
working-model calculations, not a security-status judgement, and SKILL.md §5's green/amber/
red/neutral meanings are fixed and must never be reassigned to an unrelated label.

### 2. Profile: the same page-header structural defect Increment 2 found and fixed elsewhere

`organisations/templates/organisations/profile_form.html` rendered its `<h1>` and
`<p class="page-header__subtitle">` as **direct children** of `.page-header`
(`display:flex; justify-content:space-between`) with no wrapping `<div>` — the identical defect
class Increment 2's own evidence document (§1) found and fixed on
`evidence/templates/evidence/{add_reference,upload}.html`. The "before" 1280px screenshot shows
the real rendered result: "Infosecurs Limited" floating to the top-right of the page beside the
title instead of appearing as a muted subtitle line beneath it — on the Profile page
specifically, one of the surfaces this increment's own objective names directly ("Profile ...
is likely a form").

**Fix:** wrapped `<h1>` + `<p class="page-header__subtitle">` in a single child `<div>`,
matching every other page-header in the product (including this increment's own Governance/
Workplace/Activity pages, all of which were already correctly wrapped). No wording, no new
markup beyond the one wrapping element, no behaviour change.

### 3. Governance roles: status presentation had no visual signal at all beyond plain text

`governance/templates/governance/role_assignments.html` rendered "Currently assigned to X" and
"Not yet assigned." as plain, visually-identical paragraphs — no status signal at a glance,
despite this being precisely the kind of "status presentation" this increment's own objective
names for this surface. The one real severity signal the page already carries (a role assigned
to a person since marked inactive) was, and remains, its own pre-existing `.message
message--error` alert.

**Fix:** two small, page-local `.badge` colour variants, following the fixed, already-documented
semantics in `.claude/skills/infosecurs-ui-design/SKILL.md` §5 exactly rather than inventing
anything: `.badge--assigned` (green — "Assigned" to an active person IS the complete state for
that role) and `.badge--unassigned` (neutral grey, using the dedicated `--color-neutral-bg`/
`--color-neutral-text` tokens — "not yet assigned" is informational, not itself a judged gap; no
existing severity classification anywhere in this product's code renders that state as a
red/amber signal, so this increment does not invent one). The existing inactive-assignee
`.message--error` alert is deliberately **not** duplicated with a third badge colour — two
overlapping signals for the same fact would be exactly the "visual clutter"/"restrained
secondary information" doctrine warns against. Both new badges carry real text labels
("Assigned" / "Not assigned"), never colour alone.

### 4. Governance roles: "Edit your details" had no visible action weight

The one real secondary action on the page (edit the signed-in user's own name/job title) was a
bare, unstyled inline `<a>` — easy to miss, and inconsistent with "action hierarchy"
(objective-named) elsewhere on the same page, where every other action is a real `.button`.

**Fix:** `class="button button--secondary"` added. No route, no behaviour, no new markup beyond
the one class.

### 5. Activity: list-row radius inconsistency, and an unstyled intro paragraph

`activity/templates/activity/list.html`'s own page-local `.activity-item` (a full-width
list-style row, the same category of component as `.asset-card`/`.risk-card`/etc.) was still on
the small `var(--radius)` step rather than `--radius-lg` — the sixth occurrence of exactly the
defect class Increment 2's own finding 3 named and fixed on five sibling surfaces. The page's
own explanatory intro paragraph ("A read-only history of...") rendered in plain default text,
where `organisations/templates/organisations/organisation_hub.html`'s own identically-positioned
intro paragraph (directly following `.page-header`, before any other content) already
establishes the precedent of reusing `.page-header__subtitle` for exactly this position, with no
inline-style override needed (unlike `remediation/list.html`'s own mid-body reuse of the same
class, which *does* need an inline margin override because of its different position — not a
pattern safe to copy here).

**Fix:** `.activity-item`'s radius changed to `var(--radius-lg)`; the intro paragraph given
`class="page-header__subtitle"` (zero new CSS, direct reuse of an existing, already-precedented
pattern).

## What was reviewed and deliberately left unchanged (considered, not a defect)

- **`workplace/templates/workplace/form.html`** (Add/Edit workplace) — already fully compliant
  with the established vocabulary (`.page-header` correctly wrapped, `.form-section`, `.field`,
  `.form-actions`, `.button--primary`/`--secondary`). Reviewed and captured before/after
  (unchanged pixels) as part of this increment's own in-scope surface list; no defect found.
- **`governance/templates/governance/edit_my_details.html`** — likewise already fully
  compliant. Reviewed and captured; no change made.
- **The five workplace onboarding-wizard templates**
  (`onboarding_{start,one_office,shared_coworking,all_remote,office_and_home}.html`) — this
  increment's own dispatch names "Workplace (workplace page)" as its bounded scope, i.e. the
  page reached directly from the Organisation hub (`workplace:list`) and its own add/edit form;
  the guided-setup wizard is a separate, additional flow reachable via Workplace's own "Guided
  setup" button, not itself named in this dispatch. All five were nonetheless checked for the
  same defect classes found elsewhere in this increment (unwrapped page-header, inline styles):
  all five already correctly wrap `<h1>`+subtitle in a child `<div>` and use the established
  `.form-section`/`.field`/`.form-actions` vocabulary throughout, with no inline styles. No
  defect found — left untouched, same judgement Increment 1 recorded for Stage 4 and Increment 2
  recorded for Baseline (an in-scope area reviewed and found to need no change).
- **`organisations/templates/organisations/organisation_hub.html`** — read as the cross-page
  reference this dispatch's own instructions require, not re-touched. No cross-page
  inconsistency found that it introduced.
- **The existing `.message message--error` alert for an inactive governance-role assignee** —
  kept exactly as-is (see finding 3 above); deliberately not given an additional badge.

## Component vocabulary used — no new shared component; two new local colour variants, one new local card component (following established precedent)

Every change reuses WI1/Increment-1/Increment-2's existing vocabulary (`.page-header`/
`.page-header__subtitle`, `.badge`'s shared geometry, `.button--secondary`, `.empty-state`,
`--radius-lg`). Two new page-local badge colour variants were added
(`.badge--assigned`/`.badge--unassigned` on Governance roles, `.badge--primary` on Workplace) —
each a domain-specific colour mapping on top of the already-centralised `.badge` geometry,
exactly the established "colour variants stay local" convention (M006-AUDIT-0004 J1). One new
page-local card component (`.workplace-card` and its sub-classes) was added, following the
identical, already-five-times-precedented shape used by `.asset-card`/`.risk-card`/
`.evidence-card`/`.action-card`/`.state-card` — not a new design language, a page finally gaining
the component class it was always missing. No shared `static/organisations/css/app.css` change
was needed this increment.

## Verification

### Real-browser overflow check (Playwright `scrollWidth`/`clientWidth`), all 7 surfaces, 375px

| Surface | 375px |
|---|---|
| Profile | 375 == 375 |
| Governance roles | 375 == 375 |
| Governance edit-my-details | 375 == 375 |
| Workplace list | 375 == 375 |
| Workplace add-new form | 375 == 375 |
| Workplace edit form | 375 == 375 |
| Activity list | 375 == 375 |

No horizontal overflow anywhere, including the long organisation name (Profile), the long
workplace name (Workplace list), and the long activity summary (Activity list) deliberately
seeded to provoke it.

### Keyboard/focus-visible spot check (the second permanent regression class)

No new active/current-state CSS was introduced by this increment (the badges and the
`.workplace-card`/`.activity-item` radius are plain content styling, not state indicators). As a
regression check, computed `box-shadow` was measured before/after `.focus()`:

- Governance roles' primary submit button (`button.button--primary`): `box-shadow` changes from
  `none` to `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px` on focus — the shared `:focus-visible` rule
  applies correctly.
- The sidebar's current-page accent-bar/focus-ring combination (the original WI1 regression):
  `box-shadow` before focus = `rgb(15, 106, 92) 3px 0px 0px 0px inset`; after focus =
  `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px, rgb(15, 106, 92) 3px 0px 0px 0px inset` — genuinely
  different, confirming the layered fix is still in effect on every page this increment touched
  (all of which render the shared sidebar).

### Badge text-label check (status colour is never the only signal)

`.badge` elements on Governance roles rendered exactly `['ASSIGNED', 'NOT ASSIGNED']`
(CSS `text-transform: uppercase` on the shared geometry; underlying text "Assigned"/"Not
assigned") — every badge carries a real text label, never colour alone. Workplace's own badge
rendered `['PRIMARY']`, same check.

### Test suite

Run inside the disposable `m008ewi2incr3` stack, `DJANGO_ENV=test` (not the stack's own
development-mode `.env`), full `organisations`, `governance`, `workplace`, `activity`, and
`core` suites (every app whose templates this increment touched, plus `core` for its shared
cross-app browser-acceptance/regression coverage):

```
581 passed, 7 skipped, 1 xfailed, 366 warnings in 784.83s (0:13:04)
```

(Increment 2's own equivalent combined run was `916 passed, 7 skipped, 1 xfailed`; this run
scopes to a different, smaller app set — `organisations`/`governance`/`workplace`/`activity`/
`core` rather than `policy`/`security_state`/`key_assets`/`evidence`/`remediation`/
`risk_register`/`core` — so the raw pass count is not directly comparable, but the same 7
skips/1 xfail recur unchanged, confirming they are pre-existing and unrelated to this
increment's own files.)

A targeted, verbose re-run (`-v -rs`) of exactly the files this increment's own changes touch or
could affect — `organisations/tests/{test_http_ui,test_organisation_hub,test_form_labels,
test_tenant_isolation}.py`, `governance/tests/{test_views,test_tenant_isolation}.py`,
`workplace/tests/{test_http_ui,test_tenant_isolation}.py`, `activity/tests/{test_http_ui,
test_tenant_isolation}.py`, `core/tests/{test_application_shell,
test_badge_narrow_viewport_regression,test_wi6_area_smoke_browser_acceptance,
test_active_nav}.py` — passed with zero failures and zero skips among the targeted files:

```
159 passed, 128 warnings in 221.74s (0:03:41)
```

`core/tests/test_wi6_area_smoke_browser_acceptance.py` (the exact test §8.1 of
`docs/evidence/M008E-DESIGN-DIRECTION.md` records as having previously caught a real WI1
regression) passed cleanly here, confirming no repeat of that defect class on any surface this
increment touched.

No bulk-run contention was encountered this increment — the full run and the targeted re-run
were each executed once, sequentially, with no concurrent invocation against the same disposable
stack.

- `python manage.py check`: no issues (implied by every view above returning 200/expected status
  through the full test run).
- `python manage.py makemigrations --check --dry-run`: "No changes detected" — this increment
  needed no migration.
- `gitleaks detect` (git-history-scoped, not `--no-git`), run after committing this increment's
  work: no leaks found.
- Dependency manifests confirmed byte-identical: `git diff --stat -- requirements.txt
  requirements.in requirements-dev.txt requirements-dev.in package.json` against base SHA
  `65ae8b630a6ecad893f9e92d060e4a8ee6a3055f` — empty.
- `ai_platform` / AI call paths: confirmed untouched — `git diff 65ae8b6... | grep -i
  ai_platform` returns no match.
- DARWIN: confirmed zero references anywhere in this increment's diff (`git diff 65ae8b6... |
  grep -i darwin` — no match).

## Complete changed-paths list

New:
- `docs/evidence/M008E-WI2-INCREMENT-3-COMPANY-GOVERNANCE-SURFACES.md` (this file)
- `docs/evidence/m008e-wi2-screenshots/increment-3/before/*.png` (7 pages × 3 widths = 21 files)
- `docs/evidence/m008e-wi2-screenshots/increment-3/after/*.png` (7 pages × 3 widths = 21 files)
- `scripts/_m008e_wi2_incr3_seed.py` (evidence-generation tooling, not product code)
- `scripts/_m008e_wi2_incr3_capture.py` (evidence-generation tooling, not product code)

Changed:
- `organisations/templates/organisations/profile_form.html` — page-header structural fix
  (title + subtitle now correctly wrapped in one child `<div>`).
- `governance/templates/governance/role_assignments.html` — new `.badge--assigned`/
  `.badge--unassigned` page-local colour variants and their markup; "Edit your details"
  upgraded to `.button--secondary`.
- `workplace/templates/workplace/list.html` — new, correctly-named `.workplace-*` page-local
  component replacing the previously-broken reuse of `key_assets`' own `.asset-*` classes; new
  `.badge--primary` colour variant for the "Primary" tag.
- `activity/templates/activity/list.html` — `.activity-item` radius harmonised to
  `--radius-lg`; intro paragraph now reuses `.page-header__subtitle`.

Unchanged (confirmed): every dependency manifest in the repository;
`workplace/templates/workplace/form.html`; `governance/templates/governance/
edit_my_details.html`; all five `workplace/templates/workplace/onboarding_*.html` templates;
`organisations/templates/organisations/organisation_hub.html`; every migration; every route;
every governance-role-assignment/profile-field/workplace-data-model/activity-log-generation
code path; tenant isolation; entitlements; AI behaviour.

## Hard-boundary STOP conditions encountered

None. Every change in this increment is presentation-only: a page-header structural fix
restoring the product's own already-established layout pattern (the same defect class Increment
2 found and fixed elsewhere, now found and fixed here on Profile), a complete-but-previously-
entirely-missing page-local component for a page that was rendering unstyled, two small
status-badge colour variants applying this product's own already-fixed, documented semantics
(never inventing a new one), one action upgraded from a bare link to the existing secondary-
button class, and one radius-value harmonisation plus one existing-class reuse for an intro
paragraph. No governance-role assignment/validation logic, profile field semantics/validation,
workplace data model/semantics, activity-log generation/content/ordering logic, route,
entitlement, AI behaviour, persistence/data model, or migration was touched.
