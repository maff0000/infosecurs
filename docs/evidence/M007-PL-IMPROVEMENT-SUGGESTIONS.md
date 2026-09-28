# M007 — PL Improvement Suggestions

**Authorising commit:** `fb5be593131fde51d4fc2aafce268f64a5816850` (the
exact frozen release candidate SHA).
**Mandatory per PID §42**, filed regardless of M007's final outcome.
Separated into **A. Defects** (anything that should have blocked
PRODUCT_GREEN — none found by the PL; see below) and **B. Improvements**
(future ideas that do not invalidate M007's own correctness).

---

## A. Defects

**None identified by the PL that were not already caught and resolved
within WI1-WI6 itself.** Every genuine product-source bug found during
delivery (the WI2 tier-blind Overview links retired by WI5's rewrite; the
WI6 `shell.js` overlay-click focus-return gap) was either fixed in-flow or
explicitly, durably documented as an accepted residual finding (a strict
`xfail`, not a silent gap) before this report was written. See the fresh
Auditor's own independent verdict (`docs/evidence/M007-AUDIT-0001.md`) for
whether it found anything this list missed — that document, not this one,
is authoritative on whether a Defect exists that should block closure.

---

## B. Improvements

Each entry: Category · Suggestion · Evidence/observation · Why it would
help · Security/product impact · Effort (S/M/L) · Timing (Now/Next/Later)
· Requires Central Architecture decision (Yes/No).

### 1. Dashboard / UX

**B1. Foundations page-local badge colour CSS should move to a shared
status-primitive if the pattern expands.**
- Evidence: `organisations/templates/organisations/foundations.html`
  defines its own `.badge--yes`/`.badge--partial`/`.badge--no`/
  `.badge--unknown`/`.badge--not_applicable`/`.badge--complete`/
  `.badge--incomplete` colour variants locally, following the existing,
  established M006 convention (`.badge`'s shared geometry lives in
  `app.css`; colour variants stay page-local) — correct for M007's own
  scope, but this is now the *third* page with its own local badge-colour
  block (Overview originally, then Foundations).
- Why it would help: if a fourth or fifth page needs the same state-chip
  vocabulary, three-plus independently-maintained colour blocks risk
  silent drift (one page's "Partial" colour subtly diverging from
  another's).
- Impact: cosmetic only, no security/correctness implication.
- Effort: S. Timing: Later (only once a third+ genuine need appears —
  do not extract a shared primitive speculatively for a pattern used
  twice).
- Requires Central Architecture decision: No.

**B2. Foundations workspace has no grouping/filtering by area.**
- Evidence: `organisation_foundations` renders all 18 requirement rows as
  one flat list, ordered by `display_order`.
- Why it would help: once Customer Assurance or a future module adds more
  Foundations-eligible items, a flat list of 25-30+ rows becomes harder to
  scan than the existing area labels (`baseline`/`profile`/`governance`/
  etc.) already present in the data would support if grouped visually.
- Impact: usability only.
- Effort: S-M. Timing: Next (worth doing once the item count grows past
  ~20-25, not urgent at 18).
- Requires Central Architecture decision: No (pure presentation, PID §2.3
  "function before form" already covers the constraint).

**B3 — biggest usability improvement available without new methodology:**
**surface the Needs Attention destination context inline on the
Foundations page too**, not only on Home. Today a customer visiting
Foundations directly (e.g. from a bookmark) sees the full 18-item list but
not the same prioritised "what needs attention first" framing Home gives
them. A small, additive summary line at the top of Foundations
(reusing `get_needs_attention()`'s own output — already available, no new
methodology) would close this gap cheaply.
- Effort: S. Timing: Next. Requires Central Architecture decision: No
  (consumes an existing service function, no new product surface).

### 2. Entitlements / packaging

**B4. `FoundationRequirement.code` is globally unique, not
`(code, methodology_version)`-scoped.**
- This is the item Central Architecture itself already flagged and
  explicitly deferred during the WI4 review. Recorded here for
  completeness, not re-argued: acceptable for M007/v1 (a single
  methodology version in production at a time); would need
  version-aware identity if multiple methodology generations are ever
  meant to coexist historically in the live database rather than being
  superseded outright.
- Effort: M (a real migration + resolver-registry change). Timing: Later
  (only once a genuine second methodology version is actually planned).
- Requires Central Architecture decision: **Yes** (this is a
  product/architecture call, not a PL implementation detail).

**B5. `organisations.views._product_area_url()` assumes the `ProductArea`
exists.**
- Also a Central-Architecture-flagged item from the WI5/WI6 review cycle.
  Currently safe (every code this helper is called with is a governed
  constant or a live `RequirementState.product_area_code` tied to a real
  FK), but a future misconfigured/inactive destination would raise an
  unhandled `ProductArea.DoesNotExist` rather than failing gracefully.
- Effort: S. Timing: Next (a small, low-risk hardening — worth doing
  before this helper is reused by a future WI in a context where the
  assumption might not hold as safely).
- Requires Central Architecture decision: No.

### 3. Session / authentication boundary

**B6. `entitlements.decorators.require_capability`'s deliberate second
membership-scoped query (WI3's own documented design) could be optimised
once the request-context boundary matures.**
- Central-Architecture-flagged item, recorded verbatim: WI3 duplicates the
  organisation-membership query for correctness (the decorator's own gate
  must be provably correct in isolation, without depending on the view
  body's own separate check running at all or in any particular order).
  A future, carefully-scoped optimisation (e.g. a request-scoped cache of
  the already-verified `Organisation` object, shared safely between the
  decorator and the view) could remove the redundant query once that
  sharing boundary is itself proven safe — not a WI7 candidate on its own,
  only worth doing if a real performance need appears.
- Effort: M. Timing: Later (performance-motivated only — no current
  evidence this query is a genuine bottleneck).
- Requires Central Architecture decision: **Yes** (touches the security-
  critical decorator's own correctness argument, not a PL call to make
  unilaterally).

### 4. Security hardening

**B7 — biggest security improvement available, not yet built:**
**the `organisations/overview.py` Overview "next action" links (WI2's own
flagged, accepted UX debt) still render regardless of package tier.**
Route enforcement (WI3) is the actual, mandatory security boundary and
already fully closes this — a Paused/Foundation session cannot actually
reach a gated capability by clicking one of these links, confirmed
repeatedly across WI3/WI5/WI6's own independent verification. This is
therefore **not a security defect** (Central Architecture's own WI5
ruling already confirmed this explicitly: "the links do not necessarily
need to disappear... route enforcement is the mandatory boundary"). It
remains worth closing for defence-in-depth/UX-honesty reasons: a
Paused-tier customer clicking a visible "Open security state" link and
hitting a 403 is a worse first impression than never showing the link at
all. WI5's own Engineer declined to fix this as out-of-scope, correctly.
- Effort: S (the same `has_capability` call the route guard already uses,
  applied once more inside `build_overview`'s own next-action-URL
  construction — no new entitlement decision path).
- Timing: Next.
- Requires Central Architecture decision: No (Central Architecture has
  already ruled on this exact question — this is a straightforward
  "implement the already-approved cosmetic improvement" item, not a new
  decision).

**B8. `static/organisations/js/shell.js`'s overlay-click focus-return gap
(WI6 finding, `xfail`, Low severity) still needs a correctly-diagnosed
fix.** Two plausible fixes were tried live against real Chromium and
ruled out (see `docs/evidence/M007-BROWSER-ACCEPTANCE.md`). Recommended
for a future frontend-focused pass with interactive DevTools access,
which neither the Engineer's nor the PL's own headless, scripted
Playwright session could substitute for.
- Effort: S once correctly diagnosed (currently unknown effort, since the
  root cause itself is not yet identified — could be a one-line fix or
  could reveal something structural about this browser's focus-on-click
  handling that needs a different pattern).
- Timing: Next.
- Requires Central Architecture decision: No (already explicitly accepted
  as a documented residual finding by the PL under the dual-path authority
  Central Architecture's own WI6 instructions granted).

### 5. Foundations methodology

**B9. PID §12.2's generic "not applicable = excluded" completion-
denominator hook is never exercised in v1.** No baseline `not_applicable`
answer is excluded from completion (it counts as *complete*, per §12.3's
own explicit list), and none of the 6 derived milestones can themselves be
structurally N/A today. Documented directly in `entitlements/metrics.py`'s
own docstring (WI4) so a future methodology extending the catalogue with a
genuinely-conditional item doesn't miss that this hook exists but is
currently dormant — recorded here too for visibility outside the source
comment.
- Effort: N/A (nothing to build now — this is a "remember this exists"
  note, not a work item).
- Timing: Later (only relevant once a genuinely conditional Foundations
  item is proposed).
- Requires Central Architecture decision: **Yes**, if/when it becomes
  relevant (defining what "not applicable" means for a derived milestone
  is a methodology call, not a PL implementation detail).

### 6. Metrics / scoring

**B10. No historical score trending exists (by design — PID's own
explicit non-goal for M007).** Recorded here only to make the boundary
explicit for whoever scopes a future module: Posture/Completion are
recomputed fresh on every call, nothing is stored, so "how has our posture
changed over the last quarter" is not answerable today without a new,
deliberately-scoped historical-snapshot mechanism — which PID §10.3 itself
anticipates ("M007 does not need historical score trending") without
building it.
- Effort: L (a genuinely new capability, not a small addition — would need
  its own PID).
- Timing: Later, and explicitly **not now** (see "what should NOT be
  built yet" below).
- Requires Central Architecture decision: **Yes.**

### 7. Customer Assurance

**B11. Customer Assurance (questionnaire) received zero changes in M007
beyond being correctly left alone.** No new finding — recorded as a
confirmation, not a gap: M007's own explicit non-goal list already named
this ("No XLSX/DOCX/PDF workflow yet... visible navigation name remains
Customer Assurance"), and the WI6 stale-assumption sweep confirmed nothing
in this area drifted or needs correction as a side effect of M007's other
changes.

### 8. Data / model architecture

**B12. `ProductArea`/`FoundationRequirement` are both small-integer
auto-increment primary keys (a deliberate, documented WI1 choice), while
`Organisation` uses UUIDs.** Correct and already justified in
`entitlements/models.py`'s own module docstring (governed product
metadata nothing external addresses by a guessable identifier, vs.
`Organisation`'s different, customer-facing threat model) — recorded here
only so a future engineer auditing "why are these inconsistent" finds the
answer was already deliberate, not an oversight.
- Effort: N/A. Timing: N/A. Requires Central Architecture decision: No
  (already decided, already documented).

### 9. Testing / audit

**B13 — biggest future engineering-cost reduction available: formalise
the "search for stale route/destination assumptions" sweep (WI6's own
Part D) as a standing pre-close checklist item for every future module,
not a one-off WI6 exercise.** Two genuine stale references were found this
way in M007 alone (a docstring in `entitlements/navigation.py`, and
`templates/base.html`'s now-fully-dead M006 nav block + its
`core.context_processors.active_nav` wiring). Both are cheap to find with
a deliberate grep-and-classify pass but easy to miss without one — WI5's
own Engineer independently flagged this exact class of risk before WI6
formalised it, which is itself evidence the pattern recurs.
- Effort: S (a documented checklist addition, not new tooling).
- Timing: Now (cheap, directly actionable, prevents future drift
  accumulating silently).
- Requires Central Architecture decision: No (a delivery-process
  improvement, not a product decision).

**B14. Two stale-reference findings from WI6's own sweep, not yet acted
on (flagged, not fixed, per that dispatch's own scope discipline):**
- `entitlements/navigation.py::_pick_current_area`'s docstring still
  describes the `home`/`foundations` destination collision as true
  "today" — WI5's own migration resolved it; the docstring is now stale
  (cosmetic, zero behavioural impact, the tie-break rule for that specific
  pair is simply unexercised now, not wrong).
- `templates/base.html`'s entire old M006 flat-nav block plus
  `core/context_processors.py`'s `active_nav`/`_NAV_SECTION_BY_NAMESPACE`
  wiring are now structurally unreachable dead code (confirmed: no
  template with `organisation` in its context still extends `base.html`).
  A future WI could delete this cleanly — not done here to keep WI6
  strictly a proof pass, not a refactor pass.
- Effort: S each. Timing: Next (both are small, safe, well-understood
  cleanups once someone is authorised to touch that code).
- Requires Central Architecture decision: No for the docstring fix; a
  brief **Yes** for the dead-code deletion only because it touches a
  shared file (`core/context_processors.py`) other modules may still
  reference indirectly — worth a one-line confirmation before deleting,
  not a full re-review.

### 10. Operations / deployment

**B15. Real-browser (Playwright/Chromium) capability is now established
(WI6) but is a per-container runtime install, not baked into any image.**
This is correct and deliberate (Central Architecture's own explicit
constraint), recorded here as an operational note: any NEW disposable dev
stack, CI runner, or future Auditor dispatch must run
`playwright install --with-deps chromium` itself before Playwright-gated
tests will genuinely run rather than skip — `docs/runbooks/
BROWSER-ACCEPTANCE-CAPABILITY.md` already documents this, but it's worth
flagging in this report too since it's a genuinely easy step to forget
when standing up a fresh environment (confirmed directly during WI6's own
fresh-clone proof — the very first run against a truly fresh container hit
exactly this gap before the documented step was followed).

### 11. Performance

**B16. No N+1 query issue found anywhere in M007's own new code** (the
metric service, navigation service, and Home/Foundations views were all
specifically reviewed for this during WI4/WI5's own PL verification — each
uses a small, bounded number of queries regardless of the 18-requirement/
16-ProductArea row counts). No performance work is recommended at this
time; recorded as a confirmation, not a gap.

### 12. Accessibility

**B17. The WI6 accessibility proof (skip-link, focus-visible, keyboard
reachability, heading structure, colour-not-sole-indicator) is real-browser
verified, but was not run through a dedicated automated accessibility
scanner (e.g. axe-core).** PID's own instruction explicitly said "no need
to introduce an accessibility testing framework unless useful" — the
manual/Playwright-mechanical approach taken satisfies that instruction as
written. Recorded as a possible future enhancement, not a current gap:
if the UI surface grows substantially in a future module, a lightweight
axe-core integration (a single, well-scoped dev dependency, same
runtime-only-install pattern already established for Playwright) could
catch a wider class of accessibility issue than the specific properties
WI6 manually checked.
- Effort: M. Timing: Later. Requires Central Architecture decision:
  **Yes** (a new dev dependency, even a small one, is worth an explicit
  go-ahead given this whole module's own careful "avoid unnecessary
  dependencies" discipline).

---

## Summary — the four explicitly-requested headline items

- **Biggest usability improvement available now:** B3 (surface Needs
  Attention context on the Foundations page itself, reusing the existing
  service — no new methodology, small effort).
- **Biggest future engineering-cost reduction:** B13 (formalise the
  stale-route-assumption sweep as a standing pre-close checklist item —
  already proven to catch real drift twice in this module alone).
- **Biggest security improvement:** B7 (close the Overview next-action
  links' tier-blindness for defence-in-depth/UX-honesty, even though
  route enforcement already makes this non-exploitable today).
- **What should NOT be built yet:** B10 (historical score
  trending/dashboards) and B4/B9 (any `(code, methodology_version)`
  identity redesign or conditional-completion-item methodology) — all
  three are explicitly out of M007's own scope, all three would need
  their own PID and Central Architecture authorisation before any
  implementation work starts, and none is blocking M007's own closure.
