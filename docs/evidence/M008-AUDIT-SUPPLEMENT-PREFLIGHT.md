# M008 — Audit Supplement Preflight

**Work Order:** `docs/work-orders/WO-M008-GOV-RECOVERY-002.md`
**Amendment:** `docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md`
**Architect review this supplement answers:** `docs/evidence/M008-ARCHITECT-REVIEW-PR94.md` (gaps A1, A2, A3)
**Frozen product SHA:** `6393912bc4f7a98e5d167a465369bf2a8ef26c57`
**Reviewed PR #94 head (recovery branch base for this supplement):** `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40`
**Worktree HEAD at time of this preflight:** `bb6d4ec7fd0bbb676ac4a32ef241762f890fd105`
**Implementer:** bounded Implementer, this session
**Scope:** this document only. No product code, no test code, no migrations, no dependencies, no configuration, no runtime product data.

## 1. `origin/main` frozen-SHA check

Ran directly in the worktree:

```
git ls-remote origin main
6393912bc4f7a98e5d167a465369bf2a8ef26c57	refs/heads/main
```

`origin/main` is exactly the frozen product SHA. Confirmed directly, not assumed.

## 2. PR #94 head is the base of this supplement

Ran directly:

```
git merge-base --is-ancestor 73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40 HEAD
```

Exit status 0 — `73bcb0d1dbd84eb8459f18eb5b3c1b3698949a40` (the reviewed PR #94 head) is a true ancestor of the current worktree HEAD (`bb6d4ec7fd0bbb676ac4a32ef241762f890fd105`). The commit graph from the frozen SHA to current HEAD is:

```
6393912 (frozen product SHA, origin/main)
  a380e8c [ARCH] M008 governance recovery: Phase 0 — record Architect authority
  79100a6 [WO-M008-GOV-RECOVERY-001] Record Implementer preflight evidence
  73bcb0d [WO-M008-GOV-RECOVERY-001] Independent final re-verification audit - GREEN   <- reviewed PR #94 head
  bb6d4ec [ARCH] M008 governance recovery: record Architect review + Amendment 002 + WO-002   <- current worktree HEAD
```

This confirms the supplement genuinely continues from the reviewed PR #94 head, with no rewritten or substituted history underneath it.

## 3. Every changed path remains governance/evidence documentation — zero product-path drift

Ran directly:

```
git diff --stat 6393912bc4f7a98e5d167a465369bf2a8ef26c57 HEAD
git diff --name-status 6393912bc4f7a98e5d167a465369bf2a8ef26c57 HEAD
```

Full result — 8 files changed, all additions (`A`), 1054 insertions, 0 deletions, 0 modifications of any existing file:

```
A  docs/architecture/DELIVERY-GOVERNANCE.md
A  docs/evidence/M008-ARCHITECT-REVIEW-PR94.md
A  docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md
A  docs/evidence/M008-GOVERNANCE-RECOVERY-PREFLIGHT.md
A  docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT-002.md
A  docs/pids/M008-GOVERNANCE-RECOVERY-AMENDMENT.md
A  docs/work-orders/WO-M008-GOV-RECOVERY-001.md
A  docs/work-orders/WO-M008-GOV-RECOVERY-002.md
```

Every one of these eight paths is under `docs/architecture/`, `docs/evidence/`, `docs/pids/`, or `docs/work-orders/` — the governance/evidence documentation tree this recovery has been adding commit by commit since the frozen SHA. None is a product path (no `organisations/`, `policy/`, `core/`, `config/`, `requirements*.txt`, `Dockerfile`, `docker-compose*.yml`, migrations, templates, or test files appear anywhere in the diff). No existing file was modified or deleted — every change is a brand-new file addition.

**Conclusion: the frozen product is confirmed byte-identical to `6393912bc4f7a98e5d167a465369bf2a8ef26c57` as of this worktree's HEAD. No defect in the recovery process itself was found.**

## 4. Disposable audit environment and synthetic identities the next phase will use

This is a summary, in my own words, of what the next, separately-dispatched Auditor will stand up — read from this repository's own operational runbooks, not invented:

### Environment

Per `docs/runbooks/BETA-OPERATIONS.md` ("Start"): the Auditor brings up a disposable, single-stack Docker Compose deployment (`db` + `web`, the same `docker-compose.yml` already in this repository) under its own throwaway project name, its own synthetic `.env` (copied from `.env.example` with local-only values), and its own host ports — never the canonical `infosecurs-relocation` deployment, and never the frozen product's own ports. `docker compose up -d` brings up `db` (health-gated on `pg_isready`) then `web`; `web`'s startup command runs `python manage.py migrate --noinput` automatically, so the stack self-migrates on first boot. `/healthz/` returning `{"status": "ok", "database": true}` is the signal the stack is ready to use.

Per `docs/runbooks/BROWSER-ACCEPTANCE-CAPABILITY.md`: the `playwright` Python package is already baked into the image (a normal `requirements-dev.txt` dependency), but the actual Chromium browser binary deliberately is **not** part of any built image — there is no `RUN playwright install` line in the `Dockerfile`, by design, so the production/release image never carries a bundled browser. The Auditor must separately run, against the already-running `web` container (not a throwaway `run --rm`):

```
docker compose -p <project> exec web playwright install --with-deps chromium
```

This installs the Chromium binary plus its OS-level shared libraries into that one container's writable layer only. Only after this step do the `pytest.importorskip("playwright")`-gated real-browser tests — and the Auditor's own Playwright automation for S1/S2 — actually run against a real browser instead of being skipped. Nothing here touches the Dockerfile or any image layer; `docker compose down` / a fresh build discards it completely.

### Synthetic identities

- **Customer Zero** — bootstrapped via the repository's own management command, `manage.py create_customer_zero`, which creates the fixture organisation (`customerzero` / "Infosecurs Limited") and its three governance-role assignments against the Account Holder, exactly as the prior audit (`docs/evidence/M008-FINAL-REVERIFICATION-AUDIT.md` §3, §14) already established. This is the trusted fixture the dev-only reset feature is designed to operate on.
- **A second, unrelated synthetic tenant** — a genuinely separate organisation and user with no relationship to Customer Zero (the prior audit's precedent, `tenantb_auditor` / "Tenant B Audit Org", with its own distinct `OrganisationMembership`, illustrates the shape required). For S3 this second tenant is the adversary: it must never be made the trusted `CustomerZeroFixture`, and the next Auditor must authenticate as it directly, not merely construct it.

Both identities are synthetic and disposable, created fresh inside the throwaway stack above — no real customer data, exactly as Amendment 002 requires.

## 5. S1 / S2 / S3 — the plan the next Auditor will execute (summary only; not executed here)

The following is my own summary of the scenarios the Work Order specifies. I am describing the plan; I have not run any of it, and I am not authorised to.

### S1 — True browser-only Customer Zero end-to-end cycle

A single continuous pass, driven entirely through the rendered UI with real Chromium/Playwright, with no ORM writes, no direct service calls, and no direct HTTP POSTs outside the browser automation used to populate customer state anywhere in the chain (read-only database inspection after an action, to confirm what was actually persisted, remains allowed):

reset Customer Zero → log in → finish Stage 1 on-screen → finish Stage 2 on-screen → finish Stage 3 on-screen → answer all 12 Stage 4 questions on-screen → work through Risks & Actions on-screen → generate/review the deterministic policy on-screen → approve the policy on-screen → download the real policy PDF through the browser → reset Customer Zero again → prove the next login is forced to authenticate fresh (no leftover session).

This directly answers gap **A1**: the prior audit's own account (`M008-FINAL-REVERIFICATION-AUDIT.md` §3) admits Stage 2–3 state was populated via direct service/model calls and Stage 4 via direct HTTP POSTs rather than the rendered UI, which the Architect ruled does not satisfy a real-browser E2E requirement. S1 requires the whole cycle, Stage 1 through final reset, to go through the browser only.

S1 must also **close**, not route around, the specific unexplained anomaly the same prior audit disclosed: its very first Stage-1 keyboard-submit attempt appeared to leave the browser on the Stage-1 URL after a correctly targeted Enter-key submission, and that specific symptom was never independently root-caused — the auditor switched to direct service/model calls for the remaining stages instead of resolving it. (It is distinct from the separate, already self-diagnosed and already-fixed "Log out button" CSS-selector collision bug documented in the same section.) The next Auditor must drive the Stage 1 save/redirect path for real, through the browser, and either reproduce and root-cause that anomaly or positively demonstrate the save/redirect behaves correctly end to end — not merely avoid triggering it by using a different method.

### S2 — Keyboard-only Stage 4 walkthrough

A real-Chromium pass through Stage 4 specifically, with zero mouse/pointer input of any kind: enter Stage 4 through ordinary UI navigation, then move between all interactive controls, select answers, and save/advance using the keyboard alone, across all 12 questions. The pass must include at least one question answered "Not sure" and must exercise at least one conditionally-gated option set (a control whose NOT_APPLICABLE option only appears given a specific prior answer). Throughout, the Auditor must mechanically prove — by reading real computed style, not by inspecting CSS source — that every interactive stop has a visible focus indicator, that focus never becomes trapped anywhere in the stage, and that the stage ends in the correct reviewed/still-needs-confirming progress state.

This directly answers gap **A3**: the Architect's original recovery directive called for a keyboard-only proof specifically on Stage 4, but the Work Order as recorded was broadened to "at least one full guided-journey stage" and the prior audit exercised Stage 1 instead — a change the Architect never authorised. S2 restores the original, narrower Stage-4-specific requirement.

### S3 — Foreign-tenant destructive reset attempt with the feature enabled

Run with `DJANGO_ENV=development` and `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` set for the whole scenario (not toggled only for Customer Zero's own positive reset at the end). With Customer Zero and the second, unrelated synthetic tenant both present, authenticate as the second tenant and, while the flag remains enabled throughout, attempt every destructive action directly against that authenticated session:

- a `GET` against Customer Zero's dev-only reset URL;
- a `POST` against the same URL with the confirmation payload;
- identifier/URL forgery — substituting Customer Zero's organisation id/slug into the second tenant's own request context wherever the route accepts one;
- a reset attempt by the second tenant against itself, even though it is not the trusted fixture and so should not be resettable either.

Every one of these must fail closed, and the Auditor must prove — by direct database/evidence inspection immediately after each attempt, not by inference from one passing case — that neither Customer Zero's nor the second tenant's database rows or evidence bytes changed as a result. Only after all of that is proven does the Auditor perform one genuine positive reset, as Customer Zero itself, to show the feature still works for the one identity it is meant to work for.

This directly answers gap **A2**: the prior audit's cross-tenant reset check was run while the reset feature was *disabled* (`INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=false`), so the 404 it observed was the ordinary tenant-isolation check, not proof that the destructive-reset-specific authorisation logic itself holds up when the feature is live. The Architect requires the foreign-tenant attempt proven directly with the flag enabled — not inferred from code reading, and not inferred from the feature-disabled case.

## 6. What this preflight took as given, and why that was safe

- The authenticity and binding force of the three governance documents (Architect review, Amendment 002, Work Order 002) — these are the Implementer's chain of authority per the Work Order's own instructions, and re-litigating them is outside this role's scope; their SHAs and content were read directly from the worktree, not merely assumed from the dispatch prompt.
- The accuracy of the *prior* audit's own factual narrative (what it actually did and found, e.g. the Stage-1 anomaly description, the Customer Zero / Tenant B bootstrap shape) — taken as given because this preflight's job is to plan the next audit from the existing record, not to re-audit the previous audit's claims; the next Auditor is the one who independently re-verifies product behaviour.
- Everything bearing directly on this Work Order's own verification duties (origin/main's SHA, the ancestry of PR #94's head, the full byte-for-byte path diff against the frozen SHA, and the runbook procedures for environment setup) was checked directly against the live worktree and remote, not assumed.
