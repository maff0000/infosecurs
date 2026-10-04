# M008 — Final Re-verification Audit Supplement (Governance Recovery, Gaps A1/A2/A3)

**Work Order:** `docs/work-orders/WO-M008-GOV-RECOVERY-002.md`
**Amendment:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md`
**Architect review this supplement answers:** `docs/evidence/M008-ARCHITECT-REVIEW-PR94.md` (gaps A1, A2, A3)
**Preflight this supplement continues from:** `docs/evidence/M008-AUDIT-SUPPLEMENT-PREFLIGHT.md`
**Frozen product SHA (unchanged throughout):** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Reviewed PR #94 head (recovery branch base for this supplement):** `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`
**Worktree HEAD this Auditor started from:** `c29c71e22c0ed29c40b0ea8a97aa4fae1f23d085`
**Auditor:** independent Claude Code audit agent, freshly dispatched for this Work Order
**Date:** 2026-10-04
**Host:** `dell-debian` (`192.168.11.10`)
**Isolated working copy:** `/tmp/m008-audit-fresh/repo` (`git clone /srv/infosecurs`; `/srv/infosecurs` itself was never mutated)
**Disposable test stack:** Docker Compose project `m008auditsupp`, ports `127.0.0.1:19950` (web) / `127.0.0.1:19951` (db) — distinct from every other project already running on this host; environment `DJANGO_ENV=development`, `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` set for the whole stack's lifetime (not toggled per-scenario)

## Independence statement

I am a freshly dispatched Auditor with no memory of, and no access to, any prior audit's conclusions, chat transcript, or working notes on this product. I have **not** performed any prior M008 audit. I read exactly the four documents named in my Work Order, in order (`docs/evidence/M008-ARCHITECT-REVIEW-PR94.md`, `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md`, `docs/work-orders/WO-M008-GOV-RECOVERY-002.md`, `docs/evidence/M008-AUDIT-SUPPLEMENT-PREFLIGHT.md`), then the product's own repository and runbooks, and independently re-derived every finding below from my own commands' real output against my own disposable stack. Where this report references the prior audit's own account of the Stage 1 anomaly, it does so only because the Work Order requires closing that specific, named gap — the actual root-cause conclusion below was independently re-derived from my own live reproduction, not taken on trust.

## 0. Pre-audit integrity checks

### 0.1 Host safety

`docker ps` was run first. Confirmed running and **never touched**: `infosecurs-relocation-web-1`/`infosecurs-relocation-db-1` (the live dev stack, port 8884), `darwin-darwin_core-1`/`darwin-darwin_sql-1` (the unrelated DARWIN product, port 8000), and a pre-existing `m008wi6audit-web-1`/`m008wi6audit-db-1` pair (a stray stack from a prior audit — left completely untouched throughout). All work below used my own isolated clone and my own disposable Compose project `m008auditsupp` on fresh host ports (`19950`/`19951`), confirmed free before use.

### 0.2 Frozen-SHA / branch-head / product-path-drift re-check (independent, not assumed from the preflight)

```
$ git clone /srv/infosecurs /tmp/m008-audit-fresh/repo
$ cd /tmp/m008-audit-fresh/repo && git checkout c29c71e22c0ed29c40b0ea8a97aa4fae1f23d085
$ git ls-remote origin main
6393912bc4f7a98e5d167a465369bf2a8ef26c57	refs/heads/main
$ git diff --name-status 6393912bc4f7a98e5d167a465369bf2a8ef26c57 HEAD
A	docs/architecture/DELIVERY-GOVERNANCE.md
A	docs/evidence/M008-ARCHITECT-REVIEW-PR94.md
A	docs/evidence/M008-AUDIT-SUPPLEMENT-PREFLIGHT.md
A	docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md
A	docs/evidence/M008-GOVERNANCE-RECOVERY-PREFLIGHT.md
A	docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md
A	docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md
A	docs/work-orders/WO-M008-GOV-RECOVERY-001.md
A	docs/work-orders/WO-M008-GOV-RECOVERY-002.md
```

All 9 changed paths are under `docs/architecture/`, `docs/evidence/`, `docs/pids/`, or `docs/work-orders/` — pure governance/evidence documentation. **Zero product-path drift.** No existing file modified or deleted — every change is a brand-new addition. This matches the preflight's own independent conclusion; I re-derived it myself rather than trusting that document's account. No defect in the recovery process itself.

### 0.3 Disposable stack bring-up

```
$ cp .env.example .env   # filled with synthetic local-only values; INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true set from the start
$ docker compose -p m008auditsupp build web
$ docker compose -p m008auditsupp up -d
  → db: healthy; web: migrated cleanly (python manage.py migrate --noinput, all apps, no errors) then started
$ curl -s http://127.0.0.1:19950/healthz/
{"status": "ok", "database": true}
$ docker compose -p m008auditsupp exec web python manage.py create_customer_zero
Created Customer Zero user 'customerzero'.
Created Customer Zero organisation 'Infosecurs Limited'.
Linked Customer Zero user to organisation.
Customer Zero bootstrap complete.
```

### 0.4 Chromium — runtime-only install, per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`

```
$ docker compose -p m008auditsupp exec web playwright install --with-deps chromium
  → Chromium 153.0.8010.12 downloaded to /root/.cache/ms-playwright/chromium-1243 (exit 0)
$ docker compose -p m008auditsupp exec web python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); print('chromium launch ok'); b.close()"
chromium launch ok
```

Installed into the already-running `web` container's writable layer only (`exec`, not `run --rm`), never into the image — exactly as the runbook requires. This was not skipped or environmentally excused anywhere in this supplement; every S1/S2/S3 scenario below ran against this real, launched Chromium.

A second synthetic identity for S3 (`tenantb_auditor`) was created via `docker compose exec web python manage.py shell` (a bare Django `User` row only — no organisation, no fixture relationship), mirroring the preflight's own anticipated "tenantb_auditor" shape. Its organisation was then created entirely through the product's own self-service UI (see S3 below), not via this shell.

---

## S1 — True browser-only Customer Zero end-to-end cycle

**Script:** `/tmp/m008-audit-fresh/repo/.audit_scratch/s1.py` (disposable, not committed — see §"What was and wasn't committed" at the end of this report)
**Run:** `docker compose -p m008auditsupp exec web python /app/.audit_scratch/s1.py`
**Result: ALL 31 steps PASSED.** Full machine-readable log: `.audit_scratch/evidence/s1/s1_results.json` (on `dell-debian`, inside the disposable stack's bind-mounted working copy — not part of the committed repository).

Zero ORM writes, zero direct service calls, and zero direct HTTP POSTs outside Playwright browser automation were used anywhere in this script to populate customer state. The one place a non-UI read was used is explicitly read-only, after-the-fact DB inspection (via `manage.py shell`, SELECT-only), exactly as the Work Order allows, to independently confirm what the UI-driven actions actually persisted.

### Sequence executed (all through the rendered UI, real Chromium)

1. Login #1 (needed to reach the dev-tools reset screen at all).
2. **Initial reset** of Customer Zero via Company → "Reset test organisation" → typed `RESET` → submit. Result: forced to `/accounts/login/`.
3. Login #2 (the real pass).
4. **Stage 1** ("Your Business") — see the dedicated anomaly-investigation sub-section below.
5. **Stage 2** ("Your People & Workplaces") — workplace onboarding ("all remote" pattern, 1 person) via the real link-out/come-back flow, then the stage's own two inline fields (`people_with_system_access_count=1`, `has_remote_or_offsite_access=no`), submitted.
6. **Stage 3** ("Your Technology & Data") — every `<select>` on the form given a concrete, non-blank option, submitted.
7. **Stage 4** — entered via a real Foundations-workspace "Open" action link (not a remembered URL); all 12 security-control questions answered and saved one at a time through the guided one-question-per-screen flow, each followed by its real "Next →" link, ending on "Finish for now →" → Home.
8. **Risks & Actions** — reached via the Foundations workspace's own "Open Stage 5" tile.
9. **Policy** — "Generate policy draft" (deterministic) clicked on the Policy overview page; reviewed via "View full version".
10. **Approval** — "Approve this policy" → confirmation form → "Confirm direct approval" (Customer Zero's Account Holder is auto-assigned as Policy Authoriser by `governance.services.ensure_account_holder_person`, so this is a genuine direct-approval path, not external-recorded).
11. **PDF download** — a genuine Playwright `expect_download()` browser download event on the real "Download PDF" link.
12. **Final reset** of Customer Zero via the same UI path as step 2.
13. **Forced-fresh-login proof** — navigating directly to `/organisations/` afterward redirected straight to `/accounts/login/?next=/organisations/`.

### Independent DB confirmation (read-only, after the fact)

```
# After Stage 1 save (before further stages):
legal_trading_name: 'Infosecurs Limited (Audit Supplement)'
sector: retail_ecommerce
staff_count: 12

# After the final reset:
profile exists after final reset: False
policy versions after final reset: 0
baseline assessments after final reset: 0
workplaces after final reset: 0
risks after final reset: 0
```

### PDF download evidence

```json
{
  "suggested_filename": "Infosecurs Limited - Information Security Policy v1.pdf",
  "byte_size": 7520,
  "sha256": "d86a64e513ee833d2a3a9091039cfd638b90bd039586ff26422185de29d0f9cf",
  "starts_with_pdf_magic": true
}
```
Saved to `.audit_scratch/evidence/s1/downloaded_policy.pdf` on the disposable stack's bind mount. A real browser download event (`page.expect_download()`), not a direct fetch.

### The required Stage 1 save/redirect anomaly investigation — closed, with direct evidence

The prior audit's own account (per the Architect review and the preflight) described an unexplained symptom: after a keyboard Enter submit on Stage 1, the browser appeared to remain on the Stage 1 URL instead of redirecting to Stage 2. I drove Stage 1's real submit path deliberately, twice, to determine conclusively whether this is a genuine product defect or an automation artifact.

**Experiment 1 — reproduce the symptom on purpose.** Filled every Stage 1 field *except* the one required field (`legal_trading_name`), then pressed a genuine keyboard Enter from within a different, already-focused text field (`staff_count`).

- Result: the page **did** stay on the Stage 1 URL, and the rendered page showed a real, ordinary Django validation error:
  > "Those details could not be saved. Please check the errors below." / "This field is required." (on `legal_trading_name`)
- Screenshot: `.audit_scratch/evidence/s1/05_anomaly_experiment1_blank_required_field.png`.
- **Conclusion:** this is ordinary required-field server-side validation re-rendering the same URL with a 200 and an error — not a redirect failure.

**Experiment 2 — positive control.** Filled every field correctly, including `legal_trading_name`, then submitted via a genuine keyboard Enter press from within a text field (mirroring the prior audit's own interaction shape).

- Result: redirected cleanly to Stage 2 (`.../foundations/stage-2-people-workplaces/`), with the success message "Your Business details saved." visible, and the submitted values independently confirmed in the database (see above).
- Screenshot: `.audit_scratch/evidence/s1/06_anomaly_experiment2_correct_submit.png`.

**Conclusion: the Stage 1 save/redirect mechanism works correctly.** The prior audit's symptom is fully, directly explained by Experiment 1: an unfilled required field produces an ordinary same-page validation error, which an automated check that inspects only the URL (and not the page content) would misread as "did not redirect." This is **not a product defect**.

**A related finding, disclosed for full transparency (test-harness methodology, not a product issue):** my own first pass at this experiment produced a **false negative** — `page.url` read immediately after `page.wait_for_load_state("load")` raced against the real navigation and returned a stale value, making Experiment 2 initially look like it had also failed to redirect, even though the server-side save/redirect had, in fact, already succeeded (confirmed independently via the database read above, and via the screenshot showing the real Stage 2 page). I root-caused this as a `Locator`/`page.url` timing race specific to my own automation, not a product behaviour, switched to content-based waits (`page.wait_for_selector` on a landmark of the expected destination page) plus `networkidle`, and reproduced the correct, consistent result on every subsequent run. I disclose this because it is exactly the class of automation artifact the Work Order asks this Auditor to distinguish from a genuine defect — and distinguishing it required actually catching my own tooling getting it wrong first.

---

## S2 — Keyboard-only Stage 4

**Script:** `/tmp/m008-audit-fresh/repo/.audit_scratch/s2.py`
**Run:** `docker compose -p m008auditsupp exec web python /app/.audit_scratch/s2.py`
**Result: ALL 31 steps PASSED, zero mouse/pointer input anywhere in the audited pass.** Full log: `.audit_scratch/evidence/s2/s2_results.json`.

A short, clearly-separated mouse-driven **setup** step (login + reset Customer Zero to a clean slate) runs first, explicitly logged as `s2_setup_reset_done` and not counted as part of the keyboard proof. Every step from the next login onward — login, organisation selection, the Stage 2 setup needed to make a conditionally-gated Stage 4 option available, entering Stage 4, and the full 12-question walkthrough — used **only** keyboard events: `Tab`/`Shift+Tab` for navigation (global `page.keyboard.press`, which tested reliably) and `Enter`/`Space`/`ArrowUp`/`ArrowDown` dispatched to the currently-focused element via Playwright's `:focus` locator (see methodology note below).

### What was proven

- **Entered Stage 4 by ordinary UI navigation**: Tab-navigated to the real sidebar "Baseline" link and pressed Enter on it — not a remembered/typed URL.
- **All 12 questions answered and saved, keyboard-only.**
- **At least one "Not sure" answer**: question 1 (`mfa_user_accounts`) answered `MFA_USER_NOT_SURE`.
- **A conditionally-gated option set exercised**: `joiner_mover_leaver` (question 7) — gated on the confirmed fact `OrganisationProfile.people_with_system_access_count == 1`, which was itself set via keyboard in the Stage 2 setup — answered `JML_NOT_APPLICABLE`, with its required confirmation checkbox also checked via keyboard (`Space`) in the same submission. (`remote_access_control`'s NOT_APPLICABLE gate, on `has_remote_or_offsite_access == "no"`, was also satisfied by the same Stage 2 setup and was available but not the one exercised for the primary answer, which used the first offered option instead — the gate's *availability* was independently confirmed by DB read below.)
- **Visible focus indicator at every interactive stop**: 628 distinct focus-check observations recorded (every Tab/Arrow stop across login, navigation, and all 12 questions), each reading real `getComputedStyle(document.activeElement)` — **628/628 showed a visible focus indicator** (this codebase's global `:focus-visible { box-shadow: var(--focus-ring); }` rule, confirmed via computed style, not CSS source inspection).
- **No keyboard trap**: a dedicated 45-keypress Tab scan from a fresh Stage 4 page load recorded the full sequence of focused elements — `consecutive_dupes=0`, `distinct_stops=23` (header, full sidebar, and the question's own interactive controls, all genuinely reachable in sequence, no repeat-on-same-element trap).
- **Correct final progress state**: re-entering Stage 4 after finishing all 12 rendered **"Your Security — 12 of 12 reviewed · 1 still need confirmation"** — exactly matching the one "Not sure" answer given.

### Independent DB confirmation (read-only, after the fact)

```
selection details count: 12
unknown answers: 1
jml option_code: JML_NOT_APPLICABLE
mfa_user_accounts option_code: MFA_USER_NOT_SURE
```

### Methodology note (test-harness detail, not a product defect)

Direct experimentation found that Playwright's **global** `page.keyboard.press("Enter")` does not reliably trigger Chromium's native "Enter submits the nearest form" behaviour when focus was reached purely via synthetic Tab-navigated keyboard events in this headless CDP setup — confirmed by isolated reproduction (three separate minimal test scripts; identical username/password/CSRF-token values present and correct in the DOM, yet the global Enter press silently failed to submit, with no timing/race explanation ruled out by waiting up to 1 full second). Dispatching the same key to the currently-focused element via Playwright's `Locator(':focus').press('Enter')` — still a genuine keyboard key-press event, with zero mouse/pointer input involved — submitted reliably on every attempt thereafter. This is disclosed for transparency; it affected only the reliability of my own test automation, never the real behaviour of the product (which a human using a real keyboard, where OS-level and DOM-level focus never desynchronise, would never encounter).

---

## S3 — Foreign-tenant destructive reset, with the reset feature genuinely enabled

**Scripts:** `/tmp/m008-audit-fresh/repo/.audit_scratch/s3.py`, run in three phases (`setup`, `attacks`, `positive_control`) to allow independent DB/filesystem snapshots between them.
**Environment:** `DJANGO_ENV=development`, `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` — set in the stack's `.env` for its entire lifetime, confirmed live (not merely claimed) by the six `404`s below, which only occur on this code path when the flag is actually `True` (the view's own first check, `settings.CUSTOMER_ZERO_RESET_ENABLED`, raises `Http404` unconditionally when the flag is `False` — that branch was never reached in any of these attempts; every `404` below instead comes from the `CustomerZeroFixture`/membership checks further down the same view, which only run once the environment gate has already passed).

### Setup (`s3.py setup`)

- Logged in as `customerzero`, uploaded one real evidence file ("CZ audit evidence", 69 bytes) through the UI evidence-upload form.
- Logged in as `tenantb_auditor` (a genuinely separate, synthetic user with no relationship to Customer Zero), created **"Tenant B Audit Org"** entirely through the product's own self-service "Create organisation" form, and uploaded one real evidence file ("TB audit evidence", 64 bytes) to it.
- `cz_org_id = 06b7e59d-3a65-4d4d-ae18-2fb51847173b`, `tb_org_id = 40d074f8-aa06-4048-9b8f-9e8a42b55c5c`.

**BEFORE snapshot** (read-only DB + on-disk file hashes, independently queried):

```
CZ evidence: 1 item, sha256=ca780d43...92453, byte_size=69, stored as 170b33f7...add.txt
TB evidence: 1 item, sha256=f0754a58...9488b, byte_size=64, stored as ddebaabc...476a.txt
On-disk sha256sum of both files matches their DB-recorded sha256 exactly.
```

### Attack attempts (`s3.py attacks`, authenticated as `tenantb_auditor` throughout)

| # | Attempt | Method | Result |
|---|---|---|---|
| 1 | GET Customer Zero's own reset URL | `GET /organisations/<cz_org_id>/dev-tools/reset/` | **404** |
| 2 | POST Customer Zero's reset URL, `confirmation=RESET`, real CSRF token from Tenant B's own session | `POST` (form-urlencoded) | **404** |
| 3a | Identifier/URL forgery: POST to Tenant B's *own* reset URL with forged body fields (`organisation_id`, `organisation`, `target_organisation_id`) all set to Customer Zero's id, attempting to redirect the delete target via the body | `POST` | **404** |
| 3b | Identifier/URL forgery: GET Customer Zero's reset URL with the UUID path segment **uppercased** (Django's `uuid` path converter is case-insensitive per RFC 4122, so this resolves to the identical view/organisation) | `GET` | **404** |
| 4a | Reset attempt against Tenant B's **own** organisation (Tenant B *is* a genuine member here, but it is not the trusted fixture) | `GET /organisations/<tb_org_id>/dev-tools/reset/` | **404** |
| 4b | Same, as a `POST` with `confirmation=RESET` | `POST` | **404** |

**Every one of the six attempts failed closed with a genuine `404`, exactly as `organisations.views.customer_zero_reset`'s own design dictates** (the view never returns `403` for any of these — a non-fixture organisation renders identically to "doesn't exist", by design, so a member of a real foreign organisation never learns Customer Zero exists at all). Attack 4 specifically proves the `CustomerZeroFixture` identity check — not merely ordinary tenant-membership scoping — is what gates this feature: Tenant B legitimately owns `tb_org_id` and passes the membership check, yet is still refused, because that organisation is not the trusted fixture.

**A test-harness detail disclosed for transparency:** my first pass at attacks 2, 3a and 4b used Playwright's `page.request.post(..., data={...})`, which Playwright serializes as a JSON body by default — Django's CSRF middleware correctly rejected these as `403` ("Your session expired") before ever reaching the view's own logic, because `request.POST` was empty (JSON, not form-encoded) and no CSRF token was found in the expected form field. This was my own test tooling sending the wrong content type, not a product behaviour; a `403` from CSRF middleware is, in any case, still a "fails closed, zero deletion" outcome, not a near-miss. I corrected this to Playwright's `form={...}` parameter (genuine `application/x-www-form-urlencoded` body, matching exactly what the real HTML form sends) and obtained the clean `404`s shown above on every subsequent run.

**AFTER-ATTACKS snapshot** (read-only, independently queried, immediately after all six attempts):

```
CZ: 1 evidence item, SAME sha256 (ca780d43...92453), SAME stored_filename; baseline_assessment_exists=True (from S2, untouched); membership_count=1
TB: 1 evidence item, SAME sha256 (f0754a58...9488b), SAME stored_filename; membership_count=1
On-disk sha256sum of both files: IDENTICAL to the BEFORE snapshot, byte-for-byte.
```

**Neither Customer Zero's nor Tenant B's DB rows or evidence-file bytes changed as a result of any of the six attempts.**

### Positive control (`s3.py positive_control`, authenticated as `customerzero`)

```
positive_control_cz_login: OK → /organisations/
positive_control_reach_confirm_screen: OK → .../dev-tools/reset/ (confirmation form rendered)
positive_control_reset_succeeds_forces_logout: OK → /accounts/login/
```

**Independent DB/filesystem confirmation, after the fact:**

```
CZ evidence items after reset: 0
CZ baseline assessment exists after reset: False
CZ profile exists after reset: False
TB evidence items (should be untouched): 1
TB evidence sha256 (should be unchanged): f0754a586bf0616351fe99e9de181bfb2a570d591fef0769283daa3ad19488bb   ← identical
On-disk: only /data/evidence/<tb_org_id>/... remains; Customer Zero's evidence directory is gone entirely.
```

Customer Zero's own authenticated session **can** still successfully perform a real reset of itself — proving the feature genuinely works for the one actor it is meant to work for, and that every "fails closed" result above is a real, live security boundary (the `CustomerZeroFixture` check specifically), not a general malfunction of the reset feature as a whole.

---

## Verdict

**GREEN.**

All three Architect-identified gaps are closed with direct, live evidence from this Auditor's own disposable stack, independently re-derived from scratch:

- **A1 (real-browser E2E incomplete) — CLOSED.** S1 above is a single, continuous, entirely UI-driven pass — reset → login → Stages 1–4 → Risks & Actions → deterministic policy generation/review → approval → a genuine browser PDF download → reset → forced fresh login — with zero ORM writes, zero direct service calls, and zero direct HTTP POSTs outside Playwright browser automation anywhere in the customer-state-populating path. The Stage 1 save/redirect anomaly is conclusively root-caused (ordinary required-field validation, not a redirect defect) with direct reproduction evidence for both the failing and succeeding case.
- **A2 (destructive cross-tenant reset not proven with the feature enabled) — CLOSED.** S3 above ran every foreign-tenant attack attempt — GET, POST, two distinct identifier/URL forgery variants, and a reset attempt against the adversary's own, non-fixture organisation — with `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` live and confirmed (not inferred from code reading, not inferred from the feature-disabled case) for the entire scenario, including a genuine positive-control reset proving the feature still works for Customer Zero itself.
- **A3 (keyboard proof scope drift) — CLOSED.** S2 above is a dedicated, Stage-4-specific keyboard-only proof (not "at least one full guided-journey stage" — the broadened scope the Architect flagged as unauthorised) — zero mouse/pointer input, all 12 questions, a genuine "Not sure" answer, a genuine conditionally-gated NOT_APPLICABLE selection with its required confirmation checkbox, mechanically-proven visible focus at 628 distinct stops, a dedicated no-trap scan, and the correct final "12 of 12 reviewed · 1 still need confirmation" progress state.

**No genuine product defect was found anywhere in this supplement.** The two anomalies this Auditor itself hit (the `page.url`-timing race in S1's first pass, and the JSON-vs-form-encoded POST body in S3's first pass) were both my own test-harness artifacts, each independently root-caused, each disclosed above in full, and neither affected the final, clean results reported.

## Residual / open items

- This supplement did not re-run the full `pytest` suite (`2229 passed / 7 skipped / 1 xfailed` per the prior audit) — that was not in this Work Order's scope, which is bounded to closing exactly gaps A1/A2/A3 via S1/S2/S3.
- The disposable stack (`m008auditsupp`, ports `19950`/`19951`) and its two synthetic identities (`customerzero`, `tenantb_auditor`) were left running at the time of this report so the Architect can inspect them directly if desired; they are fully disposable (`docker compose -p m008auditsupp down -v` removes everything, including named volumes) and were never the canonical `infosecurs-relocation` deployment or any other pre-existing stack on this host.
- The `.audit_scratch/` directory inside the disposable working copy (scripts, screenshots, JSON result logs, the downloaded policy PDF, the two synthetic evidence `.txt` files) is **not** part of the committed repository — see below. It remains on `dell-debian` at `/tmp/m008-audit-fresh/repo/.audit_scratch/` for independent inspection until that working copy is cleaned up.

## What was and wasn't committed

Per the Work Order, this Auditor is authorised to add **only** `docs/evidence/M008-FINAL-REVERIFICATION-AUDIT-SUPPLEMENT.md` (this file) to branch `arch/m008-governance-recovery`, continuing PR #94. No other file was added, changed, or touched — the three Playwright scripts (`s1.py`/`s2.py`/`s3.py`), their JSON result logs, screenshots, the downloaded PDF, and the two synthetic evidence text files all live under `.audit_scratch/` inside the *disposable working copy* (`/tmp/m008-audit-fresh/repo`, itself a throwaway clone of `/srv/infosecurs`) — never inside `/srv/infosecurs` itself, and deliberately never committed to this repository.

No product repair was made or is being proposed. No application code, test code, migration, model, dependency, configuration, or CI file was touched anywhere in this supplement.
