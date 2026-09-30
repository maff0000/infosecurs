# M008A — Repeatable Customer Zero Reset (Development Only)

**Parent:** `M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`  
**Status:** authorised first executable WI, bounded to DEV Customer Zero.  
**Source facts checked:** `organisations.management.commands.create_customer_zero` is idempotent and creates/reuses a user, Organisation, Membership and Account Holder governance person/roles. It gets its identity and password from local environment. It does **not** provide a reset. Current app contains tenant-owned Profile, Baseline/Answers, Workplaces, Assets, Risks, Evidence/files/links, Remediation, Policy/Versions, Questionnaire, Activity and AI invocation history. No full dependency/deletion graph has yet been certified.

## A1. User story

From a visibly labelled **DEV · Test tools** area while signed in as synthetic Customer Zero, Matt can request **Reset test organisation**. An explicit confirmation explains permanent removal of this synthetic organisation's entered data. On success, the same test account logs in again and sees the identical fresh/unanswered Foundations experience, every time. No other organisation changes.

## A2. Non-negotiable destructive-action boundary

1. The endpoint is *404/not registered or fail-closed* unless `DJANGO_ENV=development` **and** an explicit opt-in `INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET=true` is present. `DEBUG` alone is not sufficient. With production/test env, unknown/absent flag or non-target organisation: no accessible reset UI/API even with a forged POST/session. Product account/entitlements still apply; never grant a bypass to PAUSED or unauthorised identities.
2. Target must be identified as the **exact bootstrapped Customer Zero fixture**, not any arbitrary organisation with a matching display name. Before implementation, choose and document an immutable trusted test-fixture identity mechanism (e.g. dedicated fixture marker bound to original organisation UUID at bootstrap or externally pinned UUID plus validated membership). Never use a client-supplied ID as sole authority. Preserve user, user password, Organisation UUID/name, Membership, required Account Holder OrganisationPerson and governance bootstrap identity; preserve ProductArea, FoundationRequirement, baseline/risk/question methodology and entitlements.
3. Only POST with CSRF, authenticated owner, canonical server-side session validity, capability and fixture identity checks. Confirmation must name the exact organisation and include an explicit action (`RESET` or deliberate second confirmation); never trigger via GET, link prefetch or ordinary page navigation. Add throttling or single-flight protection against repeated concurrent posts; duplicate reset is deterministic and safe.
4. Reset deletes ONLY explicitly inventoried synthetic **tenant-owned** business records. No `flush`, `DROP`, truncate, unscoped `.delete()`, broad `User.objects` delete, shared product catalogue writes, arbitrary raw SQL or whole Docker volume teardown. Do not delete other tenants, global users, other-tenant login sessions, shared uploaded files, or production artefacts.
5. No reset route or command silently falls back to a broad database wipe if its safety preflight fails. Unexpected relations/unrecognised new models must cause STOP and an actionable inventory report rather than partial destructive action.

## A3. Mandatory pre-implementation deletion manifest

GUNNAR inventories **actual Django `on_delete` relationships** and storage paths for all of the following (and *any other* tenant-owned rows discovered), then records exact model/table counts and ownership before coding: OrganisationProfile, AuditEvent, BaselineAssessment/Answer, Workplace, OrganisationPerson/GovernanceRoleAssignment, KeyAsset, Risk, EvidenceItem/ControlEvidenceLink, RemediationAction/ActionEvidenceLink, current SecurityState-derived/persisted models, PolicyDocument/PolicyVersion (including approved versions in Customer Zero only), questionnaire question/response/history/grounding, activity/event/invocation records, and future M008 answer-detail records. Catalogue/seeds, user/auth, organisation/membership, session/entitlement structures are explicitly classified as preserve/reset/derived; no gaps allowed. Inventory target-specific media/evidence files with resolved path and ownership checks.

## A4. Reset semantics

- Result is a **known baseline** defined by a checked-in synthetic fixture contract, not just an empty database: preserve same Customer Zero user, organisation, membership and Account Holder identity/roles; delete all synthetic entered facts/answers/derived risk and generated artifacts; leave typed optional profile fields absent/default `unknown`, 12 baseline answers unrecorded or explicitly `unknown` according to canonical fresh-install behaviour; 18 M007 completion requirements recompute from facts, never set a score.
- The Account Holder bootstrap person/role is necessary for existing policy/identity flow. Snapshot expected untouched values before reset; if default Foundation milestones treat that assignment as satisfied on freshly bootstrapped organisation, the reset must mirror that **same** fresh-bootstrap state rather than changing methodology.
- Reset is transactionally consistent for DB: preflight, exact-tenant scoped deletes, recreate/ensure required bootstrap within a transaction; no cross-tenant cascades. For stored evidence bytes, DB and filesystem are not one atomic resource: collect safe, manifest-listed tenant file paths; delete only after DB commit with a retryable cleanup ledger/report, idempotency and **no shared path deletion**. Report incomplete cleanup as failure/pending cleanup, never call it GREEN. If the chosen mechanism cannot make safe deletion provable, STOP before first destructive run.
- Clear or rotate the current Customer Zero session after reset; require fresh login; never compromise the M007 session contract. Other users' sessions remain untouched, and an existing URL to a deleted object yields 404. Keep operational reset event in a separate non-tenant dev operational log if needed; avoid false surviving business audit history.
- No AI call. Reset is fast for small synthetic fixtures and cannot be repurposed to erase real customer records.

## A5. Interface

Single visible **Reset test organisation** button under `Development tools` only when all gates satisfy; warning says all synthetic answers, assets, evidence files, risks, generated policies and history for this one fixture will be erased; typed confirmation; busy/duplicate click handling; after completion redirect to clean Home/Foundations or login (depending session-rotation contract). Accessible keyboard/focus and clear screen-reader labels. No reset UI at all for non-dev or other org.

## A6. Tests / adversarial challenges

- Exact Customer Zero fixture reset after fully-populated synthetic scenario; repeat reset, prove identical fresh state and scores; prove same user password hash, org UUID, membership and required bootstrap identity, catalogue row counts and schema/methodology versions.
- A second unrelated tenant with same object types and evidence files remains byte-for-byte unchanged, including approved policy history. A similarly named organisation or forged org UUID must be denied.
- Production/test `DJANGO_ENV`, missing flag, non-Owner, wrong/paused tier, stale session, CSRF absent, GET, forged POST, forced replays and concurrent resets denied/no data damage.
- Delete/remap safety: an unknown foreign relation, missing evidence file, cleanup failure, corrupted/foreign storage path and rollback; fail closed with useful operator record.
- Manual first-pass UI Chromium: one button, one confirmation, resets and fresh journey renders. `:8884` stays working; no server/data volumes rebuilt unnecessarily.
- No model hidden scores/flags erroneously mark Foundations complete; exact M007 two metrics re-compute and show proper starting values.
- All existing M001–M007 tests and session/tenant security checks stay green.

## A7. Deliverables and closure

`docs/evidence/M008A-RESET-SAFETY.md` must contain deletion-ownership manifest, first/second reset counts, before/after hashes on another tenant, file cleanup/retry proof, production-denial proof and screenshots. PR includes code/test, gitleaks, six CI checks, CodeQL. Independent PL reproduces; separate bounded Auditor attacks destructive scope and environment gating. **M008A CLOSED GREEN is a prerequisite for repeatable design testing; not itself full M008 PRODUCT_GREEN.** Stop and report to Matt after reset works. Do not begin method/catalogue product code before the design-approval checkpoint.
