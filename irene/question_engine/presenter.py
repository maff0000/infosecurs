"""
Generic, section-agnostic question presenter (WO-IRENE-001 §2.2) - the
"no section-specific branching in the presenter itself" requirement means
every dispatch below is on a question's declared `capability_type` (one
of the four GENERIC, Architecture-approved shapes - Work Order §1a/
Amendment D3), never on `section_code`, a Stage-3 field name, or any
other section-specific detail. Built on the SAME typed-view-model
discipline `foundations_journey.services.get_foundations_question`'s own
return shape already uses for its single-choice case (a plain, server-
shaped object carrying only the fields a template needs) - never a raw
model/dataclass dumped straight into a template context.

This module takes already-resolved data only: a `SectionDefinition` plus
the caller's own answered-value lookup (a plain `Mapping[str, object]`
keyed by `question_code`, or `f"{question_code}:{field_code}"` for a
grouped question's sub-fields, or `question_code` again for a
linked-repeatable-record question's already-fetched rows). It never
queries a database itself and never imports anything from any specific
business-data app - a real domain adapter is responsible for building
that `answered_values` mapping from its own canonical data and passing
it in; this Increment proves the presenter only against the synthetic
fixture in `irene/tests/conftest.py`.
"""
from __future__ import annotations

import dataclasses
from typing import Mapping, Optional

from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD,
    CAPABILITY_TYPE_SINGLE_CHOICE,
    QuestionDefinitionProtocol,
    SectionDefinition,
)


class UnrenderableCapabilityTypeError(ValueError):
    """Raised if a question's `capability_type` is not one of the four
    this presenter knows how to render. Should be unreachable for any
    question that passed `irene.question_engine.registry.
    register_section`'s own validation, but this module never trusts
    that silently - fail loud, never render a blank/guessed panel."""


@dataclasses.dataclass(frozen=True)
class RenderedOption:
    code: str
    label: str
    selected: bool


@dataclasses.dataclass(frozen=True)
class RenderedGroupedField:
    field_code: str
    label: str
    options: tuple[RenderedOption, ...]


@dataclasses.dataclass(frozen=True)
class RenderedQuestion:
    """One question's presenter view-model - the ONE shape every
    capability type renders into, so a template/caller never needs to
    know which concrete capability-type class produced it beyond this
    row's own `capability_type` field (used only to pick which display
    partial to include - still never a section-specific decision)."""

    question_code: str
    title: str
    help_text: str
    capability_type: str
    explain_intent_code: str
    # single_choice
    options: tuple[RenderedOption, ...] = ()
    # grouped_independent_answer - one entry per independently-answered
    # sub-field, each reusing the same RenderedOption shape a top-level
    # single_choice question's own `options` already uses.
    grouped_fields: tuple[RenderedGroupedField, ...] = ()
    # linked_repeatable_record
    record_columns: tuple[str, ...] = ()
    record_rows: tuple[tuple[str, ...], ...] = ()
    manage_route_concept_id: str = ""
    # delegated_workflow
    delegated_route_concept_id: str = ""
    delegated_capability: str = ""


@dataclasses.dataclass(frozen=True)
class RenderedSection:
    section_code: str
    title: str
    catalogue_version: str
    interaction_contract_version: str
    questions: tuple[RenderedQuestion, ...]


def _render_single_choice(question, answered_values: Mapping[str, object]) -> RenderedQuestion:
    selected_code = answered_values.get(question.question_code)
    return RenderedQuestion(
        question_code=question.question_code,
        title=question.title,
        help_text=question.help_text,
        capability_type=question.capability_type,
        explain_intent_code=question.explain_intent_code,
        options=tuple(
            RenderedOption(code=opt.code, label=opt.label, selected=(opt.code == selected_code))
            for opt in question.options
        ),
    )


def _render_grouped_independent_answer(question, answered_values: Mapping[str, object]) -> RenderedQuestion:
    grouped_fields = []
    for field in question.fields:
        selected_code = answered_values.get(f"{question.question_code}:{field.field_code}")
        grouped_fields.append(
            RenderedGroupedField(
                field_code=field.field_code,
                label=field.label,
                options=tuple(
                    RenderedOption(code=opt.code, label=opt.label, selected=(opt.code == selected_code))
                    for opt in field.options
                ),
            )
        )
    return RenderedQuestion(
        question_code=question.question_code,
        title=question.title,
        help_text=question.help_text,
        capability_type=question.capability_type,
        explain_intent_code=question.explain_intent_code,
        grouped_fields=tuple(grouped_fields),
    )


def _render_linked_repeatable_record(question, answered_values: Mapping[str, object]) -> RenderedQuestion:
    rows = answered_values.get(question.question_code)
    if rows is None:
        rows = question.record_rows
    return RenderedQuestion(
        question_code=question.question_code,
        title=question.title,
        help_text=question.help_text,
        capability_type=question.capability_type,
        explain_intent_code=question.explain_intent_code,
        record_columns=tuple(column.label for column in question.record_columns),
        record_rows=tuple(tuple(row) for row in rows),
        manage_route_concept_id=question.manage_route_concept_id,
    )


def _render_delegated_workflow(question, answered_values: Mapping[str, object]) -> RenderedQuestion:
    return RenderedQuestion(
        question_code=question.question_code,
        title=question.title,
        help_text=question.help_text,
        capability_type=question.capability_type,
        explain_intent_code=question.explain_intent_code,
        delegated_route_concept_id=question.delegated_route_concept_id,
        delegated_capability=question.delegated_capability,
    )


_RENDERER_BY_CAPABILITY_TYPE = {
    CAPABILITY_TYPE_SINGLE_CHOICE: _render_single_choice,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER: _render_grouped_independent_answer,
    CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD: _render_linked_repeatable_record,
    CAPABILITY_TYPE_DELEGATED_WORKFLOW: _render_delegated_workflow,
}


def render_question(
    question: QuestionDefinitionProtocol, answered_values: Optional[Mapping[str, object]] = None
) -> RenderedQuestion:
    """Renders exactly one question, dispatching PURELY on its own
    `capability_type` - the one generic property every capability type
    declares (`irene.question_engine.contract`), never on which section
    it belongs to. Raises `UnrenderableCapabilityTypeError` for anything
    else."""
    renderer = _RENDERER_BY_CAPABILITY_TYPE.get(question.capability_type)
    if renderer is None:
        raise UnrenderableCapabilityTypeError(
            f"{question.question_code!r}: no renderer registered for capability_type "
            f"{question.capability_type!r}"
        )
    return renderer(question, answered_values or {})


def render_section(
    section: SectionDefinition, answered_values: Optional[Mapping[str, object]] = None
) -> RenderedSection:
    """Renders every question in `section`, in declared order. The ONLY
    section-specific values used anywhere in this function are
    `section.section_code`/`title`/version fields themselves, carried
    straight through to the view-model unchanged - no branching on
    them."""
    answered_values = answered_values or {}
    return RenderedSection(
        section_code=section.section_code,
        title=section.title,
        catalogue_version=section.catalogue_version,
        interaction_contract_version=section.interaction_contract_version,
        questions=tuple(render_question(question, answered_values) for question in section.questions),
    )


__all__ = [
    "UnrenderableCapabilityTypeError",
    "RenderedOption",
    "RenderedGroupedField",
    "RenderedQuestion",
    "RenderedSection",
    "render_question",
    "render_section",
]
