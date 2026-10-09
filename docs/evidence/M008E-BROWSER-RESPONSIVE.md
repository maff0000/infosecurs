# M008E-WI2 — PR #99 Independent Audit: Browser/Responsive Evidence

**Audited head SHA:** `b9e7b70337c17a6fbaa414d8a5924efe3727c7d9`
**Base SHA:** `4631389d82697b1c2c222254756b4c900fecf395`
**Auditor:** fresh Independent Audit agent (never the Implementer), dell-debian, 2026-10-09
**PR:** https://github.com/maff0000/infosecurs/pull/99

## 1. Disposable stack and Chromium launch proof

- Isolated worktree: `git -C /srv/infosecurs worktree add /srv/openclaw/worktrees/audit/pr-99 b9e7b70337c17a6fbaa414d8a5924efe3727c7d9` (detached HEAD at `b9e7b70`). `git merge-base --is-ancestor 4631389d... HEAD` succeeded; both SHAs resolve as real commits.
- Disposable stack: project name `m008eauditpr99`, ports `WEB_HOST_PORT=8893` / `POSTGRES_HOST_PORT=15493` (distinct from the only other running stack touching this repo, `infosecurs-relocation-web-1`/`-db-1` on 8884/15432 — confirmed via `docker ps` before starting).
- Built via `docker compose -p m008eauditpr99 build web` (no Dockerfile changes — cached layers from the existing image), `up -d`, `python manage.py check` clean, `create_customer_zero` run.
- Chromium installed **at runtime only**, per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`: `docker compose -p m008eauditpr99 exec web playwright install --with-deps chromium` (downloaded Chrome for Testing 153.0.8010.12 successfully).
- **Explicit launch+page-load proof**, run before trusting any other result:
  ```
  STATUS 200
  TITLE Log in — Infosecurs
  LEN 3420
  CHROMIUM_LAUNCH_AND_PAGE_LOAD: CONFIRMED
  ```
  (`p.chromium.launch()` → `new_page()` → `page.goto('http://127.0.0.1:8000/accounts/login/')` against the real running stack.)
- Data seeded for a realistic novice journey using the Implementer's own disposable, ORM-only seed scripts (`scripts/_m008e_wi2_incr2_seed.py`, `_incr3_seed.py`, `_incr4_seed.py` — all idempotent, all ORM-direct, **none call `questionnaire:analyse`**, confirmed by reading each script before running).

## 2. Real-browser 1280 / 768 / 375 results — every changed surface, plus the full authorised-surface list

Method: Playwright, real Chromium, authenticated as the Customer Zero fixture user, `document.documentElement.scrollWidth` vs `clientWidth` measured at each width after `networkidle` + a 100ms settle. `ok` means `scrollWidth <= clientWidth` (no horizontal overflow).

| Surface | URL | 1280px | 768px | 375px | HTTP |
|---|---|---|---|---|---|
| Home / Company hub | `/organisations/<id>/` | OK | OK | OK | 200 |
| Organisations list | `/organisations/` | OK | OK | OK | 200 |
| Foundations workspace | `/organisations/<id>/foundations/` | OK | OK | OK | 200 |
| Stage 1 (Business) | `/organisations/<id>/foundations/stage-1-business/` | OK | OK | OK | 200 |
| Stage 2 (People & Workplaces) | `.../stage-2-people-workplaces/` | OK | OK | OK | 200 |
| Stage 3 (Technology & Data) | `.../stage-3-technology-data/` | OK | OK | OK | 200 |
| Stage 4 (a representative question) | `/organisations/<id>/baseline/questions/` | OK | OK | OK | 200 |
| Risks & Actions (Foundations) | `/organisations/<id>/risks/foundations/` | OK | OK | OK | 200 |
| Security Policy — detail | `/organisations/<id>/policy/` | OK | OK | OK | 200 |
| Security Policy — version detail | `.../policy/versions/<id>/` | OK | OK | OK | 200 |
| Security Policy — approve (implementation-status table) | `.../policy/versions/<id>/approve/direct/` | OK | OK | OK | 200 |
| Security State — list | `/organisations/<id>/security-state/` | OK | OK | OK | 200 |
| Security State — detail | `.../security-state/<control_key>/` | OK | OK | OK | 200 |
| Assets (Key Assets) — list | `/organisations/<id>/assets/` | OK | OK | OK | 200 |
| Assets — detail | `.../assets/<id>/` | OK | OK | OK | 200 |
| Risks — list | `/organisations/<id>/risks/` | OK | OK | OK | 200 |
| Risks — detail | `.../risks/<id>/` | OK | OK | OK | 200 |
| Evidence — list | `/organisations/<id>/evidence/` | OK | OK | OK | 200 |
| Evidence — detail | `.../evidence/<id>/` | OK | OK | OK | 200 |
| Evidence — upload | `.../evidence/upload/` | OK | OK | OK | 200 |
| Evidence — add external reference | `.../evidence/add-reference/` | OK | OK | OK | 200 |
| Remediation — list | `/organisations/<id>/actions/` | OK | OK | OK | 200 |
| Remediation — detail | `.../actions/<id>/` | OK | OK | OK | 200 |
| Profile | `/organisations/<id>/profile/` | OK | OK | OK | 200 |
| Governance — role assignments | `/organisations/<id>/governance/roles/` | OK | OK | OK | 200 |
| Workplace — list | `/organisations/<id>/workplace/` | OK | OK | OK | 200 |
| Activity — list | `/organisations/<id>/activity/` | OK | OK | OK | 200 |
| Customer Assurance (Questionnaire) — list | `/organisations/<id>/questionnaire/` | OK | OK | OK | 200 |
| Customer Assurance — response detail (accepted/SUPPORTED) | `.../questionnaire/responses/<id>/` | OK | OK | OK | 200 |
| Customer Assurance — response detail (draft/superseded) | `.../questionnaire/responses/<id>/` | OK | OK | OK | 200 |
| Customer Zero reset — confirmation screen | `/organisations/<id>/dev-tools/reset/` | OK | OK | OK | 200 |
| Login | `/accounts/login/` | OK | OK | OK | 200 |

**Result: 31 surfaces × 3 widths = 93/93 checks pass, zero horizontal overflow anywhere.** Raw scrollWidth/clientWidth pairs were identical (e.g. `375 == 375`, `768 == 768`, `1280 == 1280`) on every single measurement — no near-misses.

## 3. Permanent regression class 1 — 375px `.progress` / long-label overflow

Specifically re-verified beyond the generic table above:

- Stage 1/2/3's new `.progress`/`.progress__label` usage (this PR's own diff — previously a plain `.stage-progress` text line) at 375px: no overflow. `static/organisations/css/app.css`'s `.progress` rule still carries `flex-wrap: wrap` and `.progress__label { flex: 1 1 auto; min-width: 0; }` — the exact WI1 fix — **unmodified by this PR's diff** (confirmed: the WI2 diff to `app.css` only adds `.empty-state--left` and the `.table`/`.table-wrap` component; it does not touch the `.progress` block at all).
- Policy approve/version-detail's new `.table-wrap` (wraps the "Implementation status" table, previously fully unstyled with no corresponding CSS rule at all) at 375px: table scrolls within its own wrapper if ever needed; page itself measured `scrollWidth == clientWidth == 375`.
- Badge-bearing surfaces (Governance roles' new `.badge--assigned`/`--unassigned`, Questionnaire response detail's corrected `.badge--draft`/`--superseded`/`--outcome-CONFIRM`/`--outcome-NOT_APPLICABLE`) at 375px: no overflow; badges inherit the shared `.badge` geometry (`max-width: 100%; white-space: normal; overflow-wrap: anywhere;`), unchanged by this PR.
- Workplace list's new `.workplace-card__title-text` (customer-controlled free-text workplace name) at 375px: no overflow — this increment added its own `min-width: 0; overflow-wrap: anywhere;` rule, the same established defect-class fix already used by `.asset-card__title-text` etc.

## 4. Permanent regression class 2 — focus suppression (box-shadow/outline overwriting `:focus-visible`)

Computed `getComputedStyle(el).boxShadow` measured before vs. after `.focus()`, real Chromium, same method the WI1 independent audit used to originally catch the PR #97 regression:

| Element | Before focus | After focus | Changed? |
|---|---|---|---|
| Sidebar current-page nav link (`.shell-nav__link[aria-current="page"]`) | `rgb(15, 106, 92) 3px 0px 0px 0px inset` | `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px, rgb(15, 106, 92) 3px 0px 0px 0px inset` | **YES** — ring layers on top of the accent bar, exactly the WI1 fix's intended behaviour |
| A non-current sidebar nav link (control) | `none` | `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px` | YES |
| Reset-confirm page's destructive submit button (`button.button--destructive`, new in this PR — was `.button--primary`) | `none` | `rgba(15, 106, 92, 0.35) 0px 0px 0px 3px` | YES |

All three show a genuinely different computed `box-shadow`, not merely "a style exists somewhere" — the WI1-era regression (accent-bar rule silently winning over `:focus-visible` with zero visual change on focus) does **not** recur anywhere this PR touches. This PR's diff does not modify `.shell-nav__link[aria-current="page"]:focus-visible` (the WI1 fix rule) at all, and no new per-page CSS rule in this PR sets `box-shadow`/`outline` on any active/selected/current/destructive state without the sitewide focus-visible ring still able to apply (verified directly above for the one new destructive-button case, which is the only new state-styled interactive element this PR adds).

## 5. Keyboard/novice-journey browser proof

Full authenticated journey run for real in the disposable stack, Customer Zero fixture user: login → Home → Foundations → Stage 1 → Stage 2 → Stage 3 → Stage 4 → Risks & Actions → Security Policy (detail/version/approve) → Security State (list/detail) → Assets (list/detail) → Risks (list/detail) → Evidence (list/detail/upload/add-reference) → Remediation (list/detail) → Company/Profile → Governance → Workplace → Activity → Customer Assurance (list + two response states) → Customer Zero reset control located via Home's `.dev-panel` → reset confirmation page. Every step returned HTTP 200 and zero overflow at all three widths (see §2 table, which is this exact journey).

- **Reset control located without being told where it lives**: Home's rendered HTML contains a `.dev-panel` block (`<span class="dev-panel__tag">Dev</span><h2>DEV · Customer Zero</h2>...`) with a single `<a class="button button--destructive" href="/organisations/<id>/dev-tools/reset/">Reset test organisation</a>` — a plain link, **not** a `<form>` of its own, to the canonical confirmation route. Confirmed by direct HTML inspection of the real rendered page, not by reading the template.
- **Gating independently re-proven at runtime** (not merely trusted from the unchanged `views.py`): with `override_settings(CUSTOMER_ZERO_RESET_ENABLED=False)`, the same authenticated request to Home shows **no** `dev-panel` in the response; with it `True` again, it reappears. This exercises the real view-level gate end-to-end, not just a template flag.
- The reset action was **not executed** during this audit (no defect required proving it).

## 6. Novice-journey screenshots

No new screenshot files were captured by this Independent Audit (time/scope were spent on direct, scriptable, more rigorous measurement — real `scrollWidth`/`clientWidth` pairs and real computed-style focus comparisons, rather than visual captures a human would then have to eyeball). The four increments' own 266 committed before/after PNGs under `docs/evidence/m008e-wi2-screenshots/increment-{1,2,3,4}/{before,after}/` were spot-checked for plausibility directly on disk (`ls -la`), not merely trusted from narrative: `stage1-business__1280.png` is 101255 bytes before / 109753 bytes after (a real, non-trivial visual change, consistent with Stage 1's progress-bar/subtitle rework), while `governance-edit-my-details__768.png` is byte-identical (50694/50694) before and after — consistent with that one page genuinely being untouched by Increment 3's diff (confirmed separately: `governance/templates/governance/role_assignments.html` is the only file Increment 3 touched in the `governance` app; `edit_my_details.html` is not in the PR diff at all). These were not independently re-rendered pixel-for-pixel by this audit. If the Delivery Controller wants independently-recaptured screenshots as a durable artefact, that is a reasonable follow-up, not a blocking gap — every claim in this document is instead backed by a live, reproducible measurement against the real running application.
