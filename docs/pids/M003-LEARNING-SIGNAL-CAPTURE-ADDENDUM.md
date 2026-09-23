# M003 — Learning Signal Capture Addendum

**Status:** AUTHORISED — narrow governance addendum, 2026-09-23
**Parent:** `docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md`
**Scope:** clarifies and constrains what M003's activity/history capture must
preserve, for the benefit of a future governed Learning Fabric. **This is
not a new module.** It does not expand M003's user-facing scope, does not
authorise any learning behaviour in M003, and must be read alongside the
M003 PID as one combined implementation authority — not as a separate
module with its own delivery gate.

---

## 1. Purpose

M003 introduces Infosecurs's first append-only activity/history capture
(PID §12). Before that capture design is implemented, Central Architecture
is recording a constraint on its shape: **capture the signal now, in a form
a future governed learning loop could use — do not perform any learning
now, and do not throw away useful correction/provenance signal merely
because M003 itself has no use for it yet.**

## 2. Capture now, learn later

M003 onward must preserve useful decision/outcome history. Infosecurs must
**not** perform autonomous learning in M003, or in any module before a
dedicated, separately-authorised Learning Fabric exists.

The intended future loop:

```text
product event -> structured outcome signal -> offline analysis
             -> proposed change -> GitHub PR -> tests/evals
             -> governed new version
```

Explicitly **not**:

```text
product event -> product silently changes itself
```

Nothing in M003 may close that second loop, in whole or in part.

## 3. Preserve meaningful before/after corrections

Where a meaningful security-state or AI-assisted decision changes, retain
enough structured provenance to later understand:

- what field/conclusion changed;
- previous value;
- new value;
- actor/source of the change;
- time;
- relevant methodology/prompt/model version where AI contributed;
- relevant object/control/risk/questionnaire identifier.

Illustrative examples (not an exhaustive or mandatory checklist for M003 to
build UI around — a guide to what "meaningful" means):

- AI-suggested risk impact/likelihood later edited by a customer;
- AI treatment edited before confirmation;
- a suggested risk dismissed;
- a baseline/control answer changed;
- evidence later contradicting a previously stated control;
- a practitioner override/correction;
- a remediation outcome;
- a later questionnaire answer correction (a future module's concern —
  named here only so the *shape* of capture stays consistent when that
  module arrives).

**Do not merely record a generic event such as `risk_updated` when the
structured delta is practical to retain.** Where an existing M001/M002 view
already has both the previous and new value in hand at the moment of a
meaningful change (e.g. a risk edit view that already loads the risk before
applying form changes), capturing that delta is a small, justified
addition — not a new subsystem.

## 4. Provenance/source distinctions

Preserve distinctions equivalent to:

```text
system_suggested
customer_confirmed
practitioner_confirmed
evidence_supported
externally_observed
```

These do not have to become one universal enum if that would distort an
existing domain's own model — M002's `Risk.source` (`ai`/`manual`) and
`Risk.status` (`draft_ai_suggested`/`confirmed`/`dismissed`) already carry
most of this distinction for the risk domain, for example, and do not need
replacing. What must remain true is that **the provenance semantics stay
recoverable** — a future reader (human or Learning Fabric) can tell a
customer assertion, an AI suggestion, a practitioner conclusion and a
technically-observed fact apart. Where a capture point's existing fields
already make that distinction recoverable, no new field is required merely
to restate it.

## 5. Privacy and tenant boundaries

This addendum does **not** authorise:

- cross-tenant learning;
- cross-tenant aggregation;
- model fine-tuning from customer data;
- exporting customer evidence into a training corpus;
- storing secrets or unnecessary sensitive content in learning records.

Do not duplicate evidence bytes or large free-text artefacts merely for
future learning. Capture structured outcomes/provenance only where useful
— an identifier and a short structured delta, not a copy of the underlying
content. This is the same tenant-isolation discipline M003's own PID §16
already requires everywhere else, restated here so it is unambiguous that
"useful for future learning" is never a reason to weaken it.

## 6. Explicit non-goals (M003, and every module before Learning Fabric is separately authorised)

Do not build:

- a Learning Fabric service;
- an analytics warehouse;
- a feature store;
- a vector database;
- an online reinforcement loop;
- self-modifying prompts;
- automatic methodology changes;
- automatic prompt optimisation;
- model fine-tuning;
- a cross-tenant learning pipeline.

The actual Learning Fabric architecture is deferred until after M005, once
the product has the full loop: `Profile -> Assets -> Controls -> Risks ->
Evidence -> Policy -> Questionnaire -> Corrections/outcomes`.

## 7. M003 implementation consequence

Where M003 introduces activity/history events (PID §12), favour structured
metadata sufficient to preserve meaningful before/after outcomes, per §3
above — this is already broadly consistent with PID §12's own field list
(the event type, actor, occurred_at, relevant identifiers and "small
structured metadata" it already specifies) and does not require a
different shape, only that the *content* of that metadata field
deliberately preserve a real delta where one exists, not just a bare
event-type marker.

Do not redesign M001/M002 wholesale merely to satisfy this addendum. Make
the smallest changes necessary so M003 does not throw away useful
correction/provenance signal that was already available at the point of
change — in particular, since M002's risk-domain corrections (an AI
suggestion later edited, or dismissed, by a customer) are named directly
in §3's examples and M002's own edit/confirm/dismiss views already hold
both the previous and new values at the moment of the change, M003's
activity-logging hook (PID §12) should be extended to also record these as
structured events, using the same logging mechanism M003 builds for its
own domains — not a second, parallel logging system.

## 8. Relationship to the M003 PID

Treat `docs/pids/M003-EVIDENCE-AND-SECURITY-STATE.md` and this addendum
together as the implementation authority for M003. This addendum adds no
new user-facing feature, no new delivery gate, and no new module boundary
— it constrains the shape of capture PID §12 already requires. M003's own
`Definition of PRODUCT_GREEN` (PID §27) is unchanged by this addendum;
satisfying it also satisfies this addendum's §3/§7 consequence, since the
activity/history requirement (PID §27.12) already covers it.
