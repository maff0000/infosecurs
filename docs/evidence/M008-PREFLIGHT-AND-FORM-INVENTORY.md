# M008 — WI0 Preflight & FOUNDATION-Accessible Free-Text Form Inventory

**Status:** first-pass inventory, produced during WI0 repository preflight. This
is the base survey M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md §4 Phase 0 calls
for ("all actual FOUNDATION-reachable routes/POSTs"). It is **not** the
exhaustive, replacement-mapped register M008B §B6 requires before the design
checkpoint — that fuller version (proposed replacement per field, screenshots,
dependency graph) is WI2 scope. This document establishes the starting
ground truth so WI2 has a verified base to extend, not a proposal.

**Method:** exhaustive `grep` sweep of every `forms.py` in the repository for
`forms.Textarea` widget usage, plus a direct search for raw HTML
`<textarea>` elements in templates (catches any narrative field not routed
through a Django form). Cross-referenced against each app's `urls.py` and
against `entitlements/migrations/0002_seed_product_areas.py`'s seeded
`min_package_tier` per `ProductArea`, which is the actual, governed source of
truth for which areas are FOUNDATION-reachable (`min_package_tier=1`) versus
MONTHLY+-only (`min_package_tier=2`, `customer_assurance`) versus PAUSED
(`min_package_tier=0`, `home`).

## Tier ground truth (from `entitlements/migrations/0002_seed_product_areas.py`)

| `min_package_tier` | Areas |
|---|---|
| 0 (PAUSED) | `home` |
| 1 (FOUNDATION) | `foundations`, `security` (+ `security_state`, `baseline`, `assets`, `risks`, `evidence`, `remediation`), `policies`, `company` (+ `profile`, `governance`, `workplace`, `activity`) |
| 2 (MONTHLY) | `customer_assurance` (questionnaire) |

Every app below except `questionnaire` is therefore FOUNDATION-reachable and
in scope for M008 non-negotiable #1 ("no discretionary multiline/free-
narrative field on any customer-facing route reachable within the FOUNDATION
product"). `questionnaire` sits at MONTHLY+ and is the PID's own named
exception ("Customer Assurance remains a distinct Monthly+ workflow... outside
the Foundations free-text restriction") — included here for completeness and
to prove the tier boundary is real, not to flag it as a violation.

## Inventory

Each row is a genuine, currently-reachable route with a multiline/narrative
input. "Verdict" classifies it against PID §3 non-negotiable #1's own
exception list (bounded identifier / date / number / file upload /
externally-supplied questionnaire input).

| # | App / form | Field | Widget | Route (URL name) | Tier | Verdict |
|---|---|---|---|---|---|---|
| 1 | `organisations.forms.OrganisationProfileForm` | `description` | `Textarea` rows=3 | `organisations:profile` | FOUNDATION | **VIOLATION** — free narrative business description. M008B §B3 "Business" proposes replacing with finite sector/motivation choice lists. |
| 2 | `organisations.forms.OrganisationProfileForm` | `commercial_security_driver` | `Textarea` rows=3 | `organisations:profile` | FOUNDATION | **VIOLATION** — M008B §B3 already proposes a controlled "customer/security motivation" choice list as the replacement. |
| 3 | `key_assets.forms.KeyAssetForm` | `description` | `Textarea` rows=3 | `key_assets:create`, `key_assets:edit` | FOUNDATION | **VIOLATION** — M008B §B3 Assets calls for "optional bounded asset label", not open narrative. |
| 4 | `evidence.forms._EvidenceCommonFieldsMixin.description` (used by both `EvidenceFileUploadForm` and `EvidenceExternalReferenceForm`) | `description` | `Textarea` rows=3, optional | `evidence:upload`, `evidence:add_reference` | FOUNDATION | **VIOLATION** — the file/reference itself is the legitimate exception (file upload / URL), but the free-text description alongside it is not. Needs a bounded/controlled replacement or removal per M008B §B3 Evidence ("safe filename is a file attribute not a narrative input"). |
| 5 | `evidence.forms.ControlEvidenceLinkForm` | `rationale` | `Textarea` rows=2, optional, max 500 | `evidence:link_control` | FOUNDATION | **VIOLATION** — narrative rationale for a support/contradict/context relationship; needs a controlled equivalent. |
| 6 | `risk_register.forms.RiskEditForm` | `threat` | `Textarea` rows=2 | `risk_register:edit` | FOUNDATION | **VIOLATION** — M008B §B3 Risk: "use the governed existing risk scenario catalogue... not user-authored threat/vulnerability prose." |
| 7 | `risk_register.forms.RiskEditForm` | `vulnerability` | `Textarea` rows=2 | `risk_register:edit` | FOUNDATION | **VIOLATION** — same as #6. |
| 8 | `risk_register.forms.RiskEditForm` | `rationale` | `Textarea` rows=3 | `risk_register:edit` | FOUNDATION | **VIOLATION** — same as #6. |
| 9 | `risk_register.forms.RiskEditForm` | `proposed_treatment` | `Textarea` rows=3 | `risk_register:edit` | FOUNDATION | **VIOLATION** — M008B §B3 Risk calls for "selectable owner/priority/treatment options" instead. |
| 10 | `remediation.forms.RemediationActionForm` | `description` | `Textarea` rows=4 | `remediation:create`, `remediation:create_from_risk`, `remediation:edit` | FOUNDATION | **VIOLATION** — M008B §B3 Remediation: "curated actions tied to a specific control/scenario", not an open-ended form. |
| 11 | `security_baseline.forms.BaselineAssessmentForm` | `note__<question_key>` (one per catalogue question, both the general 12-control page and the asset-specific protection-checks page) | `Textarea` rows=2, optional | `security_baseline:baseline` (and the reused instance on the asset-protection-checks page) | FOUNDATION | **VIOLATION — the primary/named target.** The form's own module docstring already identifies this as "the customer narrative field to retire from Foundation-facing UI." This is M008B's central deliverable: structured conditional follow-ups replace it. |
| 12 | `policy.forms.PolicyVersionEditForm` | one `section__<key>` field per policy section | `Textarea` rows=6 | `policy:version_edit` | FOUNDATION | **VIOLATION — the primary/named target for M008D.** M008D §D4 explicitly: "No per-section textarea for Foundation customer" — replace with the structured preview/approve/flag review UX. |
| — | `questionnaire.forms.QuestionnaireResponseEditForm` | `current_answer_text` | `Textarea` rows=8 | `questionnaire:response_edit` | **MONTHLY+** | **EXEMPT** — Customer Assurance response wording edit, explicitly carved out by PID §5/§non-negotiable #1. Confirmed genuinely gated at `min_package_tier=2`, not reachable from FOUNDATION. |
| — | `questionnaire/templates/questionnaire/list.html` (raw HTML, not Django-form-rendered) | `question_text` | raw `<textarea rows="4" required>` | `questionnaire:analyse` | **MONTHLY+** | **EXEMPT** — "paste one security questionnaire question" is externally-authored third-party content, exactly the PID's named "externally supplied Customer Assurance questionnaire input" exception. Also confirmed at `min_package_tier=2`. Noted separately from the form-based inventory above because it is hand-written HTML, not a `forms.py` widget — worth flagging to M008B/C so no future refactor accidentally treats it as an oversight. |

## Confirmed already-compliant apps (no violation found)

- `workplace.forms` — every field is `CharField` (short label/location),
  `IntegerField` (headcount), `ChoiceField`/`RadioSelect` (pattern/subtype).
  **Zero** `Textarea` usage anywhere in this app. Worth citing to M008C as the
  existing in-codebase precedent for what a fully structured onboarding form
  already looks like.
- `governance.forms` — `new_person_full_name`, `new_person_job_title`,
  `full_name`, `job_title` are all single-line bounded `CharField`s. No
  `Textarea`.

## Bounded-identifier exceptions already in place (not violations)

Per PID §3 non-negotiable #1's own exception list — short names, dates,
numbers, file upload:

- `organisations.forms.OrganisationCreateForm.name`,
  `OrganisationProfileForm.legal_trading_name`
- `key_assets.forms.KeyAssetForm.name`
- `evidence.forms._EvidenceCommonFieldsMixin.title`, `.source_label`,
  `observed_at`/`valid_until` (dates), `evidence.forms.EvidenceFileUploadForm.file`
  (upload), `EvidenceExternalReferenceForm.reference_url`
- `risk_register.forms.RiskEditForm.title`
- `remediation.forms.RemediationActionForm.title`, `.target_date`
- `workplace.forms.*` name/location fields, all headcount `IntegerField`s
- `governance.forms.RoleAssignmentForm.new_person_full_name`/`.new_person_job_title`,
  `MyDetailsForm.full_name`/`.job_title`
- `policy.forms.PolicyVersionEditForm.title`,
  `.next_review_date`/`PolicyApprovalConfirmForm.next_review_date`

## Totals

- **12 genuine FOUNDATION-reachable multiline narrative fields found — all 12
  are violations of PID §3 non-negotiable #1**, spanning 7 apps
  (`organisations`, `key_assets`, `evidence` ×2, `risk_register` ×4,
  `remediation`, `security_baseline`, `policy`).
- **2 fields exempt** under the Customer Assurance/MONTHLY+ carve-out
  (`questionnaire`), both independently confirmed gated at
  `min_package_tier=2` via the seeded `ProductArea` rows, not merely by
  developer intent.
- **0 violations** in `workplace` or `governance` — both already fully
  structured.

## What this document is not

This is a source-code/route inventory only — it does not yet propose the
replacement structured question/option catalogue for each violation (that is
M008B's own catalogue, §B2/§B3, subject to Product Authority approval), does
not include screenshots or a dependency graph (M008B §B6 / M008C §C3), and
does not attempt to resolve `evidence.description` or
`evidence.ControlEvidenceLinkForm.rationale`'s eventual replacement shape —
those are explicitly listed among the "hypotheses to be challenged" M008B
hands to Product Authority, not decided here.

## Preflight facts carried from repository verification (2026-09-30)

- Canonical `main` at WI0 start: `24173757c7fdcc856e3163ae6e14ebb2f981716e`
  (`origin/main` matched exactly; working tree clean except the known-benign
  untracked `docker-compose.override.yml`; no stray worktrees).
- `docs/pids/` contained only M001–M007 before this WI0; the five M008/M008A/
  M008B/M008C/M008D PID files are landed verbatim (byte-identical, `cmp`-
  verified against the supplied package) alongside this document in the same
  PR.
- DARWIN (`darwin-darwin_core-1`, `darwin-darwin_sql-1`, host port 8000) and
  the M007 dev GUI (`192.168.11.10:8884`, Compose project
  `infosecurs-relocation`) were both confirmed present/untouched and are not
  modified by this documentation-only change.
