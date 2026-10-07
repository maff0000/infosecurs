# M008E-WI1 — Current-State UX Review (Phase 1)

**PID:** `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md` §E4 Phase 1.
**Work Order:** `docs/work-orders/WO-M008E-WI1.md`.
**Method:** Real Chromium (Playwright, runtime-installed per
`docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`) against a disposable
`m008ewi1design` Docker Compose stack (`WEB_HOST_PORT=19920`,
`POSTGRES_HOST_PORT=19921`, both loopback-only), running this branch's
code at the pre-change base commit, logged in as the real Customer Zero
fixture user (`create_customer_zero`). The live `infosecurs-relocation`
dev stack (port 8884) was never touched. **No product code was changed to
produce this document** — it is a review of the state at base SHA
`186a3e6de7d5aee16840de9e3ddb10b81b002487`.

Screenshots: `docs/evidence/m008e-screenshots/before/`, one file per
`<page>__<width>.png` at 1280 / 768 / 375, for all nine required surfaces:
Home, Foundations workspace, Stage 1, a representative Stage 4 question,
Risks & Actions, Security Policy, Company/Organisation hub, Customer
Assurance, the reset confirmation page.

**Capture-method caveat (read before the Stage 4 / 375px screenshot):**
`04-stage4-question__375.png` is a `full_page=True` capture, and Chromium's
full-page screenshot mode resizes the viewport to the full document height
before shooting — which resolves `position: sticky` elements (this page's
bottom action bar, `.form-actions--sticky`) against that *enlarged*
viewport rather than the real one, making the sticky bar appear to float
above the question options instead of pinned below them. This is a known
Playwright/Chromium full-page-screenshot artifact, not a real rendering
bug — confirmed by taking a second, ordinary (viewport-only, not
full-page) 375px screenshot of the same page,
`docs/evidence/m008e-screenshots/before/stage4-viewport-only-375.png`,
which shows the normal, correct in-flow layout (options below the
intro copy, actions bar below that). Noted explicitly so a future reader
of the full-page screenshot doesn't mistake a capture artifact for a
defect.

---

## 1. Overall impression

The product is functionally solid and already has real accessibility care
behind it (visible focus, keyboard-operable forms, `overflow-wrap`
discipline, a `.badge` component that never relies on colour alone) — but
visually it reads as **internal Django tooling**, not something an SME
would pay a subscription for. Every one of the PID's own named symptoms
(§E1) is reproducible:

- Generic corporate blue (`#185ea8`) + cold grey canvas (`#f4f6f8`) is a
  stock "admin panel" palette, not a distinctive product identity.
- Every card — metric card, summary card, foundations row, dev-tools
  card — uses the **same** border, the **same** radius, the **same**
  white background. There is no visual language for "this is more
  important than that."
- Buttons have exactly two visual weights (filled blue / outlined grey)
  used **identically** regardless of whether the action is routine
  navigation ("Open profile"), the page's one primary action ("Continue
  Foundations"), or something that permanently destroys data ("Reset
  test organisation"). A destructive action currently looks exactly like
  "View security state."
- Nothing in the UI visually distinguishes a development-only affordance
  from ordinary product content (see §4 below).

## 2. Visual hierarchy

- **Home** (`01-home__1280.png`): the "Continue Security Foundations" CTA
  is meant to be the page's one obvious primary action (confirmed by the
  template's own code comment, M008C §5), but visually it is barely
  stronger than the two metric cards directly beneath it — same border
  weight, same corner radius, only a faint tint and a triangle glyph
  differentiate it. A first-time user scanning the page has no strong
  signal for "start here."
- **Foundations workspace** (`02-foundations__1280.png`): the "Your guided
  journey" stage tiles, the completion summary, and all 18 foundations
  rows are visually flat and equal-weight. The 18-row list in particular
  reads as a plain database dump — identical white rows, identical "Open"
  buttons, no grouping by area, no way to tell at a glance which of the 17
  incomplete items matter most (the existing `security_weight` data,
  shown only as small muted text "Security importance: 5" on baseline
  rows, is the one place real prioritisation information exists and it is
  the least visually prominent thing on the row).
- **Company/Organisation hub** (`07-company-hub__1280.png`): Profile,
  Governance roles, Workplace, and the dev-only reset tool are four
  **identical** cards in a single column, differing only in heading text.
  Nothing marks the fourth one as fundamentally different in kind from
  the other three.

## 3. Spacing, density, typography

- Only two heading sizes are meaningfully in play (`h1` 1.6rem, `h2`
  1.2rem) and every page uses them for everything — there is no secondary
  scale step between "page title" and "every other heading," so a stage
  tile heading, a metric card title, and a foundations-row area label all
  compete at a similar size/weight.
- Line length is reasonable on 1280px but several supporting paragraphs
  (metric card copy, the Stage 4 intro) run close to the full 376px
  content column with no `max-width` of their own — comfortable today
  only because the overall column is already narrow (`.app-main` is
  720px), not because type measure was a deliberate choice.
- Foundations' 18-row list has very little breathing room between rows at
  1280px relative to how much is packed into each row (title + badge +
  meta line + action button all in one dense strip) — it reads as a
  settings/admin list, not a guided "here is your programme" surface.
- No uppercase "eyebrow" label pattern exists above Infosecurs page `h1`s
  today (good — nothing to walk back), but Stage 4's own `.stage4-eyebrow`
  ("STAFF SIGN-IN PROTECTION") and the organisation-context label
  ("ORGANISATION") are the only two eyebrow-style labels in the whole
  product; they are genuinely structural (a real question-category name,
  a real "what is this value" label) rather than decoration.

## 4. Development-only reset affordance — the named PID complaint

Confirmed directly in the screenshots: the Customer Zero reset control
(`07-company-hub__1280.png`, "DEV · Test tools" card) is visually
**identical** to the three ordinary product cards above it — same white
background, same border, same radius, same button style. The only signal
that it is different in kind is its own heading text. This matches PID
§E1/§E2's own stated problem exactly ("insufficiently visible... too
difficult to find during testing") — it is not that the control is in a
bad location so much as that, once there, nothing about its *appearance*
marks it as categorically different from "Open profile."

The reset confirmation page itself (`09-reset-confirm__1280.png`) is
plain prose in an ordinary `.summary-card` — the destructive consequences
are explained clearly in the copy ("will **permanently remove**...",
"**This action cannot be undone**"), but the visual presentation gives
that text no more weight than any other card on the site, and the actual
"Reset test organisation" submit button is styled identically to every
other primary button in the product.

## 5. Action hierarchy / button clarity

Only two button variants exist today, `.button--primary` (filled) and
`.button--secondary` (outlined) — there is no third, visually distinct
treatment for a destructive action. Concretely:

- Home's "View security state" / "Continue Foundations" are both rendered
  `.button--secondary` — identical weight to every other secondary link
  in the product.
- The Foundations workspace's "Open Stage 1/2/3" stage tiles use
  `.button--primary` identically to "Save and continue" on a genuine form
  submission and to the actual "Reset test organisation" button on the
  confirmation page — three actions with very different stakes (navigate,
  save real data, permanently delete data) are visually indistinguishable.

## 6. Mobile presentation (375px)

No horizontal overflow was found on any of the nine captured pages at
375px — the product's prior `overflow-wrap`/responsive work (noted in
`static/organisations/css/app.css`'s own extensive comments) holds up.
Specific 375px observations:

- The sidebar correctly collapses to a hamburger-triggered drawer
  (`application_shell.html`/`shell.js`) — functional, but the drawer
  itself has had no visual design pass (plain white panel, no visual
  separation from content beyond a border).
- Foundations' 18-row list and the stage grid both stack correctly, but
  at 375px the page becomes a very long, low-information-density scroll —
  nothing is collapsed, grouped, or summarised for the narrow viewport,
  so a phone user scrolls through the same flat list a desktop user sees,
  just one column wide.
- Stage 4's option list already works reasonably well at 375px (full-width
  bordered rows, native radio inputs with adequate tap targets) — this is
  one of the stronger existing surfaces and a reasonable starting point
  for the new shared `.option-group`/`.option-card` component.
- See the capture-method caveat above regarding the Stage 4 full-page
  screenshot's sticky-bar artifact — the real, in-viewport behaviour
  (`stage4-viewport-only-375.png`) is correct.

## 7. Status clarity

- The `.badge` component (Foundations' Yes/Partially/No/Not sure/Not
  applicable + Complete/Needs completion variants) already satisfies
  "never colour-only" — every badge carries a real text label, not just a
  coloured dot. This is a genuine strength to preserve, not rebuild.
- However, the "Not sure" / "Unknown" state currently reuses the same
  flat grey as "Not applicable" (`.badge--unknown` and
  `.badge--not_applicable` both resolve to `var(--color-border)`
  background) — visually correct (both are the "neutral" bucket per PID
  §E3's four-colour semantics) but there is no shared, named "neutral"
  token in `app.css` today; it is two page-local rules that happen to
  reference the same border colour. Worth promoting to an explicit,
  intentional neutral token rather than an accidental reuse.
- Risks & Actions (`05-risks-actions__1280.png`) and Security Policy
  (`06-security-policy__1280.png`) were captured on a freshly-bootstrapped
  fixture with no data yet, so their real status-colour presentation
  (risk severity, policy truth-tags) could not be observed in this pass —
  noted as a gap in this specific review, not a product defect. Neither
  page is in WO-M008E-WI1's three-surface scope regardless.

## 8. Navigation / sidebar

- The sidebar's "current page" highlighting (`aria-current="page"` +
  `.shell-nav__link[aria-current="page"]` tint) does work correctly on
  every page, Home included — confirmed by sampling the actual pixel
  colour behind each nav link in `01-home__1280.png` (Home: `#e6eefb`,
  the exact tint colour; every other link: plain white) and cross-checked
  against `07-company-hub__1280.png` (Company: tinted; Home: plain white).
  An earlier draft of this review wrongly flagged Home as missing its
  active-state highlight entirely — that was a misreading of a real but
  very low-contrast pale-blue-on-white tint at reduced screenshot zoom,
  not an actual defect, and is corrected here rather than silently
  dropped. The real, narrower finding is contrast: at the *old* palette's
  `--color-primary-tint` (`#e6eefb` on white), the active-state signal is
  genuinely hard to see, which the new design's left accent bar (see
  `docs/evidence/M008E-DESIGN-DIRECTION.md`) directly strengthens without
  touching any navigation logic.
- The top-level nav groups ("Security," "Policies," "Company") render as
  plain bold text with no visual distinction from their own child links
  beyond font-weight/indentation — functional, but flat.

## 9. Accessibility / focus

- `:focus-visible` is implemented globally and was visually confirmed
  present (a visible box-shadow ring) during manual keyboard tabbing
  through Home, Foundations, and the Stage 4 question form, no keyboard
  traps found going into/out of the sidebar drawer.
- Chip/badge text and body copy contrast already clears WCAG AA by a wide
  margin on the current palette — the existing colour choices were already
  conservative; the new palette (see
  `docs/evidence/M008E-DESIGN-DIRECTION.md`) was checked against the same
  bar before adoption, not loosened.
- No ARIA/semantic defects were found in this pass beyond the
  already-known, already-fixed-in-code-comments items (e.g. the
  `.needs-attention__line` link-text discipline, which is already
  correct and mechanically tested).

## 10. Inconsistencies across pages

- Two different "progress" idioms exist with zero shared styling: Stage
  4's own thin `.stage4-progress__bar` (page-local `<style>` block) and
  the Foundations workspace's plain-text-only completion percentage (no
  bar at all). Same underlying concept (how much of a structured task is
  done), two different presentations, one of them not visual at all.
- Two different "DEV" visual conventions already exist in this
  repository, inconsistently: the real app currently has **none** (the
  reset card on Company hub is unstyled, §4 above) while
  `docs/design/prototype.html` (a pre-existing, uncommitted-to-product
  design exploration already in the repo) independently arrived at a
  dashed-amber-border + solid "DEV" tag convention. This review treats
  that prototype as a legitimate design precedent to build on (see the
  design-direction document), not as a path to follow verbatim (it also
  specifies Google Fonts, which ADR-0001 forbids for the real product).
- `organisations/templates/organisations/foundations.html` has one
  leftover inline `style="margin-bottom: var(--space-2);"` attribute on
  its "Your guided journey" `<h2>` — the only inline style found across
  the three in-scope templates, and a direct instance of the "avoid
  inline-style proliferation" pattern PID §E8 warns about.

## 11. Summary of what the checkpoint (Phase 2) addresses

Every item above that falls within WO-M008E-WI1's three-surface,
visual-only scope (Home, Foundations/Stage 4, Company hub) is addressed in
`docs/evidence/M008E-DESIGN-DIRECTION.md`, including the low-contrast
active-nav tint noted in §8. Items explicitly **not** addressed because
they are out of this WI's bounds: Risks & Actions / Security Policy /
Customer Assurance / the reset confirmation page's own visual design (all
explicitly deferred to the full-rollout gate per PID §E5/§E6), and
anything resembling a behavioural or workflow change.
