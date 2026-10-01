# M008 — Free-Text Replacement Register (extends WI0 inventory)

**Status:** DESIGN ARTEFACT — extends `docs/evidence/M008-PREFLIGHT-AND-FORM-INVENTORY.md`
(WI0, already merged) with the full migration/replacement decision for
each of the 12 FOUNDATION-reachable narrative fields that inventory found.
Nothing here is implemented.

For every row: current field/route, why it violates the no-narrative
doctrine, the proposed replacement interaction, new canonical storage
destination, whether the old field/data remains for historical
compatibility, whether legacy values stay visible, the migration
requirement, downstream dependencies, and any AI dependency removed.

## 1. `organisations.OrganisationProfileForm.description`

- **Route:** `organisations:profile`
- **Why it violates:** open narrative business description.
- **Replacement interaction:** finite sector/business-type choice list +
  short bounded free-text "what you do, in a few words" (max ~60 chars,
  a label not a description) — see M008B §B3 Business.
- **New canonical destination:** a new typed `OrganisationProfile.sector`
  enum field (additive migration) + the existing `description` field
  repurposed as the bounded short label (max_length tightened via
  `clean_description`, not a new column).
- **Old field retained for history:** Yes — `description` itself is
  reused, not dropped; existing long values become read-only on this one
  organisation until the customer re-saves (no forced truncation).
- **Legacy values visible/read-only:** Yes, shown as-is until re-saved.
- **Migration requirement:** one additive migration (`sector` field,
  default UNKNOWN); no backfill guess at existing customers' sector
  (none exist — Beta has no real customers yet).
- **Downstream dependencies:** `policy.grounding.build_policy_grounding_payload`
  reads `OrganisationProfile` fields — must add `sector` to its allowed
  projection list once approved; `description`'s existing inclusion stays,
  now semantically a short label rather than free prose.
- **AI dependency removed:** none (this field was never sent to any AI
  prompt as grounding — confirmed by WI0 inventory; `commercial_security_driver`
  below is the one that was).

## 2. `organisations.OrganisationProfileForm.commercial_security_driver`

- **Route:** `organisations:profile`
- **Why it violates:** open narrative "why security matters to you."
- **Replacement interaction:** finite choice list (e.g. "A customer/
  supplier asked us to", "We handle sensitive data", "We want to reduce
  risk generally", "Required for a certification/contract", "Not sure
  yet") — M008B §B3 already proposes this shape.
- **New canonical destination:** convert the existing `CharField` to a
  `ChoiceField`-backed `CharField` with a fixed, versioned choice set
  (additive — same column, new `choices=` kwarg + a data migration
  mapping any existing free-text value to the closest new choice, or to
  "Not sure yet" if no reasonable mapping exists).
- **Old field retained for history:** Yes, same column.
- **Legacy values visible/read-only:** mapped forward during migration,
  not left dangling as an un-selectable value.
- **Migration requirement:** one data migration doing the best-effort
  mapping above; genuinely safe only because Beta has zero real customer
  rows today — flagged explicitly as a one-time, pre-production-data
  operation, not a general pattern for later free-text fields once real
  customer data exists.
- **Downstream dependencies:** `policy.grounding` reads this field for
  policy purpose/scope framing — the choice-list value must still satisfy
  that grounding contract; no AI prompt change needed since the value
  stays a string.
- **AI dependency removed:** this field was previously forwarded to
  `policy_generation_v2`'s grounding payload as free text; it becomes a
  bounded enum value instead — the AI no longer receives open customer
  prose for this field.

## 3. `key_assets.KeyAssetForm.description`

- **Route:** `key_assets:create`, `key_assets:edit`
- **Why it violates:** open narrative asset description.
- **Replacement interaction:** curated asset-category tick list (already
  exists via `category`) + a short bounded label field (reuse `name`,
  tightened) — remove the separate `description` textarea entirely for
  new assets; M008B §B3 Assets: "optional bounded asset label."
- **New canonical destination:** no new field — `name` already exists
  and is bounded; `description` is dropped from the create/edit form.
- **Old field retained for history:** Yes, the column stays on
  `KeyAsset` (still present in the DB), simply no longer writable via
  the form.
- **Legacy values visible/read-only:** Yes — existing `description` values
  display read-only on the asset detail page, labelled "legacy note",
  never editable again.
- **Migration requirement:** none (no column change, only a form-field
  removal).
- **Downstream dependencies:** `risk_register.scenario_engine` reads
  `KeyAsset.category`/`criticality`, never `description` — confirmed no
  functional dependency breaks.
- **AI dependency removed:** none (this field was never AI-grounded).

## 4. `evidence._EvidenceCommonFieldsMixin.description`

- **Route:** `evidence:upload`, `evidence:add_reference`
- **Why it violates:** open narrative description alongside a file/URL
  that is itself the legitimate exception.
- **Replacement interaction:** a short, bounded "what this shows" label
  (max ~80 chars) replacing the multi-line textarea — the file/URL
  carries the actual content, the label is just a human-readable index
  entry, not a narrative.
- **New canonical destination:** same `description` column, tightened to
  a single-line `CharField`-rendered widget (no column type change
  needed — Django's `TextField` can render as a single-line input; the
  DB column itself doesn't need to shrink).
- **Old field retained for history:** Yes.
- **Legacy values visible/read-only:** Yes, shown as-is (existing longer
  values are not truncated on display, only new input is bounded going
  forward).
- **Migration requirement:** none (widget-only change).
- **Downstream dependencies:** `evidence.link_services`, `security_state`'s
  read-only aggregation layer — neither depends on `description`'s length
  or structure, confirmed no break.
- **AI dependency removed:** none.

## 5. `evidence.ControlEvidenceLinkForm.rationale`

- **Route:** `evidence:link_control`
- **Why it violates:** open narrative "why this evidence supports/
  contradicts" rationale, optional, max 500 chars.
- **Replacement interaction:** a small, finite rationale-category choice
  list (e.g. "Directly demonstrates the control", "Partially covers it",
  "Provides context only", "Contradicts the current answer") replacing
  free text.
- **New canonical destination:** `ControlEvidenceLink.rationale` column
  repurposed to store the selected category's stable code (additive —
  same column, new choices).
- **Old field retained for history:** Yes, same column; existing free-text
  values displayed read-only.
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none required for existing rows (no forced
  re-categorisation of history; a best-effort "Context only" default for
  old rows is the only safe automatic mapping, applied via one data
  migration).
- **Downstream dependencies:** `security_state`'s aggregation reads
  `ControlEvidenceLink.relationship`, not `rationale` — no break.
- **AI dependency removed:** none.

## 6. `risk_register.RiskEditForm.threat`

- **Route:** `risk_register:edit`
- **Why it violates:** user-authored threat prose, explicitly named in
  M008B §B3 Risk as something to replace with the governed scenario
  catalogue.
- **Replacement interaction:** remove this field from the edit form
  entirely for scenario-originated risks — `threat_event` is already a
  deterministic property of the matched `risk_register.methodology`
  scenario (§M008B's own catalogue linkage); the customer selects/
  confirms/dismisses, never rewrites the threat description.
- **New canonical destination:** none new — the scenario's own
  `threat_event` field (already exists in `MethodologyScenario`) becomes
  the sole source; `Risk.threat` keeps its DB column for the (today
  dormant) possibility of a fully custom, non-scenario-originated risk,
  but the standard Foundation-tier edit form no longer offers a textarea
  for it.
- **Old field retained for history:** Yes, column stays; read-only display
  of whatever text is already on existing rows.
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none.
- **Downstream dependencies:** `risk_register.grounding` (AI
  interpretation payload) currently reads `Risk.threat` as part of its
  structured projection — must confirm it still receives a value (the
  scenario's own `threat_event`, copied at instantiation time into
  `Risk.threat` exactly as today, so no grounding-contract change
  needed, only the *edit path* changes).
- **AI dependency removed:** none directly (grounding already reads the
  stored field, regardless of whether a human or the scenario engine
  wrote it) — but removing the free-edit path also removes the one place
  a customer could have introduced adversarial/unvetted prose into a
  field that reaches an AI prompt, which is itself a security-hardening
  side effect worth recording even though not an "AI call removed."

## 7. `risk_register.RiskEditForm.vulnerability`

Same analysis and replacement plan as item 6 above (`threat`) — the
scenario's own `vulnerability` wording (already state-dependent, via
`ControlGapWording`) replaces the free-edit path identically. Not
repeated field-by-field; see item 6 for the full structure.

## 8. `risk_register.RiskEditForm.rationale`

- **Route:** `risk_register:edit`
- **Why it violates:** free-text rationale for impact/likelihood ratings.
- **Replacement interaction:** a small set of predefined rationale notes
  tied to the actual impact/likelihood value selected (e.g. "Would affect
  a system handling confidential data" for higher impact) — a
  closed-form choice, not free text; customer still picks the 1-5
  impact/likelihood rating itself (unchanged, already a bounded choice).
- **New canonical destination:** same `rationale` column, repurposed to a
  selected-code value, per item 5's pattern.
- **Old field retained for history:** Yes.
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none required.
- **Downstream dependencies:** `risk_register.grounding` reads this field
  too — same "already receives whatever's stored" reasoning as item 6.
- **AI dependency removed:** same hardening side-effect as item 6.

## 9. `risk_register.RiskEditForm.proposed_treatment`

- **Route:** `risk_register:edit`
- **Why it violates:** free-text treatment description, explicitly named
  in M008B §B3 Risk ("selectable owner/priority/treatment options").
- **Replacement interaction:** the scenario's own `suggested_treatment`
  (already deterministic) becomes the default, with a small set of
  treatment-category choices (Accept / Mitigate via suggested action /
  Mitigate via custom remediation already created / Transfer) replacing
  the open text.
- **New canonical destination:** same column, repurposed, per item 5's
  pattern; the actual remediation detail lives in `remediation.
  RemediationAction.description` (also being replaced — see item 10) or
  a pointer to it.
- **Old field retained for history:** Yes.
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none required.
- **Downstream dependencies:** `remediation.services.
  create_from_risk`-style linkage (if it exists) must be checked for
  whether it reads `Risk.proposed_treatment` as a seed value for a new
  `RemediationAction` — confirm during implementation, not assumed here.
- **AI dependency removed:** same hardening side-effect as item 6.

## 10. `remediation.RemediationActionForm.description`

- **Route:** `remediation:create`, `remediation:create_from_risk`,
  `remediation:edit`
- **Why it violates:** open-ended action description, explicitly named
  in M008B §B3 Remediation ("curated actions tied to a specific
  control/scenario... not an open-ended form").
- **Replacement interaction:** a curated action-template list, one per
  risk scenario (e.g. for `endpoint_device_encryption_loss_theft`: "Enable
  full-disk encryption" — the scenario's own `suggested_treatment`,
  already deterministic text), selectable and optionally customised via
  a short bounded label, not an open description.
- **New canonical destination:** same `description` column, now
  populated by default from the matched scenario's `suggested_treatment`
  (deterministic default), editable only to a bounded label-length
  override, not arbitrary length.
- **Old field retained for history:** Yes.
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none required.
- **Downstream dependencies:** none identified beyond the form itself.
- **AI dependency removed:** none (never AI-grounded).

## 11. `security_baseline.BaselineAssessmentForm.note__<question_key>`

- **Route:** `security_baseline:baseline`
- **Why it violates:** **the primary, named target** — the per-question
  free-text note, already flagged in the form's own module docstring as
  "the customer narrative field to retire from Foundation-facing UI."
- **Replacement interaction:** entirely replaced by the structured
  conditional follow-up questions defined per-control in M008B §1-12
  above (e.g. the bounded "Which groups?"/"What's not covered?" short
  identifiers) — there is no general-purpose note field in the new
  design at all; every piece of nuance a customer previously might have
  put in free text now has its own named, bounded, versioned follow-up
  question instead.
- **New canonical destination:** the new per-control `AnswerSelectionDetail`-
  style provenance table proposed in M008B §B4 (selected option code +
  any bounded follow-up value), never a second source of truth for
  `BaselineAnswer.answer` itself.
- **Old field retained for history:** Yes — `BaselineAnswer.note` stays
  as a column; existing values display read-only on the control's detail
  view, explicitly labelled "earlier note (no longer editable)."
  stays as a column; existing values display read-only on the control's
  detail view, explicitly labelled "earlier note (no longer editable)."
- **Legacy values visible/read-only:** Yes.
- **Migration requirement:** none required for the column itself (no
  schema change needed to retire the *form field* — the new
  `AnswerSelectionDetail` model is itself a new, additive migration, per
  M008B §B4.1).
- **Downstream dependencies:** confirmed via WI0/M008A recon —
  `entitlements.metrics` never reads `BaselineAnswer.note`, only
  `.answer`; no functional dependency breaks.
- **AI dependency removed:** none (never AI-grounded).

## 12. `policy.PolicyVersionEditForm` (one textarea per section)

- **Route:** `policy:version_edit`
- **Why it violates:** **the other primary, named target** — "one big
  textarea per section," explicitly named in M008D §D4 ("No per-section
  textarea for Foundation customer").
- **Replacement interaction:** entirely replaced by the structured
  preview/approve/flag-for-review UX (M008D §D4) — Foundation-tier
  customers never see a section editor at all; they see rendered
  preview text (deterministically composed from clauses, per M008D's
  new architecture) plus **Return to question** / **Flag for review** /
  **Approve** actions.
- **New canonical destination:** none — this form is retired for
  Foundation tier entirely, not repurposed. (M008D §D4's own escape
  valve — a future, separately-authorised practitioner-only controlled
  revision mechanism outside the standard flow — is explicitly out of
  this register's scope, per that section's own wording.)
- **Old field retained for history:** The underlying `PolicyVersion.
  sections` JSON field stays exactly as today (unchanged schema,
  unchanged immutability guarantees) — only the *editing form* is
  retired, not the data model.
- **Legacy values visible/read-only:** Any already-approved
  `PolicyVersion` continues to render and download exactly as today —
  no change to historical artefacts.
- **Migration requirement:** none to the data model; the `policy_edit`
  view itself is retired/replaced for Foundation tier (implementation
  detail for the actual WI, not a schema migration).
- **Downstream dependencies:** `policy.services.generate_policy_draft`'s
  existing AI-generation call becomes the *non-default* exception path
  (M008D §D3.4) rather than the default — see the AI/cost inventory
  below for the full before/after call accounting.
- **AI dependency removed:** the default, routine policy-drafting path
  currently makes one `LiteLLMGateway` generation call per draft; the
  proposed deterministic clause-selection pipeline (M008D §D3.2) makes
  **zero** calls for the default path. This is the single largest AI-call
  reduction in the whole M008 redesign.

## Summary

| # | Field | AI-grounded today? | AI call removed by this change? |
|---|---|---|---|
| 1 | `description` (profile) | No | No |
| 2 | `commercial_security_driver` | Yes (policy grounding) | Field bounded, not removed from grounding |
| 3 | `KeyAsset.description` | No | No |
| 4 | `evidence.description` | No | No |
| 5 | `ControlEvidenceLink.rationale` | No | No |
| 6-9 | `Risk.threat/vulnerability/rationale/proposed_treatment` | Yes (risk interpretation grounding) | Hardens the grounding input path; no call count change |
| 10 | `RemediationAction.description` | No | No |
| 11 | `BaselineAnswer.note` | No | No |
| 12 | `PolicyVersionEditForm` (whole form) | Yes (generation) | **Yes — removes the default generation call entirely** |
