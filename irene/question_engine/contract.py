"""
Typed, versioned contract for IRENE's generic question-engine
(WO-IRENE-001 §2.2; PID Amendment "What this Amendment authorises" item
1; Amendment D2/D3). Built with ZERO knowledge of Stage 3 or the
`organisations` app - every type here is deliberately usable by ANY
future registered section, proven by the synthetic fixture this
package's own tests exercise (`irene/tests/conftest.py::
build_acme_test_section`, used by `irene/tests/
test_question_engine_registry.py`/`test_question_engine_presenter.py`),
never a hidden Stage-3 assumption baked into a field name or default.

Two independently-versioned axes (Amendment D2 - "Two independently-
versioned axes, not one"):

  - `SectionDefinition.catalogue_version` - this ONE section's own
    question-catalogue version, following the `CATALOGUE_VERSION`-
    constant convention `security_baseline.catalogue`/`questionnaire.
    catalogue`/`risk_register.methodology` already use.
  - `INTERACTION_CONTRACT_VERSION` (module-level, below) - the version of
    THIS generic contract/engine shape itself, shared by every section
    registered against it, bumped only when this module's own shapes
    change in an incompatible way. `irene.question_engine.registry`
    rejects any `SectionDefinition` whose own
    `interaction_contract_version` does not match this module's current
    value - a section built against a stale/foreign contract shape is
    refused at registration time, never silently accepted (Work Order
    §1a C2's "definition compatibility" checks apply to THIS axis; the
    separate, canonical-state stale-write check Amendment D2/Work Order
    R2 describes is a distinct, Increment-2-only, guarded-save-path
    concern this module has no part in).

Four declared adapter capability types (Amendment D1/D3's architecture
decision, PID Amendment "first implementation target" paragraph):
single-choice, grouped-independent-answer, linked-repeatable-record, and
delegated_workflow. The latter two are DECLARED SHAPES only in this
Increment - `irene/tests/test_question_engine_presenter.py`'s synthetic
fixture exercises all four so the generic presenter is proven against the
full declared contract before any real adapter (Increment 2) exists, but
this module does not implement linked-record CRUD or a real delegated
workflow of its own (Amendment D3: "a declared delegation shape, not a
stand-in for one").
"""
from __future__ import annotations

import dataclasses
from typing import Protocol, Union, runtime_checkable

from irene.models import IntentCode

# Bumped only when this module's own dataclass shapes change
# incompatibly - the SEPARATELY-versioned generic interaction contract
# axis (Amendment D2), never conflated with any one section's own
# `catalogue_version` below.
INTERACTION_CONTRACT_VERSION = "1.0.0"

CAPABILITY_TYPE_SINGLE_CHOICE = "single_choice"
CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER = "grouped_independent_answer"
CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD = "linked_repeatable_record"
CAPABILITY_TYPE_DELEGATED_WORKFLOW = "delegated_workflow"

# The full, fixed allowlist of capability types this engine knows how to
# register/render - Amendment D1/D3's architecture decision names exactly
# these four, never a fifth a future adapter could invent unilaterally.
KNOWN_CAPABILITY_TYPES = frozenset(
    {
        CAPABILITY_TYPE_SINGLE_CHOICE,
        CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
        CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD,
        CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    }
)


@runtime_checkable
class QuestionDefinitionProtocol(Protocol):
    """The structural shape every capability type below satisfies -
    named explicitly as a `Protocol` (WO-IRENE-001 §2.2: "typed
    dataclasses/Protocols for... `QuestionDefinition`"), so
    `irene.question_engine.registry`/`presenter`/`explain` can type-hint
    against "any registered question", never against one concrete
    capability-type class."""

    question_code: str
    title: str
    help_text: str
    capability_type: str
    explain_intent_code: str


@dataclasses.dataclass(frozen=True)
class QuestionOption:
    """One allowlisted answer option - never free text (the same
    "canonical field, no free-text alternative" discipline `irene.forms.
    AskForm`'s own `intent_code` field already applies)."""

    code: str
    label: str


@dataclasses.dataclass(frozen=True)
class GroupedAnswerField:
    """One independently-answerable sub-field of a
    `grouped_independent_answer` question - several related fields
    presented together, each with its own allowlisted options, each
    saved independently of the others (never one sub-field's save
    overwriting a sibling's). A real adapter's own real sub-fields are an
    Increment 2 concern; this type only declares the generic shape."""

    field_code: str
    label: str
    options: tuple[QuestionOption, ...]


@dataclasses.dataclass(frozen=True)
class RecordColumn:
    """One column of a `linked_repeatable_record` question's declared
    record shape - e.g. "name", "owner" - describing what each linked
    record looks like without this engine ever owning the data itself
    (Amendment D3: no second Key-Assets-shaped table; a real adapter's
    rows come from whatever existing model it already owns)."""

    code: str
    label: str


@dataclasses.dataclass(frozen=True)
class SingleChoiceQuestion:
    """One answer, chosen from a short allowlisted set (the PID
    Amendment's own "single-choice" shape) - this Increment declares the
    shape only, against a synthetic fixture, never against any real
    Stage 3 field."""

    question_code: str
    title: str
    help_text: str
    options: tuple[QuestionOption, ...]
    explain_intent_code: str = IntentCode.EXPLAIN_CONTROL
    capability_type: str = dataclasses.field(default=CAPABILITY_TYPE_SINGLE_CHOICE, init=False)


@dataclasses.dataclass(frozen=True)
class GroupedIndependentAnswerQuestion:
    """Several related sub-fields presented together, each answered
    independently - the PID Amendment's own "grouped-independent-answer"
    shape."""

    question_code: str
    title: str
    help_text: str
    fields: tuple[GroupedAnswerField, ...]
    explain_intent_code: str = IntentCode.EXPLAIN_CONTROL
    capability_type: str = dataclasses.field(
        default=CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER, init=False
    )


@dataclasses.dataclass(frozen=True)
class LinkedRepeatableRecordQuestion:
    """A declared shape for a question whose real answer is a list of
    repeatable records living in another, existing app's own model (the
    PID Amendment's own example: Key Assets) - rendered as a bounded,
    read-only summary table (declared `record_columns` + already-fetched
    `record_rows`, never a live query this generic engine runs itself)
    plus an optional `manage_route_concept_id` link to manage the records
    elsewhere. Increment 1 proves this shape only against a synthetic
    fixture - Amendment D3 scopes any REAL repeatable-record adapter to a
    future increment; this is a declared shape for future use, not a
    working inline CRUD implementation."""

    question_code: str
    title: str
    help_text: str
    record_columns: tuple[RecordColumn, ...]
    record_rows: tuple[tuple[str, ...], ...] = ()
    manage_route_concept_id: str = ""
    explain_intent_code: str = IntentCode.EXPLAIN_CONTROL
    capability_type: str = dataclasses.field(
        default=CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD, init=False
    )


@dataclasses.dataclass(frozen=True)
class DelegatedWorkflowQuestion:
    """Amendment D3's approved shape for a question IRENE explains and
    hands off entirely to an existing, already-authorised workflow
    elsewhere (the PID Amendment's own example: Key Assets, question
    3.7) - never a duplicate inline editor. `delegated_capability` is the
    ADDITIONAL entitlement code (on top of whatever the section itself
    already requires) the real destination workflow enforces (Amendment
    D1's "a third, independently-checked gate... not a substitute for
    either") - this Increment declares the field only; no real
    capability/route is registered against it here beyond what
    `irene.question_engine.registry` can independently verify against
    the existing, generic `irene.product_knowledge` registry."""

    question_code: str
    title: str
    help_text: str
    delegated_route_concept_id: str
    delegated_capability: str
    explain_intent_code: str = IntentCode.EXPLAIN_CONTROL
    capability_type: str = dataclasses.field(default=CAPABILITY_TYPE_DELEGATED_WORKFLOW, init=False)


QuestionDefinition = Union[
    SingleChoiceQuestion,
    GroupedIndependentAnswerQuestion,
    LinkedRepeatableRecordQuestion,
    DelegatedWorkflowQuestion,
]


@dataclasses.dataclass(frozen=True)
class SectionDefinition:
    """One registered section - a typed, versioned, allowlisted bundle of
    questions (PID Amendment: "a typed, versioned, allowlisted
    section/question contract"). `section_code` is this section's own
    stable identifier (Amendment D2's first versioning axis, paired with
    `catalogue_version`); `interaction_contract_version` records which
    version of THIS module's own shapes the section was built against
    (D2's second, separately-versioned axis) - `irene.question_engine.
    registry` is the one place both are checked before a section is ever
    allowed to register (see that module). `required_capabilities` is
    the composed entitlement set (Amendment D1: "both the `irene`
    capability code and the destination section's own existing code")
    the real view-layer gate must independently recheck on every
    read/explain/save/resume - this Increment only declares and
    validates the codes themselves against the existing, generic
    `irene.product_knowledge.KNOWN_CAPABILITY_CODES` allowlist; wiring a
    real per-request recheck is left to the real adapter/view code that
    registers a real section (Increment 2)."""

    section_code: str
    title: str
    catalogue_version: str
    questions: tuple[QuestionDefinition, ...]
    interaction_contract_version: str = INTERACTION_CONTRACT_VERSION
    required_capabilities: tuple[str, ...] = ()


__all__ = [
    "INTERACTION_CONTRACT_VERSION",
    "CAPABILITY_TYPE_SINGLE_CHOICE",
    "CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER",
    "CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD",
    "CAPABILITY_TYPE_DELEGATED_WORKFLOW",
    "KNOWN_CAPABILITY_TYPES",
    "QuestionDefinitionProtocol",
    "QuestionOption",
    "GroupedAnswerField",
    "RecordColumn",
    "SingleChoiceQuestion",
    "GroupedIndependentAnswerQuestion",
    "LinkedRepeatableRecordQuestion",
    "DelegatedWorkflowQuestion",
    "QuestionDefinition",
    "SectionDefinition",
]
