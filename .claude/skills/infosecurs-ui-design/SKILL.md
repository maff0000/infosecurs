---
name: infosecurs-ui-design
description: Durable visual/UX design doctrine for the Infosecurs product (server-rendered Django, no SPA framework). Load this before touching any Infosecurs template or CSS — it is the product's own design language, not a generic styling checklist. Established under M008E (docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md), WO-M008E-WI1.
---

# Infosecurs UI Design Doctrine

This is durable design doctrine for the Infosecurs product, written once under a
governed Work Order (WO-M008E-WI1) so a future, context-free dispatch can pick up
visual/UX work without having to re-derive it from scratch. It encodes *why* the
product looks the way it does, not just a palette. Read this in full before
styling or restyling any Infosecurs page.

Infosecurs is server-rendered Django (no SPA framework, no React/Vue, no
Tailwind, no commercial component library — ADR-0001). Every rule below assumes
that architecture and must not be read as licence to introduce one of those
things; a genuine need for a new frontend dependency is a STOP-and-ask, not a
design decision.

## 1. Who this is for

The audience is an SME business owner or manager — typically the person
responsible for security almost by default, not by training. Typically 5-49
employees. They are **not** a security specialist, **not** a Django developer,
and have limited patience for software that makes them feel stupid or
out of their depth. They are often doing this between other jobs, on a laptop,
sometimes on a phone. Treat them as competent and busy, not naive.

## 2. The emotional outcome every screen must produce

Calm. Trustworthy. Capable. Clear. Professional. Reassuring — **without
pretending everything is fine.** Infosecurs tells an SME owner the truth about
their security posture, including uncomfortable truths (gaps, overdue reviews,
"not sure" answers that still count as unknowns). The design's job is to make
that truth easy to absorb and act on, never to soften it into noise, and never
to manufacture false alarm either. A security product that looks alarming or
"hacker-ish" undermines trust just as much as one that looks like it is hiding
something behind a cheerful dashboard.

## 3. What to avoid — explicitly, every time

- **Hacker/cyber aesthetics**: no matrix-style imagery, no terminal/monospace
  theming, no neon-on-black, no "SOC dashboard at 2am" vibe.
- **Excessive dashboards**: no dense grid of gauges/sparklines/widgets. This
  product deliberately shows a small number of plain, well-explained numbers,
  not a wall of data.
- **Generic Bootstrap visual language**: default Bootstrap blue, default
  Bootstrap card/button shapes, the unmistakable "this is a Bootstrap app"
  look.
- **Excessive rounded cards** — the "SaaS card kit" tell: every single piece of
  content chopped into identically-rounded, identically-shadowed boxes
  regardless of what it is or how important it is. Reserve strong visual
  weight (tint backgrounds, accent borders) for things that are genuinely
  more important; plain content gets a plain container.
- **Meaningless gradients** — no decorative gradient washes. A gradient must
  never appear purely as decoration.
- **Tiny, low-contrast text** — every piece of real content must clear WCAG
  2.2 AA contrast; muted/secondary text is still genuinely readable, not a
  decorative near-invisible grey.
- **Technical cyber jargon** — write for the audience in §1. "Multi-factor
  authentication," not "MFA posture vector." Explain *why* something matters
  in plain language (the product already does this well in places — e.g. the
  Stage 4 "Why we ask" copy — extend that voice, don't abandon it).
- **Visual clutter** — if a piece of UI doesn't help the user understand their
  security state or decide what to do next, it should not be there.
- **Icon overuse** — Infosecurs does not need an icon next to every label.
  Use icons/symbols only where they carry real information (e.g. a status
  dot), never as decoration filling empty space.
- **"AI-looking" generic SaaS design** — the specific, commonly-generated
  defaults to actively avoid: a warm cream background with a high-contrast
  serif display face; a near-black background with one bright acid accent;
  tracked-out ALL-CAPS eyebrow labels above every heading; meta text joined
  with middle dots; a "→" appended to every link/button; the same soft grey
  box-shadow under every card. None of these are specific to Infosecurs —
  that is exactly why they are wrong for it.

## 4. Interaction doctrine

- **One obvious primary action per screen.** A user should never have to
  scan a page wondering what they're supposed to do next. Home's single
  "Continue Security Foundations" CTA is the model: visually the strongest
  element on the page, everything else secondary to it.
- **Strong headings.** Every page states what it is, in plain language, in
  an `<h1>`, immediately.
- **Concise explanatory copy.** Say what the user needs to know and stop.
  No marketing voice, no filler.
- **Visible progress.** Where a user is partway through something
  structured (Stage 4 of 6, N of 18 Foundations items), show it plainly —
  a short line of text plus, where it adds real clarity, a simple linear
  progress indicator. Never a decorative gauge/ring/chart standing in for a
  plain number where a plain number is the actual product decision (see
  Home's own metric cards, which are deliberately "a plain percentage and
  text, no chart/gauge/icon" — a prior, binding product decision; do not
  silently reverse it while doing visual work elsewhere).
- **Substantial, clear option controls.** Where a user chooses between a
  small number of named options (Yes / Partially / No / Not sure / Not
  applicable), each option gets a real, comfortably-sized clickable
  area — not a cramped radio button with tiny adjacent text.
- **Unmistakable selected state.** A selected option must be visually
  obvious at a glance — border + tint + (where feasible) a filled control,
  never a subtle colour shift alone.
- **"Not sure" is a legitimate, first-class answer**, not a disabled/greyed
  "lesser" option. UNKNOWN is real information Infosecurs genuinely needs
  (UNKNOWN != NO; PARTIAL != YES — never collapse these in presentation any
  more than the data model collapses them).
- **Clear gaps/warnings/actions.** When something needs attention, say so
  in plain language with a specific, concrete next step — never a vague
  "issue detected."
- **Restrained secondary information.** Metadata, counts, and disclaimers
  are present but visually quieter than the primary content — smaller,
  muted colour, never competing with the thing the user actually came to
  do.

## 5. Status-colour semantics — fixed, product-wide meaning

These meanings are load-bearing and must never be reassigned or diluted:

| Colour | Meaning |
|---|---|
| **Green** | Supported / satisfactory / completed, where "complete" is an accurate word for the state being shown. |
| **Amber** | Needs attention / requires confirmation. |
| **Red** | Gap / action required. |
| **Neutral (grey)** | Unknown / not applicable / purely informational — this is a real, distinct fourth state, not "green-ish" or "red-ish." |

**Colour is never the sole carrier of meaning.** Every status always carries a
real text label too (e.g. the existing answer badges render "Yes" / "Partially"
/ "No" / "Not sure" / "Not applicable," not an unlabelled coloured dot). This
is already how the product's `.badge` component works — preserve it when
extending or restyling status indicators.

A development-only affordance (see §7) is visually distinct from all four of
the above — it is not a severity signal and must not be confused with one.

## 6. Accessibility — WCAG 2.2 AA, non-negotiable

- Target WCAG 2.2 AA contrast for all real content text and meaningful UI
  components.
- Visible focus on every interactive element (`:focus-visible`, never
  `outline: none` without a real replacement indicator).
- Full keyboard operability — every action reachable and completable without
  a mouse, no keyboard traps (including the sidebar drawer at narrow
  viewports — opening it must not strand focus).
- Readable typography at every supported width — no text that requires
  zooming to read on a real device.
- Appropriate hit areas — interactive controls sized for an actual pointer/
  touch target, not a 12px text link doing a button's job.
- Responsive and tested at **375px / 768px / 1280px** at minimum. No
  horizontal overflow at any of these. This codebase's own established
  convention is a single CSS breakpoint (640px) rather than several —
  prefer extending that one breakpoint's rules over introducing a second
  breakpoint value; only add a second breakpoint if real, measured overflow
  or crowding is found at 768px that the 640px breakpoint cannot address,
  and document why.

## 7. Development-only affordances

Infosecurs has exactly one dev-only UI affordance today: the Customer Zero
reset control (M008A). It must look **unmistakably different** from ordinary
product content — a visitor should never wonder "is this a real feature?" —
achieved with a dashed border, a small solid "DEV" tag, and placement that
does not compete with the page's real primary action. It is never styled
using the green/amber/red/neutral status vocabulary above (a dev affordance
is not a security status).

This is a **styling convention only.** The actual gating of any dev-only
control is a server-side decision made in the view (reusing
`settings.CUSTOMER_ZERO_RESET_ENABLED` plus a `CustomerZeroFixture` check —
see `organisations/views.py`) and passed to the template as a plain boolean
context value. A template may only show or hide markup based on that value —
it must never re-derive, approximate, or duplicate the gating logic itself.

## 8. Design tokens

Infosecurs uses no external fonts or CDN assets (ADR-0001) — the system font
stack (`-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) is
deliberate, not a placeholder waiting for a "real" typeface. Visual
distinctiveness comes from colour, type scale/weight, spacing and layout
discipline, not from importing a display face.

All tokens live in `static/organisations/css/app.css`'s `:root` block.
Current custom-property names (`--color-*`, `--space-*`, `--radius*`,
`--focus-ring`) are the stable contract every template's local `<style>`
block and every shared component class is written against — when evolving
the palette, change the *values*, not the names, so every page that already
reads these tokens (including pages outside whatever surfaces a given Work
Order is bounded to) picks up the refresh consistently. Renaming or removing
an existing token is a breaking change to every template that reads it, not
a styling choice — treat it with the same caution as a schema migration.

Typography scale: `h1` 1.75rem/700 (page title, one per page), `h2` 1.25rem/
600 (section heading), `h3` 1.05rem/600, body 1rem/1.5-1.55 line-height,
meta/secondary text ~0.8125rem. Avoid introducing new uppercase "eyebrow"
labels beyond the small number already load-bearing in the product (e.g. the
organisation-context label, the Stage 4 category label) — an eyebrow above
every heading is a generic-AI tell (§3), not a real Infosecurs convention.

Spacing scale: `--space-1` (4px) through `--space-5` (40px), used
exclusively — no ad-hoc pixel values in new CSS.

Radius: a small radius for controls/chips/inputs and a larger radius for
panels/cards is a deliberate two-step scale, not a single radius applied to
everything (see §3's "excessive rounded cards" warning) — check
`static/organisations/css/app.css` for the current `--radius`/`--radius-lg`
values before introducing a third.

## 9. Component vocabulary

Prefer these existing shared classes (and their established variants) over
new one-off selectors; extend them rather than duplicating their geometry in
a page-local `<style>` block. Page-local `<style>` blocks remain acceptable,
per this codebase's own established convention, **only** for a page's own
colour-variant rules on top of a shared geometry class (e.g. Foundations'
`.badge--yes`/`.badge--partial`/etc. — the shared `.badge` class owns size/
shape/wrap, the page owns its own colour mapping) — never for layout/spacing
that could reasonably be shared.

Page/layout: `.app-main` / `.shell-main`, `.page-header`,
`.page-header__subtitle`, `.shell-sidebar` / `.shell-nav`.
Cards/panels: `.summary-card`, `.form-card`, `.metric-card`, `.foundations-row`.
Emphasis panels (primary CTA, dev tools): accent-tinted or dashed container,
never the same plain-card treatment as ordinary content.
Status: `.badge` (+ page-local colour variant), `.message` (+ `--success`/
`--error`), `.needs-attention`.
Progress: `.progress` / `.progress__track` / `.progress__fill` (added
WO-M008E-WI1) — a plain, thin linear indicator; never a gauge/ring/chart.
Forms/options: `.field`, `.input`/`.select`/`.textarea`, `.option-group` /
`.option-card` (added WO-M008E-WI1, generalised from the former
Stage-4-local `.stage4-option`).
Buttons: `.button--primary` (the one primary action), `.button--secondary`
(everything else that is still a real action), `.button--destructive`
(added WO-M008E-WI1 — any action that permanently deletes/destroys data;
currently only the Customer Zero reset action uses it).
Empty states: `.empty-state`.

## 10. Provenance

Written under WO-M008E-WI1 (parent PID: `docs/pids/M008E-PRODUCT-UX-VISUAL-HARDENING.md`),
the first governed Work Order to apply this doctrine, to exactly three
representative surfaces (Home, Foundations/Stage 4, Company/Organisation
hub) as a design checkpoint. See `docs/evidence/M008E-DESIGN-DIRECTION.md`
for that specific Work Order's own rationale and changed-file list. This
file is the durable doctrine that survives past that one Work Order — keep
it current as the design system evolves, rather than letting doctrine drift
back into individual Work Order evidence documents.
