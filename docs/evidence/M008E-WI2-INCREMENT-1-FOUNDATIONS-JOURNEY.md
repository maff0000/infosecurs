# M008E-WI2-INCREMENT-1 — Foundations Journey (Stage 1-4, Risks & Actions)

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Governing Work Order:** `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md` (this is ONE
bounded increment under that Work Order, not a separate Work Order).
**Base SHA:** `028e93d392b9f99f59500b5b22dc2a67f530ea17` (confirmed via `git rev-parse HEAD`
before any change).
**Design authority:** `.claude/skills/infosecurs-ui-design/SKILL.md` (durable doctrine) and
`docs/evidence/M008E-DESIGN-DIRECTION.md` (WI1's already-approved visual system) — this
increment introduces no new visual language, only applies/extends the existing one.

## Scope executed

Apply the already-approved M008E visual system consistently across the remaining
Foundations customer journey surfaces:

- Stage 1 — Your Business (`organisations/templates/organisations/stage1_business.html`)
- Stage 2 — Your People & Workplaces (`organisations/templates/organisations/stage2_people_workplaces.html`)
- Stage 3 — Your Technology & Data (`organisations/templates/organisations/stage3_technology_data.html`)
- Stage 4 — Your Security: reviewed against WI1's already-approved reference implementation
  (`security_baseline/templates/security_baseline/foundations_question.html`). **No sub-views
  were found uncovered** — Stage 4 has exactly one real template
  (`foundations_question.html`), already restyled under WI1; it was left unchanged.
- Risks & Actions (`risk_register/templates/risk_register/foundations_risks_actions.html`)

`organisations/templates/organisations/foundations.html` (the workspace page) was
inspected as the cross-page reference but is unchanged (already WI1 work).

## Method — browser-led, not blind-from-source

A disposable Docker Compose stack (`docker compose -p m008ewi2incr1`, `WEB_HOST_PORT=8995`,
`POSTGRES_HOST_PORT=15532`, both loopback-only) was brought up from this worktree — `docker
ps` was checked first and confirmed no related stack running; the live `infosecurs-relocation`
dev stack (port 8884) was never touched. Chromium was installed at runtime into the running
`web` container (`playwright install --with-deps chromium`), per
`docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md` — never baked into the image.

Before touching any file, real-Chromium screenshots of every in-scope surface were captured
at 1280/768/375px (`scripts/_m008e_wi2_incr1_capture.py`, modelled directly on WI1's own
`scripts/_m008e_screenshot_capture.py`), logged in as the real Customer Zero fixture user.
This "before" pass is what actually identified the two real inconsistencies fixed below — not
a source-code read.

**Capture-method caveat (same one WI1 already documented, reproduced here because it recurs
on every page using `.form-actions--sticky` — i.e. every stage in this journey, not only
Stage 4):** the `full_page=True` screenshots show the sticky bottom action bar floating
mid-page at 375px. This is a known Playwright/Chromium full-page-screenshot artifact (the
capture resizes the viewport to the full document height before shooting, which resolves
`position: sticky` against that enlarged viewport). It is **not** a real rendering defect —
confirmed directly via Playwright `scrollWidth`/`clientWidth` measurement (see the Overflow
table below) and via ordinary (non-full-page) interaction at every width.

## What the before-pass found, and what was fixed

### 1. Inconsistent page-header hierarchy ("Stage N of 6" placement)

Stage 1-3 (pre-dating M008E, built under M008B/M008C) showed "Stage N of 6" as a standalone
`<p class="stage-indicator">` line **above** the `.page-header` block. Stage 4 (WI1's own
approved work) instead folds the stage context into `.page-header__subtitle` itself
("{organisation} · Stage 4 of 6 · Question N of M"). Real-browser inspection at 1280px made
this visually obvious: Stage 1-3's own `<h1>` sat lower, with an extra, differently-styled
line above it that Stage 4 does not have — exactly the "consistent page hierarchy" the
increment's own objective calls for.

**Fix:** Stage 1-3 now fold "Stage N of 6" into `.page-header__subtitle`, matching Stage 4's
established pattern exactly (`{{ organisation.name }} · Stage N of 6`). The now-unused
`.stage-indicator` CSS rule (confirmed via repo-wide grep to have no other consumer) was
removed from `static/organisations/css/app.css` rather than left as dead CSS.

### 2. Inconsistent progress presentation

Foundations and Stage 4 both show a short text label **plus** the shared `.progress` linear
bar component. Stage 1-3 showed text only ("N of X confirmed so far."), with no visual bar —
a real, visible inconsistency in "progress presentation" (explicitly named in this
increment's objective).

**Fix:** Stage 1-3's confirmed-count line is now the real, always-visible
`.progress__label` of the shared `.progress` component, with a decorative
`.progress__track`/`.progress__fill` beneath it, `aria-hidden="true"` (same accessible
pattern Stage 4 already uses — the real percentage is already stated in the label text, so
the bar is never announced twice). The fill width is computed with Django's own
`{% widthratio %}` tag from the same `confirmed_count`/`total_count` values already in
context — no new number, no view/service change, exactly the technique Stage 4's own bar
already uses from `progress.reviewed`/`progress.total`. The former plain-text-only
`.stage-progress` CSS rule (confirmed unused elsewhere) was removed alongside
`.stage-indicator`.

### 3. Inline-style proliferation on Risks & Actions

`risk_register/templates/risk_register/foundations_risks_actions.html` had a `style="text-
align: left;"` inline attribute on its explanatory `.empty-state` block (`.empty-state`
itself defaults to centred text, correct for a genuine empty-state message, wrong for real
explanatory prose). PID §E8's "avoid inline-style proliferation" — the exact same category
WI1 already fixed once for Foundations' own former inline `style="margin-bottom: ..."` (now
`.section-header`).

**Fix:** one new shared modifier, `.empty-state--left` (`static/organisations/css/app.css`),
applied here. This is additive only — `.empty-state` on its own is untouched and still
centres text by default.

**Deliberately NOT touched:** `risk_register/list.html` and `risk_register/detail.html` carry
the exact same `style="text-align: left;"` idiom and the same `.risk-card`/`var(--radius)`
panel treatment as this page's own `.risk-action-card`. Both files are outside this
increment's bounded scope (they belong to the standalone Risk register app, not the guided
Foundations journey) — migrating them to `.empty-state--left` or to the `--radius-lg` panel
scale would be a reasonable follow-up but was left alone here rather than reached into a
sibling file not named in this dispatch's scope.

## What was deliberately left unchanged (considered, not a defect)

- **`.risk-action-card`'s `var(--radius)` panel radius** (rather than `--radius-lg`, which
  `.summary-card`/`.foundations-row`/`.stage-tile` use). This page's own `.risk-action-card`
  is styled identically to `risk_register/list.html`'s sibling `.risk-card` component
  (same radius, same badge-band colour values, same left-accent-border convention) — bumping
  only this file to `--radius-lg` would create a *new* inconsistency between the two risk-card
  surfaces rather than removing one, since the sibling file is out of this increment's scope.
  Left as-is; a future increment covering the standalone Risk register app could reconsider
  both together.
- **Risks & Actions' page-header subtitle** keeps its own "← Back to Foundations · {org}"
  pattern rather than gaining a "Stage 5 of 6" label (the Foundations workspace's own stage
  tile does call it "Stage 5: Your Risks & Actions", and `organisations/tests/
  test_guided_journey.py`'s own comments confirm the guided-journey resolver treats it as a
  real stage). This page does not follow the sequential Back/Next chaining Stage 1-4 share
  (no "next stage" action, reachable from multiple places, and the resolver can skip straight
  past it — "Judgement call 2" in `organisations/guided_journey.py`). Adding "Stage 5 of 6"
  risked implying a sequential-continuation semantic the product does not actually enforce;
  left unchanged rather than invent new wording not already stated elsewhere.
- **`.profile-form`** (the `<form>` class on Stage 1-3) has no CSS rule anywhere in the
  stylesheet — it is a shared, pre-existing, deliberately-empty hook also used by
  `key_assets/form.html`, every `workplace/*.html` onboarding template, `organisations/
  profile_form.html`, and `governance/edit_my_details.html`. Left untouched: it is a shared
  selector well outside this increment's own file list, not something to style unilaterally
  from here.
- **Stage 4's own template/CSS** — reviewed, not re-designed, per this dispatch's explicit
  instruction. No sub-view was found missed.

## Component vocabulary used — no new component introduced except one modifier

Every change reuses WI1's existing vocabulary (`.page-header`/`.page-header__subtitle`,
`.progress`/`.progress__label`/`.progress__track`/`.progress__fill`, `.summary-card`,
`.form-section`, `.field`, `.button--primary`/`--secondary`). The one new class,
`.empty-state--left`, is a modifier on an existing component (not a new component), added
because the existing vocabulary had no left-aligned variant of `.empty-state` and the need
recurs within this increment's own scope (see "Inline-style proliferation" above).

## Verification

### Real-browser overflow check (Playwright `scrollWidth`/`clientWidth`), all six surfaces, all three widths

| Surface | 375px | 768px | 1280px |
|---|---|---|---|
| Stage 1 | 375 == 375 | 768 == 768 | 1280 == 1280 |
| Stage 2 | 375 == 375 | 768 == 768 | 1280 == 1280 |
| Stage 3 | 375 == 375 | 768 == 768 | 1280 == 1280 |
| Foundations (unchanged, re-verified) | 375 == 375 | 768 == 768 | 1280 == 1280 |
| Risks & Actions | 375 == 375 | 768 == 768 | 1280 == 1280 |
| Stage 4 (unchanged, re-verified) | 375 == 375 | 768 == 768 | 1280 == 1280 |

No horizontal overflow anywhere — WI1's own `.progress` `flex-wrap: wrap` fix (the first
permanent regression class) is confirmed still in effect for the new Stage 1-3 progress bars
too (same shared CSS rule, same component, never duplicated locally).

### Keyboard/focus-visible spot check (the second permanent regression class)

No new active/selected/status styling was introduced by this increment (the new `.progress`
markup on Stage 1-3 is a straight reuse of the existing shared component; `.empty-state--left`
only changes `text-align`). As a regression check rather than a new-styling proof, computed
`box-shadow` was measured before/after `.focus()` (the same method WI1's own independent audit
used to catch the sidebar accent-bar/focus-ring collision on PR #97):

- Stage 1's primary submit button (`button.button--primary`): `box-shadow` changes from
  `none` to `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px` on focus — the shared `:focus-visible`
  rule still applies correctly, unaffected by this increment's changes.
- The sidebar's current-page accent-bar/focus-ring combination (the exact WI1 regression)
  was not re-triggered: this increment adds no new `aria-current`/active-state CSS anywhere.

### Test suite

Run inside the disposable `m008ewi2incr1` stack, `DJANGO_ENV=test` (not the stack's own
development-mode `.env`), full `organisations`, `risk_register`, `security_baseline`, and
`core` suites (every app whose templates/views this increment touched, plus `core` for its
shared cross-app browser-acceptance/regression coverage):

```
852 passed, 7 skipped, 1 xfailed, 398 warnings in 785.31s (0:13:05)
```

A targeted, verbose re-run of exactly the files this increment's own changes touch or could
affect (`organisations/tests/test_stage1_business_view.py`,
`test_stage2_people_workplaces_view.py`, `test_stage3_technology_data_view.py`,
`test_guided_journey.py`, `test_foundations_view.py`,
`risk_register/tests/test_foundations_risks_actions.py`) with `-rs` (skip reasons) confirms
every one of those 66 tests passes with zero skips:

```
66 passed, 61 warnings in 66.60s (0:01:06)
```

The 7 skips / 1 xfail in the full run are pre-existing, unrelated to any file this increment
touched (not in `organisations`'s stage/foundations tests, `risk_register`'s foundations-
risks-actions tests, or any template/CSS this increment changed).

- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: "No changes detected" — this increment
  needed no migration.
- `gitleaks detect` (git-history-scoped, not `--no-git`), run after committing this
  increment's work: no leaks found.
- Dependency manifests confirmed byte-identical: `git diff --stat -- requirements.txt
  requirements.in requirements-dev.txt requirements-dev.in package.json` — empty.
- `ai_platform` / AI call paths: confirmed untouched — no file in this increment's diff
  references `ai_platform`, and none of the changed templates/CSS invoke anything in that
  app.
- DARWIN: confirmed zero references anywhere in this increment's diff (`git diff | grep -i
  darwin` — no match).

## Complete changed-paths list

New:
- `.claude/skills` — none (no new design doctrine needed; existing doctrine fully covers this
  increment).
- `docs/evidence/M008E-WI2-INCREMENT-1-FOUNDATIONS-JOURNEY.md` (this file)
- `docs/evidence/m008e-wi2-screenshots/increment-1/before/*.png` (6 pages × 3 widths = 18
  files)
- `docs/evidence/m008e-wi2-screenshots/increment-1/after/*.png` (6 pages × 3 widths = 18
  files)
- `scripts/_m008e_wi2_incr1_capture.py` (evidence-generation tooling, not product code —
  modelled on WI1's own `scripts/_m008e_screenshot_capture.py`)

Changed:
- `organisations/templates/organisations/stage1_business.html` — page-header subtitle now
  includes "Stage 1 of 6"; confirmed-count line now uses the shared `.progress` component.
- `organisations/templates/organisations/stage2_people_workplaces.html` — same two changes,
  Stage 2.
- `organisations/templates/organisations/stage3_technology_data.html` — same two changes,
  Stage 3.
- `risk_register/templates/risk_register/foundations_risks_actions.html` — former inline
  `style="text-align: left;"` replaced with the new `.empty-state--left` modifier class.
- `static/organisations/css/app.css` — `.stage-indicator`/`.stage-progress` rules removed
  (both now unused); one new modifier, `.empty-state--left`, added next to `.empty-state`.

Unchanged (confirmed): every dependency manifest in the repository;
`security_baseline/templates/security_baseline/foundations_question.html` (Stage 4);
`organisations/templates/organisations/foundations.html`; `organisations/views.py`;
`risk_register/views.py`; every migration; every route; every answer-semantics/posture/
risk-generation code path.

## Hard-boundary STOP conditions encountered

None. Every change in this increment is presentation-only: page-header markup, a decorative
progress-bar visual over an already-shown number, and one inline-style-to-class migration.
No question catalogue, answer value, mapping, UNKNOWN/PARTIAL semantics, save behaviour,
route, progress/completion methodology, posture/risk-generation logic, tenant isolation,
entitlement logic, AI behaviour, or data model/migration was touched.
