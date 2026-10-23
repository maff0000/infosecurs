"""
WO-IRENE-001 Increment 2 - the "second section without touching IRENE
core" proof (WO §3.2's last bullet / §3.10's second evidence artifact;
PID Amendment Closure condition item 3's second mandatory acceptance
condition; WO §3.8's audit gate: "the second-section proof genuinely
touching zero lines of Increment 1's orchestration/modal/renderer code
(a `git diff` scope check, not a verbal claim)").

A second, deliberately small, GENUINELY DIFFERENT synthetic section from
Increment 1's own "Acme Test Section" fixture
(`irene/tests/conftest.py::build_acme_test_section`, a fictional
widget/manufacturing test rig) - a fictional "Starlight Bakery" kitchen-
safety snapshot, registered purely through
`irene.question_engine.registry.register_section`, exactly as documented
in `docs/guides/IRENE-SECTION-INTEGRATION-GUIDE.md`, whose own worked
example IS this file's `build_starlight_bakery_section()`.

Deliberately exercises three of the four declared capability types
(Amendment D1/D3) - `single_choice`, `grouped_independent_answer`, and
`delegated_workflow` - and deliberately OMITS `linked_repeatable_record`:
this fictional bakery-safety snapshot has no natural "a list of records
already owned by another existing app" concept of its own. Increment 1's
own Acme fixture already proves that fourth shape fully
(`test_question_engine_presenter.py::
test_renders_linked_repeatable_record_as_a_bounded_read_only_summary`);
forcing an unrelated fourth question in here purely to tick a box would
not be a genuine second-section proof, it would be padding - the Work
Order itself says exactly this is acceptable ("doesn't need to cover all
four if your fictional scenario doesn't naturally call for it").

This file imports NOTHING from `irene.question_engine.contract`,
`registry`, `presenter`, or `explain` beyond each module's own documented
public surface (every name below appears in that module's own `__all__`)
- no private helper, no monkeypatch, no reach into module internals. Nor
does it import or reference anything from `organisations`/`key_assets`/
Stage 3 - this section is synthetic and fictional, completely decoupled
from the real Stage 3 adapter a different engineer is concurrently
building in a different isolated worktree, under a different WO-IRENE-001
Increment 2 task.

None of these tests use the `db` fixture - exactly like Increment 1's own
equivalent tests (`test_question_engine_registry.py`/
`test_question_engine_presenter.py`), confirmed by inspection before
writing this file. The registry/presenter/explain modules are pure
Python/dataclasses and a `SectionDefinition` is never persisted to any
database table (WO §2.4/§3.4: zero backing table for the registry
itself).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from irene.models import IntentCode
from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_SINGLE_CHOICE,
    DelegatedWorkflowQuestion,
    GroupedAnswerField,
    GroupedIndependentAnswerQuestion,
    QuestionOption,
    SectionDefinition,
    SingleChoiceQuestion,
)
from irene.question_engine.explain import resolve_explanation_skill
from irene.question_engine.presenter import render_section
from irene.question_engine.registry import (
    deregister_section,
    get_section,
    register_section,
    registered_section_codes,
)

STARLIGHT_BAKERY_SECTION_CODE = "starlight_bakery_section"


def build_starlight_bakery_section() -> SectionDefinition:
    """The Integration Guide's own worked example
    (docs/guides/IRENE-SECTION-INTEGRATION-GUIDE.md cites this exact
    function by name). A fictional kitchen-safety snapshot for a
    fictional "Starlight Bakery" - genuinely different subject matter,
    field names, and question codes from Increment 1's own "Acme Test
    Section" (a widget/manufacturing fixture), proving the contract is
    reusable for an unrelated scenario rather than secretly Acme-shaped.

    Registered purely through `irene.question_engine.registry.
    register_section` by the fixtures below - this function itself never
    touches `SECTION_REGISTRY`, exactly mirroring `irene.tests.conftest.
    build_acme_test_section`'s own "builds a fresh definition, registers
    nowhere itself" discipline."""
    return SectionDefinition(
        section_code=STARLIGHT_BAKERY_SECTION_CODE,
        title="Starlight Bakery - Kitchen Safety Snapshot",
        catalogue_version="1.0.0",
        required_capabilities=("irene",),
        questions=(
            SingleChoiceQuestion(
                question_code="bakery_oven_type",
                title="What type of oven does the bakery use?",
                help_text="Pick the oven type currently in use on site.",
                options=(
                    QuestionOption(code="wood_fired", label="Wood-fired"),
                    QuestionOption(code="electric", label="Electric"),
                    QuestionOption(code="gas", label="Gas"),
                ),
            ),
            GroupedIndependentAnswerQuestion(
                question_code="bakery_packaging_specs",
                title="Packaging specifications",
                help_text="Answer each packaging specification independently.",
                fields=(
                    GroupedAnswerField(
                        field_code="uses_compostable_wrapping",
                        label="Uses compostable wrapping?",
                        options=(
                            QuestionOption(code="yes", label="Yes"),
                            QuestionOption(code="no", label="No"),
                        ),
                    ),
                    GroupedAnswerField(
                        field_code="uses_branded_boxes",
                        label="Uses branded boxes?",
                        options=(
                            QuestionOption(code="yes", label="Yes"),
                            QuestionOption(code="no", label="No"),
                        ),
                    ),
                ),
            ),
            # "customer_assurance_upload" is a real, already-registered,
            # AVAILABLE `irene.product_knowledge` concept whose own
            # `required_capability` is "customer_assurance" (matched
            # below in `delegated_capability`) - reused purely as a
            # stand-in referenceable concept so this fixture can exercise
            # the registry's real concept-id validation, exactly as
            # Increment 1's Acme fixture reuses "task_list"/"tasks" for
            # the same reason. Never a Stage-3/`organisations`/
            # `key_assets` reference of any kind.
            DelegatedWorkflowQuestion(
                question_code="bakery_ingredient_sourcing_review",
                title="Ingredient sourcing review",
                help_text=(
                    "Sourcing compliance is handled by the existing "
                    "Customer Assurance workflow, not inside this snapshot."
                ),
                delegated_route_concept_id="customer_assurance_upload",
                delegated_capability="customer_assurance",
            ),
        ),
    )


@pytest.fixture
def starlight_bakery_section():
    return build_starlight_bakery_section()


@pytest.fixture
def registered_starlight_bakery_section(starlight_bakery_section):
    """Mirrors `irene.tests.conftest.registered_acme_test_section`'s own
    register-then-deregister-in-finally shape, so this fixture never
    leaks registry state into any other test module."""
    register_section(starlight_bakery_section)
    try:
        yield starlight_bakery_section
    finally:
        deregister_section(STARLIGHT_BAKERY_SECTION_CODE)


def _question(rendered_section, question_code):
    return {q.question_code: q for q in rendered_section.questions}[question_code]


class TestSecondSectionRegistersThroughTheDocumentedContractAlone:
    def test_register_and_get_round_trip(self, registered_starlight_bakery_section):
        section = get_section(STARLIGHT_BAKERY_SECTION_CODE)
        assert section.section_code == STARLIGHT_BAKERY_SECTION_CODE
        assert len(section.questions) == 3
        assert STARLIGHT_BAKERY_SECTION_CODE in registered_section_codes()

    def test_second_section_is_genuinely_different_from_the_first(self, registered_starlight_bakery_section):
        """Not a copy of Acme with renamed strings: different subject,
        different question/field codes, and a different capability-type
        mix (three types, no linked_repeatable_record)."""
        section = get_section(STARLIGHT_BAKERY_SECTION_CODE)
        question_codes = {q.question_code for q in section.questions}
        assert question_codes.isdisjoint(
            {
                "acme_widget_colour",
                "acme_widget_specs",
                "acme_widget_parts",
                "acme_widget_registration",
            }
        )
        capability_types = {q.capability_type for q in section.questions}
        assert capability_types == {
            CAPABILITY_TYPE_SINGLE_CHOICE,
            CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
            CAPABILITY_TYPE_DELEGATED_WORKFLOW,
        }


class TestSecondSectionRendersCorrectlyViaTheUnmodifiedGenericPresenter:
    def test_renders_single_choice_with_the_selected_option_marked(self, registered_starlight_bakery_section):
        rendered = render_section(registered_starlight_bakery_section, {"bakery_oven_type": "gas"})
        question = _question(rendered, "bakery_oven_type")
        assert question.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE
        options_by_code = {opt.code: opt.selected for opt in question.options}
        assert options_by_code == {"wood_fired": False, "electric": False, "gas": True}

    def test_renders_grouped_independent_answer_fields_independently(self, registered_starlight_bakery_section):
        rendered = render_section(
            registered_starlight_bakery_section,
            {
                "bakery_packaging_specs:uses_compostable_wrapping": "yes",
                "bakery_packaging_specs:uses_branded_boxes": "no",
            },
        )
        question = _question(rendered, "bakery_packaging_specs")
        assert question.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER
        fields_by_code = {field.field_code: field for field in question.grouped_fields}
        compostable_selection = {
            opt.code: opt.selected for opt in fields_by_code["uses_compostable_wrapping"].options
        }
        branded_selection = {opt.code: opt.selected for opt in fields_by_code["uses_branded_boxes"].options}
        # Each sub-field's own answer is independent of its sibling's -
        # one field being "yes" never flips the other.
        assert compostable_selection == {"yes": True, "no": False}
        assert branded_selection == {"yes": False, "no": True}

    def test_renders_delegated_workflow_as_a_declared_handoff_never_an_inline_editor(
        self, registered_starlight_bakery_section
    ):
        rendered = render_section(registered_starlight_bakery_section)
        question = _question(rendered, "bakery_ingredient_sourcing_review")
        assert question.capability_type == CAPABILITY_TYPE_DELEGATED_WORKFLOW
        assert question.delegated_route_concept_id == "customer_assurance_upload"
        assert question.delegated_capability == "customer_assurance"
        # No inline-editor fields leak through for a delegated_workflow
        # question - Amendment D3: "no duplicate asset editor".
        assert question.options == ()
        assert question.grouped_fields == ()
        assert question.record_rows == ()

    def test_renders_all_three_questions_in_declared_order_with_section_metadata_carried_through(
        self, registered_starlight_bakery_section
    ):
        rendered = render_section(registered_starlight_bakery_section)
        assert [q.question_code for q in rendered.questions] == [
            "bakery_oven_type",
            "bakery_packaging_specs",
            "bakery_ingredient_sourcing_review",
        ]
        assert rendered.section_code == registered_starlight_bakery_section.section_code
        assert rendered.catalogue_version == registered_starlight_bakery_section.catalogue_version
        assert (
            rendered.interaction_contract_version
            == registered_starlight_bakery_section.interaction_contract_version
        )


class TestSecondSectionQuestionsDispatchExplanationsByIntentCodeOnly:
    """The exact same mechanism Increment 1 already proved
    (`test_question_engine_presenter.py::
    TestExplanationInterfaceDispatchesByIntentCodeOnlyNeverBySection`) -
    re-proved here from a second, unrelated, previously-nonexistent
    section to show the dispatch genuinely does not care which section a
    question came from."""

    def test_every_question_declares_explain_control_and_resolves_a_skill(
        self, registered_starlight_bakery_section
    ):
        for question in registered_starlight_bakery_section.questions:
            assert question.explain_intent_code == IntentCode.EXPLAIN_CONTROL
            skill = resolve_explanation_skill(question)
            assert skill is not None

    def test_second_section_resolves_to_the_identical_skill_as_the_first_section(
        self, registered_starlight_bakery_section
    ):
        from irene.tests.conftest import build_acme_test_section

        bakery_question = registered_starlight_bakery_section.questions[0]
        acme_question = build_acme_test_section().questions[0]
        assert bakery_question.explain_intent_code == acme_question.explain_intent_code

        skill_for_bakery = resolve_explanation_skill(bakery_question)
        skill_for_acme = resolve_explanation_skill(acme_question)
        assert skill_for_bakery is not None
        assert skill_for_bakery.name == skill_for_acme.name


class TestSecondSectionProofTouchesZeroLinesOfIncrement1sCoreModules:
    """WO-IRENE-001 §3.8's audit gate, run as an executed scope check
    rather than asserted in prose: confirms the actual repository diff
    introduces zero changes to any of Increment 1's four core modules.

    Diffs against the merge-base of `HEAD` and this branch's own parent
    integration branch (`wo/IRENE-001-pilot`) when that ref is
    resolvable, falling back to `HEAD` otherwise - so that, right now
    (zero commits made on top of this branch yet), it is equivalent to
    diffing against HEAD, and remains meaningful if a future commit is
    later made on top of this branch before that ref is checked again.
    Skips (never fails CI for an unrelated reason) if this checkout has
    no usable git history to diff against - e.g. a tarball export with
    no `.git` directory - since that is an environment limitation, not
    evidence of a scope violation."""

    CORE_MODULES = (
        "irene/question_engine/contract.py",
        "irene/question_engine/registry.py",
        "irene/question_engine/presenter.py",
        "irene/question_engine/explain.py",
    )
    PARENT_BRANCH_CANDIDATES = ("wo/IRENE-001-pilot", "origin/wo/IRENE-001-pilot")

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _diff_base_ref(self, repo_root: Path) -> str:
        for ref in self.PARENT_BRANCH_CANDIDATES:
            result = subprocess.run(
                ["git", "merge-base", "HEAD", ref],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        return "HEAD"

    def test_git_diff_shows_zero_changes_to_increment_1s_core_modules(self):
        if shutil.which("git") is None:
            pytest.skip("git is not available in this environment")

        repo_root = self._repo_root()
        if not (repo_root / ".git").exists():
            pytest.skip("no .git directory in this checkout - cannot run a diff scope check")

        base_ref = self._diff_base_ref(repo_root)
        result = subprocess.run(
            ["git", "diff", "--stat", base_ref, "--", *self.CORE_MODULES],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pytest.skip(f"git diff could not run in this environment: {result.stderr.strip()}")

        assert result.stdout.strip() == "", (
            "Increment 1's core engine modules show diff activity relative to "
            f"{base_ref!r} - this violates the 'second section without touching "
            f"IRENE core' proof:\n{result.stdout}"
        )
