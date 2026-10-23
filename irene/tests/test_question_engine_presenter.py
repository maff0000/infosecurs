"""
WO-IRENE-001 Increment 1 §2.7 - "the generic presenter renders each of
the four declared capability types correctly from the fixture alone" and
"the explanation interface dispatches by intent code only". Both proved
here purely against the fictional "Acme Test Section" fixture
(`irene/tests/conftest.py::build_acme_test_section`) - never Stage 3.
"""
from dataclasses import replace

import pytest

from irene.models import IntentCode
from irene.question_engine import presenter
from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD,
    CAPABILITY_TYPE_SINGLE_CHOICE,
    QuestionOption,
    SingleChoiceQuestion,
)
from irene.question_engine.explain import resolve_explanation_skill
from irene.tests.conftest import build_acme_test_section


def _question(rendered_section, question_code):
    by_code = {q.question_code: q for q in rendered_section.questions}
    return by_code[question_code]


class TestGenericPresenterRendersAllFourCapabilityTypesFromTheFixtureAlone:
    def test_renders_single_choice_with_the_selected_option_marked(self):
        section = build_acme_test_section()
        rendered = presenter.render_section(section, {"acme_widget_colour": "blue"})
        question = _question(rendered, "acme_widget_colour")
        assert question.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE
        options_by_code = {opt.code: opt.selected for opt in question.options}
        assert options_by_code == {"red": False, "blue": True}

    def test_renders_grouped_independent_answer_fields_independently(self):
        section = build_acme_test_section()
        rendered = presenter.render_section(
            section,
            {
                "acme_widget_specs:has_handle": "yes",
                "acme_widget_specs:has_lid": "no",
            },
        )
        question = _question(rendered, "acme_widget_specs")
        assert question.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER
        fields_by_code = {field.field_code: field for field in question.grouped_fields}
        handle_selection = {opt.code: opt.selected for opt in fields_by_code["has_handle"].options}
        lid_selection = {opt.code: opt.selected for opt in fields_by_code["has_lid"].options}
        # Each sub-field's own answer is independent of its sibling's -
        # one field being "yes" never flips the other.
        assert handle_selection == {"yes": True, "no": False}
        assert lid_selection == {"yes": False, "no": True}

    def test_renders_linked_repeatable_record_as_a_bounded_read_only_summary(self):
        section = build_acme_test_section()
        rendered = presenter.render_section(section)
        question = _question(rendered, "acme_widget_parts")
        assert question.capability_type == CAPABILITY_TYPE_LINKED_REPEATABLE_RECORD
        assert question.record_columns == ("Part name", "Owner")
        assert question.record_rows == (("Bracket", "Warehouse A"), ("Bolt", "Warehouse B"))
        assert question.manage_route_concept_id == "task_list"

    def test_renders_delegated_workflow_as_a_declared_handoff_never_an_inline_editor(self):
        section = build_acme_test_section()
        rendered = presenter.render_section(section)
        question = _question(rendered, "acme_widget_registration")
        assert question.capability_type == CAPABILITY_TYPE_DELEGATED_WORKFLOW
        assert question.delegated_route_concept_id == "task_list"
        assert question.delegated_capability == "tasks"
        # No inline-editor fields leak through for a delegated_workflow
        # question - Amendment D3: "no duplicate asset editor".
        assert question.options == ()
        assert question.grouped_fields == ()
        assert question.record_rows == ()

    def test_renders_all_four_questions_in_declared_order_with_section_metadata_carried_through(self):
        section = build_acme_test_section()
        rendered = presenter.render_section(section)
        assert [q.question_code for q in rendered.questions] == [
            "acme_widget_colour",
            "acme_widget_specs",
            "acme_widget_parts",
            "acme_widget_registration",
        ]
        assert rendered.section_code == section.section_code
        assert rendered.catalogue_version == section.catalogue_version
        assert rendered.interaction_contract_version == section.interaction_contract_version


class TestPresenterRejectsAnUnrenderableCapabilityType:
    def test_raises_for_a_forged_capability_type_rather_than_guessing(self):
        section = build_acme_test_section()
        bogus_question = section.questions[0]
        object.__setattr__(bogus_question, "capability_type", "execute_arbitrary_sql")
        with pytest.raises(presenter.UnrenderableCapabilityTypeError, match="execute_arbitrary_sql"):
            presenter.render_question(bogus_question)


class TestExplanationInterfaceDispatchesByIntentCodeOnlyNeverBySection:
    """WO-IRENE-001 §2.7: 'the explanation interface dispatches by intent
    code only' - proved as an executed test, not an assertion in prose."""

    def test_two_different_sections_sharing_an_intent_code_resolve_to_the_same_skill(self):
        question_from_acme = build_acme_test_section().questions[0]
        question_from_an_unrelated_synthetic_section = SingleChoiceQuestion(
            question_code="totally_unrelated_question",
            title="Totally unrelated",
            help_text="x",
            options=(QuestionOption(code="a", label="A"),),
        )
        assert question_from_acme.explain_intent_code == IntentCode.EXPLAIN_CONTROL
        assert question_from_an_unrelated_synthetic_section.explain_intent_code == IntentCode.EXPLAIN_CONTROL

        skill_for_acme = resolve_explanation_skill(question_from_acme)
        skill_for_unrelated = resolve_explanation_skill(question_from_an_unrelated_synthetic_section)

        assert skill_for_acme is not None
        assert skill_for_acme.name == skill_for_unrelated.name

    def test_changing_only_the_intent_code_changes_the_resolved_skill_regardless_of_section(self):
        question = build_acme_test_section().questions[0]
        task_help_question = replace(question, explain_intent_code=IntentCode.TASK_NEXT_STEP_HELP)

        assert resolve_explanation_skill(question).name != resolve_explanation_skill(task_help_question).name

    def test_an_unclear_intent_code_resolves_to_no_skill_regardless_of_section(self):
        question = build_acme_test_section().questions[0]
        unclear_question = replace(question, explain_intent_code=IntentCode.UNCLEAR)
        assert resolve_explanation_skill(unclear_question) is None

    def test_an_unrecognised_intent_code_resolves_to_no_skill_regardless_of_section(self):
        question = build_acme_test_section().questions[0]
        forged_question = replace(question, explain_intent_code="not_a_real_intent")
        assert resolve_explanation_skill(forged_question) is None
