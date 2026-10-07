# M008E-WI1 — Design Direction (Phase 2 checkpoint)

**PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md` §E4 Phase 2 / §E5.
**Work Order:** `docs/work-orders/WO-M008E-WI1.md`.
**Durable doctrine:** `.claude/skills/infosecurs-ui-design/SKILL.md` (read
that file for the full audience/avoid-list/interaction/status/
accessibility doctrine this direction implements — this document is the
rationale for *this specific* Work Order's execution of it, not a
restatement of the doctrine itself).
**Current-state findings this design responds to:**
`docs/evidence/M008E-CURRENT-UX-REVIEW.md`.

This is the Phase 2 checkpoint required by PID §E5: a real, implemented
visual-design direction for exactly three representative surfaces — Home,
Foundations/Stage 4, Company/Organisation hub — plus the newly-discoverable
DEV reset panel. **This is a checkpoint for Product Authority approval, not
authority to roll the design across the rest of the application** (PID
§E5/§E6).

---

## 1. Design language and why

The current-state review found a product that is functionally sound but
reads as generic internal Django tooling: stock corporate blue on cold
grey, every card the same weight regardless of importance, no visual
distinction between a routine navigation link and a destructive action
(§§1–5 of the review). The brief (PID §E1) is explicit about the target:
calm, clear, premium, trustworthy B2B software for a non-specialist SME
owner — not flashy, not a security dashboard, not generic SaaS.

The direction chosen:

- **A deep teal primary (`#0f6a5c`) on a warm-neutral canvas (`#eef1ef`)**,
  replacing the generic corporate blue (`#185ea8`) on cold grey
  (`#f4f6f8`). Teal reads as "professional assurance" rather than
  "generic admin tool" or "hacker/cyber" — it sits deliberately away from
  both the stock Bootstrap-blue default and the near-black-plus-neon
  cliché the product doctrine explicitly avoids. This is not an
  from-nothing invention: `docs/design/prototype.html`, an earlier,
  uncommitted-to-product design exploration already present in this
  repository, independently arrived at the same ink/paper/teal family —
  treated here as a legitimate precedent to build on (continuity with the
  team's own prior thinking), not copied verbatim (that file also
  specifies Google Fonts, which ADR-0001 forbids for the real product, and
  a ring/gauge metric visual, which PID §13/§2.3 forbids for Home — both
  deliberately NOT carried over; see §6 below).
- **A deliberate two-step radius scale** (`--radius` 6px for controls,
  new `--radius-lg` 12px for panels/cards) instead of one radius applied
  to everything — a direct response to the review's "every card is the
  same weight" finding and the design doctrine's own "excessive rounded
  cards" warning.
- **A reserved, high-weight treatment for the ONE primary action per
  page** — Home's "Continue Security Foundations" CTA moved from a
  light-tint box (visually too close to the plain metric cards beneath
  it, per the review) to a solid filled panel using the primary colour as
  a background. This is the only place in the product that colour is used
  this way, which is what gives it weight — it is not a pattern applied
  to anything else.
- **A third button variant, `.button--destructive`**, for the one action
  in the product that permanently deletes data (the Customer Zero reset).
  Previously indistinguishable from "View security state."
- **A dashed-border, amber-tagged "DEV" panel** for the one development-
  only affordance in the product — visually unmistakable as not being
  ordinary product content, and deliberately never using the green/amber/
  red/neutral status vocabulary for anything other than its own literal
  "Dev" tag (which borrows the amber tone for visibility, the same amber
  already used for "needs attention," which already carries
  cautionary weight in this product — not a new, fifth status colour).

No external fonts/CDN assets were added (ADR-0001) — the same system font
stack continues to carry the whole product; distinctiveness comes from
colour, the radius scale, spacing discipline, and the new intentional
hierarchy (solid CTA vs. plain card vs. dashed dev panel), not from a new
typeface.

## 2. Typography scale

| Element | Size | Weight | Notes |
|---|---|---|---|
| `h1` (page title, one per page) | 1.75rem | 700 | up from 1.6rem — more separation from `h2` |
| `h2` (section heading) | 1.25rem | 600 | up from 1.2rem |
| `h3` (new) | 1.05rem | 600 | a third step the product had no name for before (used inside panels, e.g. stage tile headings) |
| body | 1rem | 400 | unchanged, line-height 1.5 |
| meta/secondary | ~0.8125–0.85rem | 400 | unchanged |

Font family unchanged: `-apple-system, "Segoe UI", Roboto, Helvetica,
Arial, sans-serif` (ADR-0001). No new uppercase "eyebrow" label pattern
was introduced — the only two eyebrow-style labels in the product
(the organisation-context label, Stage 4's own question-category label)
are untouched and remain the only ones, per the design doctrine's
explicit caution against proliferating that pattern.

## 3. Spacing / layout system

The existing `--space-1` through `--space-5` scale (4/8/16/24/40px) is
unchanged and used exclusively — no ad-hoc pixel values were introduced
anywhere in this Work Order's new CSS. Page-width rules (`.app-main`
720px, `.shell-sidebar` 240px) are unchanged. The one new layout primitive
is the two-step radius scale described in §1.

## 4. Colour and status-badge semantics

**The product's four-colour status meaning is unchanged and was not
touched in this Work Order**: green = supported/satisfactory/completed,
amber = needs attention/confirmation, red = gap/action required, neutral
= unknown/not applicable. The `.badge` component (Foundations'
Yes/Partially/No/Not sure/Not applicable + Complete/Needs completion
chips) is untouched — same markup, same per-page colour-variant `<style>`
block convention, same "never colour-only" guarantee (every badge still
carries a real text label). Two new named tokens,
`--color-neutral-bg`/`--color-neutral-text`, were added so a future page
can reach for an intentional neutral token instead of reusing
`--color-border` by coincidence (the review's §7 finding) — nothing that
currently renders changed colour as a result; this is additive only.

Every colour pairing in the refreshed palette was checked against WCAG
2.2 AA (4.5:1 for normal text, with buttons specifically checked against
the stricter normal-text floor rather than assuming the 3:1 large-text
allowance applies to a ~15px bold label):

| Pairing | Ratio |
|---|---|
| Body text (`#17241d`) on canvas (`#eef1ef`) | 14.13:1 |
| Muted text (`#57665d`) on canvas | 5.33:1 |
| Primary (`#0f6a5c`) on white | 6.49:1 |
| White on primary | 6.49:1 |
| Primary-dark (`#0b4f45`) on white | 9.47:1 |
| Success text on success bg | 5.76:1 |
| Warning text on warning bg | 5.30:1 |
| Error text on error bg | 6.35:1 |
| Neutral text on neutral bg | 5.04:1 |
| White on destructive button (`#b23f3b`) | 5.73:1 |

The destructive button colour was deliberately chosen darker than the
product's existing plain `--color-error-border` (`#d9534f`, which would
have given only 3.96:1 for white text — insufficient for a bold ~15px
label) specifically so the one most consequential button in the product
clears the same bar as everything else, not a lower one.

## 5. Reset-control placement and gating

Per PID §E2/§E9: the DEV Customer Zero reset panel now appears on Home
(`organisations/templates/organisations/detail.html`), using the exact
copy specified in the PID, in addition to its existing location on the
Company hub (`organisations/templates/organisations/organisation_hub.html`,
restyled onto the same new `.dev-panel` component, not removed). Both
templates' visibility is driven by the same single boolean,
`customer_zero_reset_enabled`, now computed by one shared view-layer
function, `organisations.views._customer_zero_reset_enabled_for`
(`settings.CUSTOMER_ZERO_RESET_ENABLED and CustomerZeroFixture.objects.
filter(organisation=organisation).exists()`) — previously the exact same
two-line expression duplicated once already (in `organisation_hub`); this
Work Order factored it into one function used by both call sites rather
than adding a third copy for Home. **No new gating logic was written** —
this is the same check `organisation_hub` already made, and the real
reset view (`organisations.views.customer_zero_reset`) still independently
enforces its own fail-closed authorization regardless of what any
template renders (unchanged, untouched by this Work Order).

The Home panel's own action is a plain `<a href="...">` to the existing
confirmation page (`organisations:customer_zero_reset`), never a `<form>`
of its own — it cannot execute a reset directly, only navigate to the
existing, unmodified confirmation-and-type-RESET flow. Proven in
`organisations/tests/test_home_reset_panel.py` (see §8).

On Home, the panel is rendered independently of `is_paused` — the view
computes `customer_zero_reset_enabled` once and passes it into both the
Paused and non-Paused render branches, because it is a development-
environment/fixture-identity gate, not a package-tier entitlement (PID
§E9 — the dev tool must not quietly disappear for a Paused test session).

## 6. What was deliberately NOT changed

- **Home's two metric cards remain a plain percentage + text, no gauge/
  ring/chart** — PID §13/§2.3's own binding "function before form"
  decision, reaffirmed rather than reopened. `docs/design/prototype.html`
  uses an SVG ring for this; it was not adopted.
- **The `needs-attention__line` markup is byte-identical** — only its
  CSS (a sunken-row background) changed, so the mechanical real-HTML-parse
  proof in `organisations/tests/test_home_view.py` (every line is never
  itself one giant anchor, only the words "Go to X" are the link) needed
  no changes and still passes unmodified.
- **No new dependency.** `requirements.txt`/`requirements.in`/
  `requirements-dev.txt`/`requirements-dev.in` are byte-identical to the
  base commit (`git diff` confirms no changes) — no package manifest in
  this repository changed at all.
- **No SPA framework, no Tailwind, no component library** — every change
  is a server-rendered Django template and a hand-written addition to the
  existing `static/organisations/css/app.css`.
- **No route, view-level security check, entitlement, or data-model
  change.** `organisations/views.py`'s only non-cosmetic change is the
  `_customer_zero_reset_enabled_for` extraction described in §5, which
  reads the same two facts the code already read, from the same places.

## 7. Accessibility choices

- Every new/changed colour pairing cleared WCAG 2.2 AA (§4).
- `:focus-visible` styling is untouched and still applies to every new
  interactive element (buttons, option cards, the dev panel's link) with
  no additional work needed — it was already a global rule.
- The new decorative progress bars (Foundations' completion summary,
  Stage 4's reuse of the same component) are marked `aria-hidden="true"`
  — the exact same percentage is already real, readable text immediately
  beside each bar, so the bar is not announced a second time in a
  different form to screen-reader users.
- The new `.option-card` selected-state styling (`:has(input:checked)`)
  is a progressive enhancement on top of the real, always-accessible
  native radio input — a browser without `:has()` support still shows a
  fully functional, correctly-labelled radio button; it only loses the
  extra border/tint visual flourish, never the actual selection state.
- The sidebar's active-page indicator gained a left accent bar
  (`box-shadow: inset 3px 0 0 var(--color-primary)`) on top of its
  existing tint — a second, stronger visual cue for "you are here,"
  addressing the review's finding that the old pale-tint-only signal was
  genuinely low-contrast at a glance (§4/§8 of the review) — `aria-
  current="page"` itself was already correct and is untouched.
- Manual keyboard tabbing was re-checked after the CSS changes on Home,
  Foundations, and the Stage 4 question form in the disposable stack —
  focus order unchanged, visible focus ring present throughout, no
  keyboard traps.

## 8. Verification

- `organisations/tests/test_home_reset_panel.py` (new, 5 tests): proves
  the Home panel is visible when all three gates hold, absent when the
  flag is disabled, absent for a non-fixture organisation, visible
  regardless of package tier (including Paused), and that its action is
  a plain link to the existing confirmation page, never a `<form>` of its
  own.
- Full `organisations` + `security_baseline` suite: 415 passed, 0 failed
  (run inside the disposable `m008ewi1design` stack, `DJANGO_ENV=test` to
  match CI rather than the stack's own development-mode `.env`).
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes
  detected — this Work Order needed no migration.
- `gitleaks protect --staged`: no leaks found, against exactly the files
  this Work Order's commits contain (the disposable stack's own `.env`,
  which does carry a locally-generated dev secret key, is gitignored and
  was never staged).

## 9. Complete changed/new file list

New:
- `.claude/skills/infosecurs-ui-design/SKILL.md`
- `docs/evidence/M008E-CURRENT-UX-REVIEW.md`
- `docs/evidence/M008E-DESIGN-DIRECTION.md` (this file)
- `docs/evidence/m008e-screenshots/before/*.png` (27 files, 9 pages × 3
  widths, plus one extra viewport-only sanity shot — see the review
  document's capture-method caveat)
- `docs/evidence/m008e-screenshots/after/*.png` (27 files, same 9 pages ×
  3 widths, captured post-change — the Work Order required after-shots
  for the three redesigned surfaces; all nine were captured for a
  complete record and to confirm the shared-CSS refresh did not break the
  six pages this Work Order did not otherwise touch)
- `organisations/tests/test_home_reset_panel.py`
- `scripts/_m008e_screenshot_capture.py` (evidence-generation tooling,
  not product code — see its own module docstring)

Changed:
- `organisations/views.py` — `_customer_zero_reset_enabled_for` helper
  extracted; `organisation_detail` now computes and passes
  `customer_zero_reset_enabled` in both its Paused and non-Paused render
  branches; `organisation_hub` now calls the shared helper instead of
  repeating the same expression.
- `organisations/templates/organisations/detail.html` — new DEV panel
  block (PID §E2 exact copy), gated on `customer_zero_reset_enabled`.
- `organisations/templates/organisations/foundations.html` — stage tiles
  moved onto the new `.stage-tile` class; completion summary gained a
  decorative `.progress` bar; the one inline `style="..."` attribute on
  this page replaced with `.section-header`.
- `organisations/templates/organisations/organisation_hub.html` — dev
  tools card restyled onto `.dev-panel`/`.button--destructive`.
- `security_baseline/templates/security_baseline/foundations_question.html`
  — local `.stage4-progress*`/`.stage4-option*`/`.stage4-explainer`
  classes replaced with the new shared `.progress`/`.option-group`/
  `.option-card`/`.alert` components; one inline `style="..."` attribute
  on the bare fieldset replaced with `.fieldset--bare`. Only the
  question-category eyebrow/"why we ask" styling remains page-local.
- `static/organisations/css/app.css` — token values refreshed (palette,
  typography scale, new `--radius-lg`/`--color-neutral-*`/
  `--color-destructive-*`/`--color-surface-sunken` tokens); new shared
  components (`.button--destructive`, `.dev-panel`, `.progress`,
  `.option-group`/`.option-card`, `.alert`, `.stage-tile`,
  `.section-header`, `.fieldset--bare`); existing panel/card classes
  (`.summary-card`, `.form-card`, `.auth-card`, `.card-list__link`,
  `.empty-state`, `.form-section`, `.metric-card`, `.guided-cta`,
  `.paused-state`, `.needs-attention`, `.foundations-summary`,
  `.foundations-row`) moved onto the new `--radius-lg` panel radius; no
  existing custom-property *name* removed or renamed.

Unchanged (confirmed): `requirements.txt`, `requirements.in`,
`requirements-dev.txt`, `requirements-dev.in`, and every other dependency
manifest this repository has.
