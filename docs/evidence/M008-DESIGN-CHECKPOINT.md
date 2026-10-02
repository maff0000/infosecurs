# M008 — Design Artefact Checkpoint Package (Revision 2)

**Status:** DESIGN ARTEFACT PHASE, Revision 2. Supersedes
`M008-DESIGN-CHECKPOINT.md` (Revision 1, merged via PR #84). Overall
design direction is **APPROVED** by Central Architecture/Product
Authority; this revision implements a bounded correction pass on
Revision 1, not a reinterpretation. Nothing described here is
implemented — substantive M008B/C/D implementation remains blocked
pending explicit approval of this revision.

**M008A (the dev-only Customer Zero reset) remains separately CLOSED
PRODUCT_GREEN** and operational on the dev stack, unaffected by this
design phase.

## What changed in this revision — summary

1. **Every bounded free-text follow-up removed** (MFA "Which groups?",
   backup "What's covered?", business "what you do in a few words",
   evidence "what this shows", remediation custom labels). Replaced by
   finite choices or omitted entirely. Only legal/trading name and
   named-person identity remain textual — never sent to AI.
2. **NOT_APPLICABLE eligibility corrected.** Removed entirely for
   `device_encryption`, `endpoint_protection`,
   `security_awareness_training`, `privileged_access_separation`.
   `remote_access_control` and `joiner_mover_leaver` keep NOT_APPLICABLE
   but re-gated on two new, dedicated, explicitly-confirmed structured
   facts — never on `staff_count`, cloud-provider selection, or office-
   working status alone.
3. **New structured-question methodology version**
   (`FOUNDATIONS_QUESTION_METHODOLOGY_VERSION`), separate from the
   unchanged `security_baseline.CATALOGUE_VERSION`. Every answer option
   now has a stable `option_code`; provenance persists control key,
   option code, derived canonical answer, and methodology version.
4. **Option-level policy provenance** applied consistently across all 12
   controls — every control with more than one option mapping to the
   same canonical state keeps each option's own distinct downstream
   wording (Central Architecture's own named example,
   `BACKUPS_RESTORE_UNTESTED` vs. `BACKUPS_COVERAGE_PARTIAL`,
   implemented exactly, plus four more controls with the same pattern).
5. **Exact Stage 1–3 question catalogue produced in full** — nothing
   left to Engineer implementation. Technology/data questions moved
   from Stage 1 to Stage 3 as instructed; the existing Assets-review
   requirement folded into Stage 3 using curated categories only.
6. **Progress semantics corrected** to REVIEWED/confirmed terminology —
   `12 of 12 reviewed · 3 still need confirmation`, never a bare
   "Complete" badge while UNKNOWN remains.
7. **Risk presentation corrected** — confirmed risks (NO/PARTIAL)
   explicitly separated from items needing confirmation (UNKNOWN):
   `3 security risks identified · 2 things still need confirming`.
8. **Policy architecture redesigned as primarily NORMATIVE.** The
   distributable PDF states fixed commitments, identical wording for
   every organisation regardless of current state. Current-state
   gaps/actions move to a separate **Implementation status** record,
   shown only in the in-product review screen, never the downloadable
   PDF. Governance roles named by their real business-facing titles
   (Security responsible person / Policy authoriser / Senior
   leadership) — never Infosecurs's internal "Account Holder" term.
9. **Policy readiness gate redesigned** — reviewed-not-perfect
   approval, UNKNOWN never silently converted, approval explicitly does
   not imply compliance, Foundations Completion remains ungated by
   policy approval.
10. **Approved UX decisions preserved unchanged**: six-stage split,
    Home-first Continue action, meaningful Needs Attention labels
    (superseding M007's literal "click here"), zero-routine-LLM design.

## Revised artefacts

| Artefact | File | What changed |
|---|---|---|
| Question catalogue (Stage 4, all 12 controls) | `docs/design/M008B-QUESTION-CATALOGUE.md` | Option codes added; NOT_APPLICABLE corrected; follow-ups removed; option-level provenance documented |
| **New:** exact Stage 1–3 catalogue | `docs/design/M008B-STAGES-1-3-CATALOGUE.md` | New deliverable — every Stage 1/2/3 question, options, and canonical field mapping in full |
| Free-text replacement register | `docs/design/M008-FREE-TEXT-REPLACEMENT-REGISTER.md` | Rows 1, 4, 10, 11 corrected in place to remove reintroduced free text |
| UX flow / conditional map / Home / progress / risk presentation | `docs/design/M008C-UX-FLOW-DESIGN.md` | Conditional map's two NOT_APPLICABLE rows corrected; new §6 (progress semantics) and §7 (risk presentation) added |
| Policy architecture | `docs/design/M008D-POLICY-ARCHITECTURE.md` | Rewritten: NORMATIVE/implementation-status split, governance-role wording, policy readiness gate |
| Sample policies | `docs/design/M008D-SAMPLE-POLICIES.md` | Rewritten to describe the two-document-per-scenario output |
| Truth matrix | `docs/design/M008D-POLICY-TRUTH-MATRIX.md` | Rewritten: fixed normative clause table + option-level implementation-status table |
| AI/cost inventory | `docs/design/M008-AI-COST-INVENTORY.md` | **Unchanged** — zero-routine-LLM target already met in Revision 1, confirmed still true |
| Prototype | `docs/design/prototype.html` + Artifact (same URL, new version) | Backup question now shows granular options with no follow-up; progress lines use reviewed/confirmed copy; Risks & Actions screen split into two groups; Policy screen split into downloadable-policy + implementation-status sections |
| Screenshots | `docs/design/screenshots/` (21 PNGs) | Regenerated from the Revision 2 prototype at 375/768/1280px |
| Sample policy PDFs | `docs/design/policies/M008D-sample-policy-{a,b,c}.pdf` | Regenerated — normative-only content, real governance-role names |
| **New:** implementation status PDFs | `docs/design/policies/M008D-implementation-status-{a,b,c}.pdf` | New artefact — the gap/action record kept separate from the distributable policy, per option_code |

## Clickable prototype (updated, same URL)

**URL:** https://claude.ai/artifact/JHveVvgY4qb2BvVQabpZy5 (Version 3)

Same screens as Revision 1, now reflecting every correction above: the
backup question (representative conditional question) shows four
granular options and "Not sure," no follow-up field; the Stage 4
progress line reads "4 of 12 reviewed · 1 still needs confirming"; the
Risks & Actions screen shows "Confirmed risks" and "Things still needing
confirmation" as two explicit groups with the exact headline copy; the
Policy screen shows the normative-only downloadable policy and a
visually separate Implementation status section, never merged.

## Sample policies (regenerated)

Each scenario now has **two** real rendered PDFs rather than one blended
document:

- `M008D-sample-policy-{a,b,c}.pdf` — the distributable policy, fixed
  normative commitments, identical structure across every scenario,
  real named governance role-holders (not "Account Holder").
- `M008D-implementation-status-{a,b,c}.pdf` — internal-only, per-control
  current state keyed to exact `option_code`, explicitly marked
  "not the distributable policy."

Scenario C's policy PDF demonstrates the key structural consequence of
the normative-first design: the fixed commitment clauses **do render**
even for a freshly-reset organisation (they don't depend on confirmed
facts), while the document is still headed "Preview — not approvable"
because the policy readiness gate's business-context and reviewed-
controls conditions aren't met; its implementation-status record shows
all 12 controls `NOT_YET_CONFIRMED`.

## Known design tradeoffs / items still requiring Product Authority decision

Carried from Revision 1, unaffected by this correction pass:
1. Stage split (Business vs. Technology & Data as two stages) —
   recommended, your call.
2. No control weight/scenario/policy-section renamed — confirmed again
   in this revision; any future change is a separate methodology
   decision.
3. Sample policies render at 2 pages each, within the existing 2–4 page
   target — no breach proposed.

## What happens next

Per the master PID's own gate: **STOP here.** No M008B/C/D
implementation begins until Matt/Product Authority explicitly approves
this revision.
