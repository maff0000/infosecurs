# M008B — Exact Stage 1–3 Structured Question Catalogue (Revision 2, new deliverable)

**Status:** DESIGN ARTEFACT. Produced in full per Central Architecture's
explicit instruction not to leave Stage 1–3 wording/options to Engineer
implementation. Every question below maps to a real, already-existing
field (or one of the two new dedicated facts from
`M008B-QUESTION-CATALOGUE.md` §0) — nothing here invents a new
canonical data model beyond those two additive fields.

Technology/data questions that Revision 1 placed in Stage 1 are moved to
Stage 3, per Central Architecture's explicit instruction.

**[WI-ERRATA correction]** Stage 1 originally omitted two existing
`OrganisationProfile` facts that belong there. Both are added below as
1.4 and 1.5 — no new canonical data model, both fields already exist.

---

## Stage 1 — Your Business

**Business identity/context only.** Five questions.

### 1.1 Legal / trading name
- **Question:** "What is your business's legal or trading name?"
- **Input:** bounded text (the one genuinely unavoidable identifier,
  per Central Architecture's own exception) — `OrganisationProfile.
  legal_trading_name`. **Never sent to any AI prompt.**

### 1.2 Sector
- **Question:** "Which best describes what your business does?"
- **Input:** single choice from a finite list — **new field**,
  `OrganisationProfile.sector` (additive migration), replacing
  Revision 1's free-text "what you do in a few words."
- **Options (`option_code` → label):**
  | `option_code` | Label |
  |---|---|
  | `SECTOR_PROFESSIONAL_CONSULTING` | Professional or consulting services |
  | `SECTOR_RETAIL_ECOMMERCE` | Retail or e-commerce |
  | `SECTOR_FINANCIAL_ACCOUNTING` | Financial or accounting services |
  | `SECTOR_HEALTHCARE_CARE` | Healthcare or care services |
  | `SECTOR_TECHNOLOGY_SOFTWARE` | Technology or software |
  | `SECTOR_MANUFACTURING_LOGISTICS` | Manufacturing or logistics |
  | `SECTOR_CONSTRUCTION_TRADES` | Construction or trades |
  | `SECTOR_EDUCATION_TRAINING` | Education or training |
  | `SECTOR_LEGAL_SERVICES` | Legal services |
  | `SECTOR_HOSPITALITY` | Hospitality |
  | `SECTOR_OTHER` | Other / not listed |
  | `SECTOR_NOT_SURE` | Not sure yet |

### 1.3 Business size
- **Question:** "Approximately how many people work at the business?"
- **Input:** number — existing `OrganisationProfile.staff_count`.
  **Context only** — per Central Architecture's correction, this value
  is **never** sufficient authority for any NOT_APPLICABLE gate on its
  own (see control 7's own dedicated gating fact instead).

### 1.4 Why are you working on security now? — **[WI-ERRATA, added]**
- **Question:** "Why are you working on security now?"
- **Input:** single choice from a finite list — existing
  `OrganisationProfile.commercial_security_driver` field (already a
  `CharField`; this choice list is the field's corrected, bounded value
  set, per the free-text replacement register's Row 2 correction — no
  new column).
- **Options (`option_code` → label):**
  | `option_code` | Label |
  |---|---|
  | `DRIVER_CUSTOMER_SUPPLIER` | A customer or supplier has asked us to |
  | `DRIVER_SENSITIVE_DATA` | We handle sensitive or confidential information |
  | `DRIVER_CERTIFICATION_CONTRACT` | We need it for a certification or contract |
  | `DRIVER_GENERAL_RISK` | We want to reduce cyber risk generally |
  | `DRIVER_NOT_SURE` | Not sure yet |
- Single choice. **No text field** — the free-text replacement
  register's Row 2 correction (removing the open "why security matters"
  narrative) is implemented exactly by this question.

### 1.5 Do customers or suppliers ask you to complete security questionnaires? — **[WI-ERRATA, added]**
- **Question:** "Do customers or suppliers ever ask you to complete
  security questionnaires?"
- **Input:** single choice — existing `OrganisationProfile.
  receives_security_questionnaires` field, the existing tri-state
  `TRI_STATE_CHOICES` values (`UNKNOWN` → "Not confirmed", `YES` →
  "Yes", `NO` → "No"), presented to the customer as Yes / No / Not sure.
  No new truth store — this is the field's existing value set, asked at
  the right point in the guided journey rather than left stranded.

---

## Stage 2 — Your People & Workplaces

**People, access population, work pattern, workplaces, governance
roles.** Five questions/steps.

### 2.1 Work pattern
- **Question:** "Where do people normally work?"
- **Input:** single choice — the existing `workplace.
  WorkplacePatternForm.PATTERN_CHOICES`, unchanged:
  | `option_code` (existing constant) | Label |
  |---|---|
  | `all_remote` | Everyone works from home |
  | `one_office` | We have one office |
  | `shared_coworking` | We use a shared/coworking office |
  | `office_and_home` | Office + home working |
  | `several_locations` | We have several locations |
- **Follow-up:** the existing, already-structured per-pattern onboarding
  step (name/location-label/approximate-headcount fields — no change,
  already bounded, not narrative).

### 2.2 Workplaces
- Reuses the existing `workplace.Workplace` create/edit flow for any
  additional locations beyond the pattern step — already fully
  structured (name, type, location label, headcount), no change.

### 2.3 People with system access — **new dedicated fact**
- **Question:** "How many people — including contractors or anyone
  else, not just staff — have access to your business systems or
  accounts?"
- **Input:** number — **new field**, `OrganisationProfile.
  people_with_system_access_count` (additive migration). Distinct from
  `staff_count` on purpose: this is the one and only authority for
  `joiner_mover_leaver`'s NOT_APPLICABLE gate (`M008B-QUESTION-CATALOGUE.md` control 7).
- If the answer is exactly `1`, a required, explicit confirmation
  choice is shown before NOT_APPLICABLE becomes selectable on the
  `joiner_mover_leaver` question in Stage 4: "Confirm: no other staff,
  contractor, or shared/service accounts exist for this organisation"
  — a checkbox-style confirmation, not free text.

### 2.4 Remote/offsite access — **new dedicated fact**
- **Question:** "Does anyone access business systems or data from
  outside your normal workplace(s), even occasionally — for example
  from home, while travelling, or on a personal device?"
- **Input:** single choice — **new field**,
  `OrganisationProfile.has_remote_or_offsite_access` (tri-state,
  additive migration):
  | `option_code` | Label | Stored value |
  |---|---|---|
  | `OFFSITE_ACCESS_YES` | Yes, at least sometimes | `yes` |
  | `OFFSITE_ACCESS_NO` | No, never | `no` |
  | `OFFSITE_ACCESS_NOT_SURE` | Not sure | `unknown` |
- Only `OFFSITE_ACCESS_NO` (stored `no`) permits `remote_access_
  control`'s NOT_APPLICABLE option in Stage 4 — never inferred from
  `working_model` or any other fact.

### 2.5 Governance roles
- Reuses the existing `governance.GovernanceRoleAssignment`/
  `OrganisationPerson` role-assignment UI, unchanged in mechanism — one
  page, one reassignment control per role:
  - **Security responsible person** (`ROLE_SECURITY_RESPONSIBLE`)
  - **Policy authoriser** (`ROLE_POLICY_AUTHORISER`)
  - **Senior leadership representative** (`ROLE_SENIOR_LEADERSHIP`)
- A named person's full name is the one other genuinely unavoidable
  textual identifier (per Central Architecture's own exception) —
  already bounded (`OrganisationPerson.full_name`, short text, not
  narrative), **never sent to any AI prompt.**

---

## Stage 3 — Your Technology & Data

**Productivity/email platform, cloud, devices, own software/service,
data categories, assurance status, curated key assets.** Moved here from
Stage 1 per Central Architecture's correction.

### 3.1 Productivity/email platform
- **Question:** "Which productivity/email platform do you mainly use?"
- **Input:** single choice — existing `OrganisationProfile.
  productivity_platform` (`PRODUCTIVITY_PLATFORM_CHOICES`, unchanged):
  Microsoft 365 / Google Workspace / Other / Not confirmed.

### 3.2 Cloud infrastructure
- **Question:** "Do you use any cloud infrastructure providers — for
  example for hosting, servers or storage — beyond your productivity
  platform?"
- **Input:** single choice — existing `OrganisationProfile.
  primary_cloud_provider` (`CLOUD_PROVIDER_CHOICES`, unchanged): None /
  AWS / Azure / GCP / Other / Not confirmed.

### 3.3 Device management
- **Question:** "How are the devices staff use for work managed?"
- **Input:** single choice — existing `OrganisationProfile.
  endpoint_management` (`ENDPOINT_MANAGEMENT_CHOICES`, unchanged):
  Company-managed devices / Bring your own device (BYOD) / Both / Not
  confirmed. (Drives the `endpoint_protection` option-availability
  conditioning in Stage 4, `M008B-QUESTION-CATALOGUE.md` control 3.)

### 3.4 Own software/service
- **Question:** "Does your business develop or host its own software
  or service — for example a product you sell, or a customer-facing
  application?"
- **Input:** single choice — existing `OrganisationProfile.
  develops_hosts_own_software` (tri-state boolean, unchanged): Yes / No
  / Not confirmed.

### 3.5 Data categories handled
- **Question:** "What kinds of data does your business handle?
  (Select all that apply.)"
- **Input:** a checklist of four existing, independent tri-state facts,
  presented together as one structured multi-select screen, each still
  its own field (no change to the underlying model, only presentation):
  - `handles_personal_data` — "Personal data about customers or
    individuals"
  - `handles_confidential_business_data` — "Confidential business
    information (e.g. financial records, contracts)"
  - `handles_payment_card_data` — "Payment card data"
  - `handles_special_category_data` — "Special category data (e.g.
    health, biometric, or similarly sensitive personal data)"
  - Each item individually selectable Yes / No / Not confirmed —
    genuinely independent facts, not a forced single choice.

### 3.6 Assurance status
- **Question:** "Do you hold, or are you working towards, any of the
  following?"
- **Input:** two existing, independent single-choice fields, presented
  together: `cyber_essentials_status` and `iso27001_status`
  (`ASSURANCE_STATUS_CHOICES`, unchanged): Not certified / In progress
  / Certified / Not confirmed, each.

### 3.7 Key assets (the existing Assets-review requirement, folded in here)
- **Question:** "What are your business's key assets — the systems,
  devices, information or services that matter most if something goes
  wrong?"
- **Input:** structured, curated, per asset — reuses the existing
  `key_assets.KeyAsset` model exactly as already corrected in the
  free-text replacement register (Revision 1): a short bounded
  **name** (identifier, e.g. "Finance laptop fleet" — not a
  description), a **category** from the existing fixed
  `CATEGORY_CHOICES` (People / Endpoint / Identity or productivity /
  Cloud service / Business application / Information / Network or
  location / Other), and a **criticality** from the existing fixed
  choices (Low / Medium / High). **No description textarea** — the
  free-text replacement register's correction (removing `KeyAssetForm.
  description` entirely) is the Stage 3 asset-capture mechanism, not a
  separate new one. Customers add as many assets as are genuinely
  relevant; this satisfies the existing Assets-review completion
  milestone (`entitlements.FoundationRequirement` `milestone_assets_
  review`) without reintroducing prose.

---

## What is explicitly NOT asked in Stages 1–3

No open "describe your business," no open "describe your asset," no
open "anything else we should know" field anywhere in these three
stages. Every question above maps to exactly one existing or new
(additive) structured field; nothing is collected that has nowhere
canonical to live.
