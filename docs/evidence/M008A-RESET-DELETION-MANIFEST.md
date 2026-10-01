# M008A — Reset Deletion Manifest

**Status:** FROZEN pre-implementation manifest (PID §A3: "GUNNAR inventories
actual Django `on_delete` relationships and storage paths... records exact
model/table counts and ownership before coding"). This document is the
single source of truth the M008A reset service must implement against.
Derived entirely from direct reads of the live model graph on canonical
main `809014222546ddc18e5953477455adb4f11f1df9`, not inferred from the PID
text alone.

**Classification key:** every tenant-owned model is exactly one of:
- **PRESERVE** — bootstrap identity; the reset must never touch this row.
- **DELETE** — synthetic business/security data; the reset must remove
  every row scoped to the target organisation.
- **RECREATE/ENSURE** — must exist in a specific state after reset,
  re-derived via the same idempotent bootstrap path, not hand-written.
- **DERIVED/NO PERSISTED STATE** — nothing to delete; correctness follows
  automatically once its own inputs are correctly reset.

## Bootstrap identity — PRESERVE (never deleted, never recreated with a new identity)

| Model | What survives | Why |
|---|---|---|
| `auth.User` (Customer Zero user) | username, password hash, email, pk | The reset is "clear business data," never "destroy and recreate the account." |
| `organisations.Organisation` | UUID pk, `name` | Deleting and recreating this would mint a new UUID — violates "same org UUID every reset" (PID §A4). |
| `organisations.CustomerZeroFixture` | the one marker row (M008A-WI1a) | **This is the reset's own authority check** — see §2 below. Deleting it would make the fixture unidentifiable to the next reset. |
| `organisations.OrganisationMembership` | the Owner membership row | Required for the user to reach the organisation at all post-reset. |
| `governance.OrganisationPerson` (Account Holder's own row only) | the one row with `user=<customer zero user>` | Confirmed: enforced unique by the partial `unique_linked_user_per_organisation` constraint (`user__isnull=False`) — there is exactly one such row per organisation. |
| `governance.GovernanceRoleAssignment` (the 3 rows assigned to the Account Holder) | all 3 `ROLE_CHOICES` rows, `person=<Account Holder's OrganisationPerson>` | **Confirmed by direct code read of `governance.services.ensure_account_holder_person`**: on genuine first bootstrap it unconditionally assigns *all three* role choices to the Account Holder. A reset's fresh-state contract must reproduce exactly this — not zero roles. |
| `entitlements.ProductArea` | all 16 seeded rows, globally | Zero FK to `Organisation` anywhere in this model — confirmed structurally impossible for a per-organisation reset to touch it. |
| `entitlements.FoundationRequirement` | all 18 seeded rows, globally | Same — zero FK to `Organisation`. `product_area` FK is `PROTECT`, but that's internal to the untouched global catalogue. |

## Synthetic business/security data — DELETE (every row scoped to the target organisation)

| App.Model | FK → | on_delete | Files on disk? | Ordering note |
|---|---|---|---|---|
| `organisations.OrganisationProfile` | `organisation` (OneToOne) | CASCADE | no | **Confirmed safe to let cascade-delete, no recreation needed** — `organisations/views.py`'s profile view does `.filter(organisation=organisation).first()` (not `.get()`), and builds the form with `instance=None` gracefully when absent. Classified DELETE, not RECREATE/ENSURE. |
| `organisations.AuditEvent` | `organisation` | CASCADE | no | Synthetic audit trail of profile changes for this fixture. |
| `security_baseline.BaselineAssessment` | `organisation` (OneToOne) | CASCADE | no | Cascades to all its `BaselineAnswer` rows automatically — no separate delete call needed. |
| `security_baseline.BaselineAnswer` | `assessment` | CASCADE | no | **Confirmed**: `entitlements/metrics.py`'s resolver reads `baseline_answers.get(question_key, ANSWER_UNKNOWN)` — a hard-delete of every row produces a lookup dict with zero entries, so every question resolves to `ANSWER_UNKNOWN`, byte-identical to "never answered." No special-casing required for the UNKNOWN-never-NO fresh-state contract. |
| `workplace.Workplace` | `organisation` | CASCADE | no | |
| `governance.OrganisationPerson` (every row except the Account Holder's) | `organisation` | CASCADE | no | Delete all rows where `user` is null or `user != <customer zero user>`. |
| `governance.GovernanceRoleAssignment` (every assignment except the Account Holder's 3) | `organisation` | CASCADE | no | `person` FK is `PROTECT` against `OrganisationPerson` — **see the one real ordering constraint below.** |
| `key_assets.KeyAsset` | `organisation` | CASCADE | no | |
| `risk_register.Risk` | `organisation` | CASCADE | no | `key_asset`/`ai_invocation_record` FKs are `SET_NULL` — no ordering constraint. |
| `evidence.EvidenceItem` | `organisation` | CASCADE | **yes** | DB row and file bytes are two separate resources — see filesystem section below. `superseded_by` self-FK is `SET_NULL`. |
| `evidence.ControlEvidenceLink` | `organisation`, `evidence` | both CASCADE | no | Deleted transitively with either parent. |
| `remediation.RemediationAction` | `organisation` | CASCADE | no | `risk`/`key_asset`/`completed_by`/`assigned_to`/`created_by` FKs are `SET_NULL` — no ordering constraint. |
| `remediation.ActionEvidenceLink` | `organisation`, `action`, `evidence` | all CASCADE | no | |
| `policy.PolicyDocument` | `organisation` (OneToOne) | CASCADE | no | Cascades to all its `PolicyVersion` rows. |
| `policy.PolicyVersion` | `document`, `organisation` | both CASCADE | no (PDF rendered on demand, never stored as a file) | **Confirmed by reading `PolicyVersion.save()` directly**: its `ImmutablePolicyVersionError` guard is scoped to `save()` only. Django's cascade-delete collector issues bulk `DELETE` SQL and never calls `.save()` on the rows being removed — the guard cannot fire during a whole-row cascade delete. Safe to delete approved/superseded versions this way; **never** attempt an in-place field wipe instead (that would hit the guard, correctly). `policy_authoriser`/`approved_by`/`ai_invocation_record`/`superseded_by` FKs are all `SET_NULL`. |
| `questionnaire.QuestionnaireQuestion` | `organisation` | CASCADE | no | Cascades to all its `QuestionnaireResponse` rows. |
| `questionnaire.QuestionnaireResponse` | `organisation`, `question` | both CASCADE | no | Same immutability-guard-vs-cascade-delete reasoning as `PolicyVersion` above — confirmed by reading its `save()` override directly; irrelevant to deletion. |
| `activity.ActivityEvent` | `organisation` | CASCADE | no | Append-only log; PID §A4 explicitly: "avoid false surviving business audit history" for a synthetic fixture. |
| `ai_platform.AIInvocationRecord` | `organisation` | CASCADE | no | Stores only a hash, never raw prompt/response — nothing extra to scrub. |

## DERIVED / NO PERSISTED STATE — nothing to delete

| App | Why |
|---|---|
| `security_state` | **Confirmed by reading `security_state/models.py` directly**: it is a docstring-only file — "Deliberately no models here... a read-only aggregation/projection layer over `security_baseline.BaselineAnswer`, `evidence.ControlEvidenceLink`/`EvidenceItem` and `remediation.RemediationAction`... Nothing in this app calls `.save()`/`.create()`/`.update()`/`.delete()` against any model." Its correctness is automatic once the three source apps above are correctly reset. |
| `entitlements` posture/completion metrics | Computed on read from surviving facts (confirmed above for baseline; the same resolver pattern applies to the other 17 of the 18 completion requirements) — never directly written by the reset. Recomputing automatically shows correct fresh values once the underlying facts are deleted. |

## The one real ordering constraint

`governance.GovernanceRoleAssignment.person` is `on_delete=models.PROTECT` against `OrganisationPerson` (not against `Organisation` directly — there is no PROTECT anywhere pointing at `Organisation` itself, confirmed). The reset never deletes the `Organisation` row itself (it's PRESERVE), so a naive `Organisation.delete()` cascade is never attempted — but the manual per-model deletes above must still respect this ordering **within the transaction**:

1. Delete every `GovernanceRoleAssignment` for this organisation **except** the 3 rows pointing at the Account Holder's own `OrganisationPerson`.
2. Delete every `OrganisationPerson` for this organisation **except** the Account Holder's own row.
3. (Steps 1–2 must happen in this order — deleting a non-Account-Holder `OrganisationPerson` while a `GovernanceRoleAssignment` still protects it via `PROTECT` would raise `ProtectedError`; deleting the role assignments first clears that protection.)

No other `PROTECT`/`RESTRICT` exists anywhere in the organisation-rooted FK graph.

## Filesystem — evidence bytes (separate resource, not atomic with the DB transaction)

- **Confirmed exact path pattern** by reading `evidence/storage.py` directly: `EVIDENCE_STORAGE_ROOT/<organisation_id>/<opaque-server-generated-uuid-filename>.<ext>` — one directory per tenant, fully isolated, server-generated opaque filenames (never derived from client input, never derived from a DB-stored path field — `EvidenceItem` stores only the bare `stored_filename`, no directory component).
- **No existing helper for "delete organisation X's whole evidence directory" or "list all files for organisation X"** — only `evidence_file_path(organisation_id, stored_filename)` exists, resolving and containment-checking one file at a time. **The Engineer must write a new helper** reusing that exact containment pattern (`os.path.realpath(os.path.join(root, str(organisation_id)))`, verified via `os.path.commonpath` against `root` before any removal — never trust a constructed path without re-verifying containment).
- **Required ordering** (PID §A4's own words: DB and filesystem are "not one atomic resource"): the DB transaction (all `DELETE`s above) commits first; only after a successful commit does the reset enumerate and remove the organisation's evidence directory. If filesystem cleanup fails partway, the DB state is already fully consistent (zero `EvidenceItem` rows reference the now-partially-deleted files), and the cleanup step must be safely retryable/idempotent on a later run without touching the DB again.
- Never delete a file because a filename was merely supplied in a request or reconstructed from an assumption — only ever remove files found by actually listing the real, containment-verified `<organisation_id>` directory.

## Session handling (action, not a model to delete)

Not a persisted per-organisation model — the *active HTTP session* for the request performing the reset. Per Central Architecture's explicit instruction (§8): after the DB transaction commits and evidence-byte cleanup is attempted, call Django's own `logout(request)` (not merely `entitlements.session.issue_context`'s key-rotation) to fully destroy the current session, then redirect to the login page. Other users' sessions are keyed independently and must be completely unaffected — `logout(request)` only ever touches the current request's own session.

## Totals

- **7 bootstrap-identity row groups PRESERVE** (User, Organisation, CustomerZeroFixture, Membership, Account Holder's OrganisationPerson, Account Holder's 3 GovernanceRoleAssignments, the 2 global catalogues).
- **17 app/model DELETE targets**, all CASCADE from `organisation`, one real intra-transaction ordering constraint (GovernanceRoleAssignment before OrganisationPerson, scoped to non-Account-Holder rows only).
- **1 derived app with zero persisted state** (`security_state`).
- **1 separate filesystem resource** (evidence bytes) requiring a new containment-checked directory-deletion helper, committed only after the DB transaction succeeds.
- **1 required session action** (`logout(request)`, not a model).

No unclassified tenant-owned model remains outside this manifest as of canonical main `809014222546ddc18e5953477455adb4f11f1df9`. If `manage.py` preflight at implementation time finds any `Organisation`-scoped FK not listed here, the reset must FAIL CLOSED rather than proceed with a best-effort delete — see the Engineer dispatch's own preflight-check requirement.
