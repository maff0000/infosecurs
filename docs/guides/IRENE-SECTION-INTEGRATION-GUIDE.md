# IRENE Section Integration Guide

**Audience:** an engineer who has never seen `irene.question_engine`
before and needs to register a new section (a group of questions IRENE
can present, explain, and read answers for) against the generic engine
delivered in WO-IRENE-001 Increment 1.

**Promise this guide keeps:** following the steps below registers a real
section through the documented contract alone — **zero lines changed**
in `irene/question_engine/contract.py`, `registry.py`, `presenter.py`,
or `explain.py`. This is not a claim; it is exactly what
`irene/tests/test_question_engine_second_section_integration.py` does,
and that file's own
`TestSecondSectionProofTouchesZeroLinesOfIncrement1sCoreModules` class
checks it with a real `git diff`. Read that file alongside this guide —
every step below cites the exact line in it that demonstrates the step.

**The four modules you will use, never modify:**

| Module | What you call from it |
|---|---|
| `irene.question_engine.contract` | The dataclasses you build your section and questions out of |
| `irene.question_engine.registry` | `register_section()` — the one way a section becomes real |
| `irene.question_engine.presenter` | `render_section()` / `render_question()` — turns your section into a view-model |
| `irene.question_engine.explain` | `resolve_explanation_skill()` — resolves which skill answers "explain this" for one of your questions |

If a new section genuinely requires changing one of these four files,
stop — that is a sign the contract itself is missing something, which is
an Increment 1 architecture conversation, not a section-registration
task. This guide exists because, for an ordinary new section, that
should never be necessary.

---

## Step 1 — Pick your `section_code` and question codes

- `section_code` must match `^[a-z][a-z0-9_]*$` (lowercase letters,
  digits, underscore, starting with a letter) —
  `irene.question_engine.registry._SAFE_CODE_PATTERN`. Anything else
  (e.g. `"../etc/passwd"`) is rejected at registration time with
  `InvalidSectionDefinitionError`.
- Each `question_code` inside your section must be unique within that
  section. Duplicate codes are rejected outright — nothing is partially
  registered.
- Pick a `catalogue_version` string for your section (its own, following
  the `CATALOGUE_VERSION`-constant convention already used by
  `security_baseline.catalogue`/`questionnaire.catalogue`/
  `risk_register.methodology`). This is **one of Amendment D2's two
  independently-versioned axes** — your section's own question-catalogue
  version. Bump it whenever your section's own question wording/options
  change in a way that matters.
- Leave `interaction_contract_version` at its default
  (`irene.question_engine.contract.INTERACTION_CONTRACT_VERSION`) unless
  you have a specific reason to pin an older one — this is the
  **separate**, second D2 axis: the version of the generic engine shape
  itself. The registry rejects a section built against any value other
  than the engine's current one (`InvalidSectionDefinitionError`,
  "a section built against a stale/foreign contract version is rejected
  outright").

Worked example:
`irene/tests/test_question_engine_second_section_integration.py::STARLIGHT_BAKERY_SECTION_CODE
= "starlight_bakery_section"`, `catalogue_version="1.0.0"`.

## Step 2 — Choose which of the four capability types each question needs

`irene.question_engine.contract` declares exactly four, and only these
four (`KNOWN_CAPABILITY_TYPES`) — you cannot invent a fifth:

| Capability type | Dataclass | Use it when... |
|---|---|---|
| `single_choice` | `SingleChoiceQuestion` | the answer is one pick from a short allowlisted set |
| `grouped_independent_answer` | `GroupedIndependentAnswerQuestion` | several related sub-questions are answered together, each independently of the others |
| `linked_repeatable_record` | `LinkedRepeatableRecordQuestion` | the real answer is a list of records that live in another, existing app's own model — rendered as a read-only summary with a link to manage them elsewhere; this engine never owns that data itself |
| `delegated_workflow` | `DelegatedWorkflowQuestion` | IRENE should explain the question, then hand off entirely to an existing, already-authorised workflow elsewhere — never a duplicate inline editor |

You do not need all four for every section. Pick only the ones your
section's actual questions call for — the second-section proof itself
deliberately uses only three
(`single_choice`, `grouped_independent_answer`, `delegated_workflow`)
and explicitly skips `linked_repeatable_record` because its fictional
scenario has no natural "list of records owned elsewhere" concept
(see that test file's module docstring for the reasoning). Forcing in a
capability type your section does not naturally need is not a stronger
proof — it is padding.

Every capability-type dataclass shares these fields: `question_code`,
`title`, `help_text`, and `explain_intent_code` (defaults to
`IntentCode.EXPLAIN_CONTROL` — leave it at the default unless you have a
specific, already-registered sibling intent code; see Step 5). Each
dataclass is `frozen=True` — build it fully via its constructor, never
mutate a field afterwards.

### `single_choice`

```python
from irene.question_engine.contract import QuestionOption, SingleChoiceQuestion

SingleChoiceQuestion(
    question_code="bakery_oven_type",
    title="What type of oven does the bakery use?",
    help_text="Pick the oven type currently in use on site.",
    options=(
        QuestionOption(code="wood_fired", label="Wood-fired"),
        QuestionOption(code="electric", label="Electric"),
        QuestionOption(code="gas", label="Gas"),
    ),
)
```

### `grouped_independent_answer`

```python
from irene.question_engine.contract import (
    GroupedAnswerField, GroupedIndependentAnswerQuestion, QuestionOption,
)

GroupedIndependentAnswerQuestion(
    question_code="bakery_packaging_specs",
    title="Packaging specifications",
    help_text="Answer each packaging specification independently.",
    fields=(
        GroupedAnswerField(
            field_code="uses_compostable_wrapping",
            label="Uses compostable wrapping?",
            options=(QuestionOption(code="yes", label="Yes"), QuestionOption(code="no", label="No")),
        ),
        GroupedAnswerField(
            field_code="uses_branded_boxes",
            label="Uses branded boxes?",
            options=(QuestionOption(code="yes", label="Yes"), QuestionOption(code="no", label="No")),
        ),
    ),
)
```

### `linked_repeatable_record` (declared shape — see contract.py's own
docstring: this Increment proves the rendering shape only; it does not
implement generic inline CRUD)

```python
from irene.question_engine.contract import LinkedRepeatableRecordQuestion, RecordColumn

LinkedRepeatableRecordQuestion(
    question_code="...",
    title="...",
    help_text="...",
    record_columns=(RecordColumn(code="part_name", label="Part name"), ...),
    record_rows=(("Bracket", "Warehouse A"), ...),   # or leave empty and pass real rows via answered_values at render time — see Step 4
    manage_route_concept_id="task_list",  # must be a REAL, registered, AVAILABLE irene.product_knowledge concept id
)
```

### `delegated_workflow`

```python
from irene.question_engine.contract import DelegatedWorkflowQuestion

DelegatedWorkflowQuestion(
    question_code="bakery_ingredient_sourcing_review",
    title="Ingredient sourcing review",
    help_text="Sourcing compliance is handled by the existing Customer Assurance workflow, not inside this snapshot.",
    delegated_route_concept_id="customer_assurance_upload",  # must be a REAL, registered, AVAILABLE irene.product_knowledge concept id
    delegated_capability="customer_assurance",                # must be a known capability code (irene.product_knowledge.KNOWN_CAPABILITY_CODES)
)
```

**Important for `linked_repeatable_record` and `delegated_workflow`:**
the concept id you reference must already exist, be registered, and be
available in `irene.product_knowledge.PRODUCT_KNOWLEDGE_MAP` (check with
`irene.product_knowledge.get_concept("your_concept_id")` — must not
return `None`). The registry checks this for you and rejects the section
outright if it does not hold
(`InvalidSectionDefinitionError`, "is not a registered, available
Product Knowledge Map concept"). You cannot invent a new concept id here
— register it properly in `irene.product_knowledge` first, as its own,
separate, independently-reviewed change, if it genuinely does not exist
yet.

## Step 3 — Assemble your `SectionDefinition`

```python
from irene.question_engine.contract import SectionDefinition

def build_starlight_bakery_section() -> SectionDefinition:
    return SectionDefinition(
        section_code="starlight_bakery_section",
        title="Starlight Bakery - Kitchen Safety Snapshot",
        catalogue_version="1.0.0",
        required_capabilities=("irene",),  # composed with your destination's own capability, per Amendment D1
        questions=(
            # ... your QuestionDefinition instances from Step 2, in display order ...
        ),
    )
```

`required_capabilities` must only contain codes already known to
`irene.product_knowledge.KNOWN_CAPABILITY_CODES` — an unregistered one is
rejected the same way an unregistered concept id is. Per Amendment D1,
for a real (non-synthetic) section this should compose `"irene"` with
whatever capability code already gates the destination page/data you are
presenting — never a new capability code invented for IRENE itself. The
view layer that actually serves your section is still responsible for
independently rechecking authorisation on every read/explain/save/resume
request — this contract only declares and validates the codes
themselves (see `SectionDefinition`'s own docstring in `contract.py`).

Worked example: `build_starlight_bakery_section()` in
`irene/tests/test_question_engine_second_section_integration.py`.

## Step 4 — Register it

```python
from irene.question_engine.registry import register_section

register_section(build_starlight_bakery_section())
```

That is the **entire** registration mechanism. `register_section()`
fully validates your `SectionDefinition` first
(`irene.question_engine.registry.validate_section_definition`) — every
problem found is collected into one `InvalidSectionDefinitionError`,
never a partial registration — then adds it to the in-code
`SECTION_REGISTRY` dict, keyed by `section_code`. There is no database
table, no migration, no admin UI entry. Calling `register_section()`
twice with the same `section_code` simply replaces the earlier
definition.

**Where to call this for a real (non-synthetic) section:** at import
time, from your own adapter module (e.g.
`irene/question_engine/adapters/your_section.py`), imported once during
Django app startup — mirroring how `irene.skill_loader` loads skill
manifests at import/boot time, never from a request body or any other
untrusted runtime input. **Where to call this for a test:** through a
`pytest` fixture that also deregisters afterwards, so registry state
never leaks between tests — see
`irene/tests/conftest.py::registered_acme_test_section` (Increment 1's
own fixture) and this guide's own worked example,
`irene/tests/test_question_engine_second_section_integration.py::registered_starlight_bakery_section`:

```python
import pytest
from irene.question_engine.registry import deregister_section, register_section

@pytest.fixture
def registered_starlight_bakery_section(starlight_bakery_section):
    register_section(starlight_bakery_section)
    try:
        yield starlight_bakery_section
    finally:
        deregister_section("starlight_bakery_section")
```

To confirm it registered: `irene.question_engine.registry.get_section("your_section_code")`
returns your `SectionDefinition`, and raises
`UnregisteredSectionError` for any code not currently registered — it
never returns `None`. `registered_section_codes()` lists every currently
registered code.

## Step 5 — Render it

```python
from irene.question_engine.presenter import render_section

rendered = render_section(
    section,
    answered_values={
        "bakery_oven_type": "gas",                                      # single_choice: keyed by question_code
        "bakery_packaging_specs:uses_compostable_wrapping": "yes",       # grouped_independent_answer: "question_code:field_code"
        "bakery_packaging_specs:uses_branded_boxes": "no",
        # linked_repeatable_record: question_code -> already-fetched rows (tuple of tuples); omit to fall back to the definition's own record_rows
    },
)
```

`render_section()` dispatches **purely on each question's own
`capability_type`** — never on which section it belongs to — and returns
a `RenderedSection` of `RenderedQuestion` view-models, each carrying only
the fields a template needs (selected options marked, grouped fields
rendered independently, delegated-workflow questions carrying zero
inline-editor fields). You never query a database from inside this
module and you never import anything business-specific into it — your
own adapter/view code is responsible for building the `answered_values`
mapping from whatever real data backs your section, and passing it in.
See `irene.question_engine.presenter`'s own module docstring for the
exact key-shape rules per capability type.

Worked example: every test in
`TestSecondSectionRendersCorrectlyViaTheUnmodifiedGenericPresenter`
in `irene/tests/test_question_engine_second_section_integration.py`.

## Step 6 — Wire on-demand explanations

Every question you built in Step 2 already carries an
`explain_intent_code` (default `IntentCode.EXPLAIN_CONTROL`). To resolve
which skill answers an "explain this" request for one of your questions:

```python
from irene.question_engine.explain import resolve_explanation_skill

skill = resolve_explanation_skill(question)  # None if the intent code is unclear/unrecognised - fail-closed, never a guessed fallback
```

This dispatches through the exact same, already-existing
`irene.skill_router.select_skill()` / `IntentCode.EXPLAIN_CONTROL` path
every other intent-code-driven IRENE request already uses — keyed
**purely by intent code, never by section**. You do not add a new
`IntentCode` member or a new dispatch mechanism for an ordinary new
section; you reuse `EXPLAIN_CONTROL` (or a declared sibling intent code,
if one already exists for your specific case). Building the actual typed
question context to hand to the real AI gateway
(`ai_platform.gateway.LiteLLMGateway.ask_adviser`, per Work Order R1) is
a job for your own adapter/view code, not this module — `explain.py`'s
job stops at "which skill would answer this".

Worked example:
`TestSecondSectionQuestionsDispatchExplanationsByIntentCodeOnly` in
`irene/tests/test_question_engine_second_section_integration.py` —
including a direct proof that a second, unrelated section sharing the
same intent code resolves to the identical skill as the first section
(`test_second_section_resolves_to_the_identical_skill_as_the_first_section`).

## Step 7 — Prove you touched zero lines of IRENE's core

Before you consider your section "integrated", run:

```bash
git diff --stat -- irene/question_engine/contract.py irene/question_engine/registry.py \
    irene/question_engine/presenter.py irene/question_engine/explain.py
```

against whatever base your new section's commits sit on top of. Empty
output is the proof. `irene/tests/test_question_engine_second_section_integration.py::
TestSecondSectionProofTouchesZeroLinesOfIncrement1sCoreModules` runs this
exact check as an executed test (diffing against the merge-base with
this delivery line's own `wo/IRENE-001-pilot` integration branch, when
resolvable, falling back to `HEAD`) rather than leaving it as a verbal
claim — copy that test's shape into your own section's test suite if you
want the same guarantee checked automatically for your own change too.

---

## Summary — the whole formula in one place

1. Pick a `section_code` (safe identifier) and a `catalogue_version`.
2. Build each question as one of the four `contract.py` dataclasses
   (`SingleChoiceQuestion`, `GroupedIndependentAnswerQuestion`,
   `LinkedRepeatableRecordQuestion`, `DelegatedWorkflowQuestion`) — only
   the ones your section actually needs.
3. Assemble a `SectionDefinition` from them.
4. `register_section(your_definition)` — once, at import time for a real
   section, or inside a register/deregister test fixture.
5. `render_section(your_definition, answered_values={...})` to get a
   view-model; `resolve_explanation_skill(question)` to resolve an
   on-demand explanation.
6. Run the `git diff` scope check against `contract.py`/`registry.py`/
   `presenter.py`/`explain.py` — it should be empty.

Every step above is cited against a real, executed test in
`irene/tests/test_question_engine_second_section_integration.py` — this
guide describes nothing that file does not already do.
