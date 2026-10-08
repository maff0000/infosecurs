# M008E-WI2-INCREMENT-4 — Customer Assurance / Reset Confirmation / Pre-organisation Surfaces

**Parent PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`
**Governing Work Order:** `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md` (this is ONE
bounded increment under that Work Order, not a separate Work Order — the fourth and FINAL
increment under this rollout, following `docs/evidence/M008E-WI2-INCREMENT-1-FOUNDATIONS-JOURNEY.md`,
`docs/evidence/M008E-WI2-INCREMENT-2-RISK-POLICY-SURFACES.md` and
`docs/evidence/M008E-WI2-INCREMENT-3-COMPANY-GOVERNANCE-SURFACES.md`).
**Base SHA:** `7c7609f57f2e23a44db74bf2e6a6be73b7fa6798` (Increment 3's own evidence commit,
confirmed via `git rev-parse HEAD` before any change — already independently verified clean by
the Delivery Controller).
**Design authority:** `.claude/skills/infosecurs-ui-design/SKILL.md` (durable doctrine) and
`docs/evidence/M008E-DESIGN-DIRECTION.md` (WI1's already-approved visual system) — this
increment introduces no new visual language, only applies/extends the existing one.

## Scope executed

Apply the already-approved M008E visual system consistently across the final WI2 surface group
named in this increment's dispatch:

- Customer Assurance (`questionnaire/templates/questionnaire/{list,response_detail,response_edit}.html`)
- The reset confirmation screen (`organisations/templates/organisations/customer_zero_reset_confirm.html`
  — reached from the Home/Company-hub "Reset test organisation" link, both already restyled
  under WI1)
- Login (`templates/registration/login.html`)
- Pre-organisation surfaces: `organisations/templates/organisations/{list,create}.html` (reached
  before any organisation context exists — `organisations:list`/`organisations:create`,
  confirmed via `organisations/views.py` to carry no `organisation` in their own context) and
  `templates/identity/unsafe_link_rejected.html` (the one other `templates/base.html`-extending,
  pre-organisation-context page in the codebase — see `templates/application_shell.html`'s own
  header comment and `docs/evidence/M007-SESSION-ENTITLEMENTS.md` finding 5, which independently
  confirms these are the only four pages that still extend `base.html` rather than
  `application_shell.html`, none of which ever has `organisation` in context).

`questionnaire/templates/questionnaire/response_edit.html` was reviewed and found already fully
compliant with the established vocabulary — see "What was reviewed and left unchanged" below.

## Method — browser-led, not blind-from-source

A disposable Docker Compose stack (`docker compose -p m008ewi2incr4`, `WEB_HOST_PORT=8997`,
`POSTGRES_HOST_PORT=15537`, both loopback-only, `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true`)
was brought up from this worktree — `docker ps` was checked first and confirmed no
`m008ewi2incr*`-named stack running; the live `infosecurs-relocation` dev stack (port 8884) and
every other host service were left untouched throughout.

Chromium was installed at runtime into the running `web` container (`playwright install
--with-deps chromium`), per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md` — and, per this
dispatch's explicit instruction, **explicitly verified** before trusting any capture/test result:
a direct `playwright.sync_api.sync_playwright().chromium.launch()` call, navigating to the real
login page and reading its title, was run and confirmed `CHROMIUM LAUNCH OK` before any capture
or test run. This check was repeated a second time after the container was recreated mid-session
(a `.env` edit triggers `docker compose up -d` to recreate the `web` container, which wipes its
writable layer, including the just-installed Chromium cache) — the re-verification caught this
immediately rather than silently producing a false "SKIPPED" result, exactly the failure mode
this dispatch's own instructions warned about.

Representative data was seeded into the real Customer Zero organisation via the ORM
(`scripts/_m008e_wi2_incr4_seed.py`, evidence-generation tooling, not product code, modelled on
Increment 3's own `scripts/_m008e_wi2_incr3_seed.py`): three `QuestionnaireQuestion`/
`QuestionnaireResponse` rows created directly via the ORM — **never** via `questionnaire:analyse`
(which calls the real AI gateway) — a long/overflow-provoking draft GAP response, an accepted
SUPPORTED response, and a superseded CONFIRM response (pointing at the accepted one), to exercise
every outcome/status badge colour and the superseded-note banner; plus a second organisation
membership for the `customerzero` user with a deliberately long name, so `organisations:list`
renders more than one `.card-list` row and exercises the long-name overflow-wrap protection.

Before touching any file, real-Chromium screenshots of every in-scope surface were captured at
1280/768/375px (`scripts/_m008e_wi2_incr4_capture.py`, modelled on Increment 3's own capture
script) — login captured from a genuinely fresh, anonymous browser context (an authenticated
session must never influence how the pre-login page itself renders), everything else from an
authenticated `customerzero` session. 8 pages were captured both before and after (24 screenshots
per pass, 48 total): login; organisations list; organisations create; Customer Assurance list;
Customer Assurance response detail (draft); Customer Assurance response detail (accepted);
Customer Assurance response edit; reset confirmation.

`templates/identity/unsafe_link_rejected.html` is reached only mid-way through a real federated
OAuth linking attempt (`identity/adapters.py`), not from any direct URL route, so it cannot be
driven through ordinary Playwright navigation in a disposable dev stack with no real
Google/Microsoft OAuth credentials configured. It was still verified with real Chromium, not
blind-from-source: `django.template.loader.render_to_string` rendered the real template (with a
`RequestFactory` request and the same context keys the real adapter supplies) to a string, which
Playwright then loaded via `page.set_content()` against the running stack's own origin (so the
real `{% static %}` stylesheet resolves and applies) — real browser, real CSS, real computed
layout, at 1280px and 375px, both confirming no horizontal overflow (`1280 == 1280`,
`375 == 375`).

## What the before-pass found, and what was fixed

### 1. Reset confirmation page: the exact same dead CSS-class defect WI1 already found and fixed elsewhere — now found here (the one surface that fix never reached)

`organisations/templates/organisations/customer_zero_reset_confirm.html` rendered its panel as
`.summary-card dev-tools-card`. `dev-tools-card` has **no CSS rule anywhere in the stylesheet** —
confirmed by a repo-wide grep before touching anything. This is the identical defect class
WO-M008E-WI1 already found and fixed on both of this page's own upstream entry points: its own
`app.css` comment for `.dev-panel` records that "the former plain `.summary-card dev-tools-card`
... had no CSS rule of its own - this card was visually identical to the three above it", fixed
on Home and the Organisation hub. This confirmation page — reached by clicking through from
either of those already-fixed `.dev-panel` affordances — was the one surface that fix never
reached: the "before" screenshot shows it rendering as an ordinary plain white card,
indistinguishable from any other content panel in the product, directly contradicting the design
doctrine's own §7 requirement that the one development-only affordance in the product be
"unmistakably different" — most consequential on the one page whose entire purpose is executing
that dev-only action.

**Fix:** moved onto the shared `.dev-panel` component (dashed amber border, `.dev-panel__tag`
"Dev" chip), identical to Home/the Organisation hub. No wording, no new markup beyond the
existing shared component's own structure.

### 2. Reset confirmation page: the actual destructive action used the ordinary primary-button treatment, weaker than the links that merely navigate to it

The confirmation page's own submit button — the one control in the entire product that actually
executes an irreversible delete — used `.button--primary`, the same styling as any routine
"continue"/"save" action. Both of this page's own upstream entry points (Home, the Organisation
hub) already link to it using `.button--destructive` (the variant WO-M008E-WI1 introduced
specifically for "the one action in the product that permanently deletes data" — its own
`app.css` comment). The actual execute-the-action button, on the one page where the action is
actually executed, carried a weaker visual signal than the mere navigation links leading to it —
backwards from the action-hierarchy objective this increment's own dispatch names explicitly
("the reset confirmation's destructive action in particular").

**Fix:** `.button--primary` → `.button--destructive` on the submit button only. Same label
("Reset test organisation"), same `<form>`, same fail-closed view-level check
(`organisations.views.customer_zero_reset`) — confirmed untouched, see "Security gate" section
below.

### 3. Reset confirmation page: the confirmation input had no `.field` wrapper

The `<label>`/`<input>` pair for the "Type RESET to confirm" control was a bare
`<p><label>...<br><input></p>`, rendering the label as plain unweighted text with no consistent
spacing — every other form input in the product (including this same page's sibling pages) uses
the shared `.field` wrapper (bold label, consistent spacing, `.input`'s border/radius/focus-ring
styling).

**Fix:** wrapped in `.field`; input gained `class="input"`. Exact same `id`, `name`,
`autocomplete="off"`, `autocapitalize="off"`, `spellcheck="false"`, `required` attributes,
unchanged — see "Security gate" section below for why this is safe.

### 4. Customer Assurance (Questionnaire list): the paste-a-question form used raw, unclassed controls with inline `style="width: 100%;"`

`questionnaire/templates/questionnaire/list.html`'s textarea and text input carried
`style="width: 100%;"` inline attributes and no `.textarea`/`.input` class at all — rendering as
plain, square-cornered browser-default controls with no border-radius/focus-ring, the one
remaining "inline-style proliferation" instance this increment's own dispatch (and PID §E8) warns
against, on a page this Work Order's own objective names directly ("Customer Assurance"). Labels
were plain, unwrapped `<p><label>...<br></p>` text, not bold like every other form field in the
product.

**Fix:** wrapped in `.field` divs; textarea gained `class="textarea"`, input gained
`class="input"`; inline `style` attributes removed entirely (the classes already provide the
equivalent width/border/radius/focus-ring behaviour, consistent with every other form in the
product).

### 5. Customer Assurance (Questionnaire list): "Questions asked so far" had no visual structure at all

The list of previously-asked questions was a plain `<ul><li>` with the question title, source
label and current-answer link all run together as one unbroken line of inline text (confirmed by
the "before" screenshot) — the exact "weak visual hierarchy"/"pages that look like internal
tooling" defect class the PID's own objective names, on a page this increment's own dispatch
names directly.

**Fix:** a new page-local row component, `.question-row`/`.question-row__body`/`__title`/`__meta`/
`__action` (defined in this page's own `<style>` block, following M008E-WI2-INCREMENT-3's own
precedent for `.workplace-*` rather than reusing another domain's literally-named class) — the
same title/meta/action row shape already established five-plus times by `.foundations-row`,
`.asset-card`, `.risk-card`, `.evidence-card`, `.action-card`, `.state-card` and
`.workplace-card`. Each question now renders as its own bordered row with a bold title, a muted
meta line for the source label, and (where a response exists) a `.button--secondary` action
carrying the **exact same wording as before** ("SUPPORTED (current answer)"/"GAP (draft — not yet
accepted)" etc., unchanged) — no new copy, no new state signal duplicated alongside it (a second,
separate colour badge was deliberately not added here — it would duplicate the exact same outcome
text the button already carries, which is precisely the "visual clutter"/"restrained secondary
information" the design doctrine warns against; see `M008E-WI2-INCREMENT-3`'s own finding 3 for
the identical judgement call made there).

### 6. Customer Assurance (response detail): two hardcoded hex colours, one of them the literal pre-WI1 corporate blue, and two tokens reached for `--color-border` by coincidence rather than the dedicated neutral tokens

`questionnaire/templates/questionnaire/response_detail.html`'s own page-local `<style>` block
hardcoded `.badge--superseded` to `#e6eefb`/`#185ea8` and `.badge--outcome-CONFIRM` to
`#fdf1d6`/`#8a5a00` — the first is the exact literal generic-corporate-blue pairing
`docs/evidence/M008E-DESIGN-DIRECTION.md` §1 describes replacing everywhere else in the product
("generic corporate blue (`#185ea8`) on cold grey"); SKILL.md §5 defines exactly four status
colours (green/amber/red/neutral) and this was a genuine, silent fifth. The second is a
near-duplicate, one-digit-off copy of the real `--color-warning-bg`/`--color-warning-text` token
values (`#fdf1dc`/`#8a5a06`) rather than the tokens themselves — invisible today, but a silent
drift risk against any future palette refresh (the whole point of the token system, per
`app.css`'s own header comment: "renaming/changing a token's *value* reaches every page that
reads it by name; a hardcoded copy never does"). Separately, `.badge--draft` and
`.badge--outcome-NOT_APPLICABLE` both reused `--color-border` as a background by coincidence,
exactly the pattern WO-M008E-WI1 added the dedicated `--color-neutral-bg`/`--color-neutral-text`
tokens to replace (its own evidence, §4) — this page was the one surface that addition never
reached.

**Fix:** `badge--draft`/`badge--superseded`/`badge--outcome-NOT_APPLICABLE` → `--color-neutral-bg`/
`--color-neutral-text` (all three are workflow-state/informational, not a security-truth
judgement — SKILL.md §5's own "neutral = unknown/not applicable" meaning, or a plain workflow
state like "draft"/"superseded" that is not itself one of the four judged meanings).
`badge--outcome-CONFIRM` → the real `--color-warning-bg`/`--color-warning-text` tokens (CONFIRM
= "needs confirmation" = SKILL.md §5's own amber meaning — the colour choice was already
semantically correct, only the literal hex was wrong). No colour's underlying meaning changed.

### 7. Customer Assurance (response detail): the superseded-note was a bespoke class with the same hardcoded blue, duplicating a component that already exists for exactly this purpose

`.superseded-note` was a bespoke page-local class (background `#e6eefb`, border `#185ea8` —
the same hardcoded blue as finding 6) for a short contextual note tied to the current response's
own history — precisely the case `.alert`/`.alert--info` (`.claude/skills/infosecurs-ui-design/
SKILL.md` §9's own "alerts/warnings" vocabulary entry, added under WO-M008E-WI1) was already
built for.

**Fix:** replaced `.superseded-note` with `.alert.alert--info`. Same wording, same position, no
new component — one less one-off class, one real defect-colour instance removed.

### 8. Customer Assurance (response detail): `.fact-card`'s radius was never harmonised onto the panel step

`.fact-card` (one card per grounding fact shown under "Why this answer?") is the same full-width
list-row shape as `.asset-card`/`.risk-card`/`.evidence-card`/`.action-card`/`.state-card`/
`.workplace-card`, all of which M008E-WI2-INCREMENT-2/3 harmonised onto the larger `--radius-lg`
panel step (SKILL.md §8's deliberate two-step radius scale) — the recurring defect class
Increment 3 itself numbered as its "sixth occurrence"; this is its seventh.

**Fix:** `.fact-card`'s `border-radius` changed from `var(--radius)` to `var(--radius-lg)`. No
other property changed.

### 9. Login: the username/password fields (inside "Use a local development account instead") were plain, unclassed browser-default controls

Real-browser inspection (expanding the `<details>` disclosure and measuring computed style, not
source-reading alone) showed `#id_username` with `border-radius: 0px` and
`border: 2px inset rgb(118, 118, 118)` — pure browser-default chrome, clashing visibly against
the polished provider buttons immediately above and the rounded `.button--secondary` "Log in"
button immediately below. The surrounding `.field` wrapper was already present and correct
(bold label, spacing); only the `<input>` elements themselves were missing `class="input"`.

**Fix:** `class="input"` added to both `#id_username` and `#id_password`. No other attribute
changed.

### 10. Pre-login error page (`identity/unsafe_link_rejected.html`): its one action was a bare, unstyled link

The "Back to log in" link on this page (reached mid-OAuth-linking-attempt, per
`identity/adapters.py`) was a plain `<a>` with no button styling — the same "action hierarchy"
defect class fixed on Governance roles' "Edit your details" link in Increment 3 (finding 4),
here on the one other pre-organisation-context page in the codebase that still had it.

**Fix:** `class="button button--secondary"` added. No route, no behaviour, no new markup beyond
the one class.

## What was reviewed and deliberately left unchanged (considered, not a defect)

- **`questionnaire/templates/questionnaire/response_edit.html`** — already fully compliant with
  the established vocabulary (`.page-header` correctly wrapped, `.form-card`, `.field`,
  `.form-actions`, `.button--primary`/`--secondary`). Reviewed and captured before/after
  (unchanged pixels); no defect found.
- **`organisations/templates/organisations/list.html`** and **`organisations/templates/
  organisations/create.html`** — already fully compliant (`.page-header`, `.card-list`,
  `.empty-state`, `.form-card`, `.field`). Both reviewed and captured at all three widths; no
  defect found. The long seeded organisation name wraps correctly via the existing
  `.card-list__title { overflow-wrap: anywhere; }` rule (M006-AUDIT-0002 G2).
- **`templates/base.html`'s own `.app-header__nav-primary` block** — confirmed, per
  `docs/evidence/M007-SESSION-ENTITLEMENTS.md` finding 5, to be structurally unreachable dead
  code on every page this increment touches (none of them ever has `organisation` in context) —
  a pre-existing, already-documented finding from a prior Work Order, not something this
  increment introduces or needs to fix; left untouched, consistent with that finding's own
  "non-blocking, no behavioural risk" disposition.
- **The mismatch between this page's own `<h1>`/`<title>` ("Questionnaire Assurance") and the
  sidebar nav label for the same feature ("Customer Assurance",
  `entitlements/migrations/0002_seed_product_areas.py`)** — a genuine, real naming inconsistency,
  found during this increment's own investigation. Deliberately **not fixed**: changing a
  page's own displayed name is a content/copy decision, not a styling/presentation one, and this
  Work Order's own scope is visual/presentation only. Disclosed here transparently rather than
  silently left out of the record or silently "fixed" past this Work Order's own boundary - a
  question for Product Authority, not a styling judgement call for this Implementer to make
  unilaterally.

## Security gate — the reset confirmation page's safeguards are byte-identical

Per this dispatch's own hard boundary, before touching `customer_zero_reset_confirm.html`,
`organisations/views.py::_customer_zero_reset_enabled_for` and
`organisations/views.py::customer_zero_reset` were read in full (see that view's own extensive
module comment on its three authority layers: the environment gate checked first and failing
closed as a plain 404 for both GET and POST; the `CustomerZeroFixture` identity check,
independently re-checked inside `reset_customer_zero_organisation` itself; ordinary tenant-owner
membership via `get_member_organisation_or_404`). **`organisations/views.py` was not touched by
this increment at all** — confirmed by `git diff 7c7609f57f2e23a44db74bf2e6a6be73b7fa6798 --
organisations/views.py` returning empty. Every change to
`customer_zero_reset_confirm.html` is template-only:

- The confirmation input's `id="id_confirmation"`, `name="confirmation"`, `autocomplete="off"`,
  `autocapitalize="off"`, `spellcheck="false"`, `required` attributes are byte-identical — only
  wrapped in a `.field` div and given `class="input"`.
  The view's own `if confirmation != "RESET":` check (case-sensitive, exact-match) reads this
  same `name="confirmation"` POST field exactly as before.
- The submit button's class changed (`.button--primary` → `.button--destructive`); its `type`,
  its being inside the one real `<form method="post">` on the page, and the CSRF token are
  unchanged. No second form, no client-side-only confirmation path, no JavaScript was added
  anywhere on this page.
- Every word of the page's own warning/consequence copy ("This is a development-only tool",
  "will permanently remove", "This action cannot be undone", etc.) is byte-identical.
- `organisations/tests/test_reset_views.py` and `organisations/tests/test_reset_service.py`
  (the view/service-level fail-closed behaviour tests) pass unchanged — see "Test suite" below.

## Component vocabulary used — no shared `app.css` change; two existing components reused on a page that had never reached them, one new page-local component, two existing token categories reused to replace hardcoded hex

Every change reuses WI1/Increment-1/2/3's existing vocabulary (`.dev-panel`, `.field`/`.input`/
`.textarea`, `.button--destructive`/`--secondary`, `.alert`/`.alert--info`, `--radius-lg`,
`--color-neutral-*`/`--color-warning-*`). One new page-local component was added
(`.question-row`/`__body`/`__title`/`__meta`/`__action` in `questionnaire/list.html`'s own
`<style>` block) — not a new design language, the same title/meta/action row shape already used
seven times elsewhere, following Increment 3's own "page-local component, not another domain's
literal class name" precedent. **No shared `static/organisations/css/app.css` change was needed
this increment** — every fix was either a class swap in a template, a page-local `<style>` block
edit, or a page-local component addition.

## Verification

### Real-browser overflow check (Playwright `scrollWidth`/`clientWidth`), all 8 surfaces, 375px

| Surface | 375px |
|---|---|
| Login (anonymous context) | 375 == 375 |
| Organisations list | 375 == 375 |
| Organisations create | 375 == 375 |
| Customer Assurance list | 375 == 375 |
| Customer Assurance response detail (draft) | 375 == 375 |
| Customer Assurance response detail (accepted) | 375 == 375 |
| Customer Assurance response edit | 375 == 375 |
| Reset confirmation | 375 == 375 |
| `identity/unsafe_link_rejected.html` (rendered via `render_to_string` + `page.set_content`) | 375 == 375 |

No horizontal overflow anywhere, including the long seeded organisation name (organisations
list) and the long, deliberately overflow-provoking questionnaire question (Customer Assurance
list and its response detail/edit pages).

### Keyboard/focus-visible spot check (the second permanent regression class)

No new active/current-state CSS was introduced by this increment (every change is plain content
styling — badge colours, a button variant swap, a card/panel class swap, a new but
non-state-bearing row component). As a direct regression check (computed `box-shadow`
before/after `.focus()`, the same method WI1's own §8.2 finding used after independent audit
caught the original miss):

- Reset confirmation page's submit button (now `.button--destructive`): `box-shadow` changes
  from `none` to `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px` on focus.
- Login's first provider button (`.button--provider`, unchanged by this increment, re-checked as
  a control): `box-shadow` changes from `none` to the same focus-ring value on focus.

Both genuinely different before/after — no repeat of the WI1 sidebar-accent-bar regression class
anywhere this increment touched.

### Badge text-label check (status colour is never the only signal)

Confirmed by direct screenshot of the previously-unexercised superseded/CONFIRM combination (the
seeded superseded response): `SUPERSEDED` (now neutral grey) and `CONFIRM` (now real warning
amber) both render as real, readable pill text — never colour alone — and the superseded-note
`.alert.alert--info` beneath them is visually and semantically distinct from the dev-only
`.dev-panel` amber (never confused with a severity signal, per SKILL.md §7).

### Test suite

Run inside the disposable `m008ewi2incr4` stack, `DJANGO_ENV=test` (not the stack's own
development-mode `.env`):

```
$ docker compose -p m008ewi2incr4 exec -e DJANGO_ENV=test web pytest -q questionnaire organisations identity core
611 passed, 7 skipped, 1 xfailed, 330 warnings in 752.89s (0:12:32)
```

- `python manage.py makemigrations --check --dry-run`: "No changes detected" — this increment
  needed no migration.
- `gitleaks detect` (git-history-scoped, not `--no-git`), run after committing this increment's
  work: 143 commits scanned, "no leaks found" (run after committing this increment's work).
- Dependency manifests confirmed byte-identical: `git diff --stat -- requirements.txt
  requirements.in requirements-dev.txt requirements-dev.in package.json` against base SHA
  `7c7609f57f2e23a44db74bf2e6a6be73b7fa6798` — empty.
- `ai_platform` / AI call paths: confirmed untouched — `git diff 7c7609f5... | grep -i
  ai_platform` returns no match. The three seeded `QuestionnaireResponse` rows used for
  screenshot capture were created directly via the ORM, never via `questionnaire:analyse` (the
  view that calls the real AI gateway) — zero AI calls were made at any point in this increment.
- DARWIN: confirmed zero references anywhere in this increment's diff (`git diff 7c7609f5... |
  grep -i darwin` — no match).

## Complete changed-paths list

New:
- `docs/evidence/M008E-WI2-INCREMENT-4-ASSURANCE-RESET-PREORG-SURFACES.md` (this file)
- `docs/evidence/m008e-wi2-screenshots/increment-4/before/*.png` (8 pages × 3 widths = 24 files)
- `docs/evidence/m008e-wi2-screenshots/increment-4/after/*.png` (8 pages × 3 widths = 24 files)
- `scripts/_m008e_wi2_incr4_seed.py` (evidence-generation tooling, not product code)
- `scripts/_m008e_wi2_incr4_capture.py` (evidence-generation tooling, not product code)

Changed:
- `organisations/templates/organisations/customer_zero_reset_confirm.html` — `.summary-card
  dev-tools-card` → `.dev-panel`; submit button `.button--primary` → `.button--destructive`;
  confirmation input wrapped in `.field` + `class="input"`. View/gate untouched.
- `questionnaire/templates/questionnaire/list.html` — paste-a-question form fields wrapped in
  `.field` + `.textarea`/`.input`, inline `style` removed; "Questions asked so far" moved onto a
  new page-local `.question-row` component.
- `questionnaire/templates/questionnaire/response_detail.html` — `badge--draft`/
  `badge--superseded`/`badge--outcome-CONFIRM`/`badge--outcome-NOT_APPLICABLE` moved from
  hardcoded/near-duplicate hex onto the real `--color-neutral-*`/`--color-warning-*` tokens;
  `.superseded-note` replaced with `.alert.alert--info`; `.fact-card` radius harmonised to
  `--radius-lg`.
- `templates/registration/login.html` — `#id_username`/`#id_password` gained `class="input"`.
- `templates/identity/unsafe_link_rejected.html` — "Back to log in" upgraded to
  `.button--secondary`.

Unchanged (confirmed): every dependency manifest in the repository; `organisations/templates/
organisations/{list,create}.html`; `questionnaire/templates/questionnaire/response_edit.html`;
`organisations/views.py` (including `customer_zero_reset` and
`_customer_zero_reset_enabled_for`); every migration; every route; tenant isolation;
entitlements; authentication/session logic; AI behaviour; `ai_platform`; DARWIN.

## Hard-boundary STOP conditions encountered

None. Every change in this increment is presentation-only: a dead CSS class replaced with the
already-existing component it was supposed to use, a button-variant swap that strengthens (never
weakens) the one destructive action's visual signal, form fields wrapped in the product's own
established `.field`/`.input`/`.textarea` vocabulary, hardcoded/near-duplicate hex colours
replaced with the named design tokens they were always supposed to read, one bespoke class
replaced with an existing component built for exactly that purpose, one radius-value
harmonisation, and one new page-local row component following a seven-times-precedented shape.
No view, route, security gate, entitlement, AI behaviour, persistence/data model, or migration
was touched.

## M008E-WI2 final surface-coverage check (this is the last planned WI2 increment)

Cross-checking `docs/work-orders/WO-M008E-WI2-VISUAL-ROLLOUT.md`'s own authorised surface list
against WI1 + Increments 1-4:

| Surface | Covered by |
|---|---|
| Home | WI1 |
| Foundations workspace | WI1 |
| Stages 1-4 | WI1 (Stage 4) + Increment 1 (Stages 1-3; Stage 4 reviewed, no change needed) |
| Risks & Actions | Increment 1 |
| Security Policy | Increment 2 |
| Security State | Increment 2 |
| Baseline | Increment 2 (reviewed — legacy redirect into the already-restyled Stage 4, no separate template) |
| Assets | Increment 2 |
| Risks | Increment 2 |
| Evidence | Increment 2 |
| Remediation | Increment 2 |
| Company/Organisation | WI1 (hub) + Increment 3 (cross-page reference, unchanged) |
| Profile | Increment 3 |
| Governance | Increment 3 |
| Workplace | Increment 3 |
| Activity | Increment 3 |
| Customer Assurance | **Increment 4 (this increment)** |
| The dev reset confirmation screen | **Increment 4 (this increment)** |
| Login/pre-organisation surfaces | **Increment 4 (this increment)** |

Every surface named in `WO-M008E-WI2-VISUAL-ROLLOUT.md`'s authorised list has now been covered
across WI1 and Increments 1-4. Nothing on that list was found missed.
