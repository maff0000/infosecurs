"""
WO-IRENE-001 Increment 1 §2.7 - "Unit tests using a synthetic, throwaway
section/question definition... to prove: registration rejects malformed/
unknown entries". Every section built here is the fictional "Acme Test
Section" (`irene/tests/conftest.py::build_acme_test_section`) or a
deliberately-broken variant of it - never a real business section, and
never anything from a real domain app.
"""
from dataclasses import replace

import pytest

from irene.question_engine import contract
from irene.question_engine.contract import DelegatedWorkflowQuestion
from irene.question_engine.registry import (
    SECTION_REGISTRY,
    InvalidSectionDefinitionError,
    UnregisteredSectionError,
    get_section,
    register_section,
    registered_section_codes,
    validate_all_registered_sections,
)
from irene.tests.conftest import ACME_TEST_SECTION_CODE, build_acme_test_section


class TestRegistrySucceedsForAValidSyntheticSection:
    def test_register_and_get_round_trip(self, registered_acme_test_section):
        section = get_section(ACME_TEST_SECTION_CODE)
        assert section.section_code == ACME_TEST_SECTION_CODE
        assert len(section.questions) == 4
        assert ACME_TEST_SECTION_CODE in registered_section_codes()

    def test_boot_time_validator_passes_once_registered(self, registered_acme_test_section):
        validate_all_registered_sections()  # must not raise


class TestRegistryRejectsUnregisteredSectionCodes:
    """WO-IRENE-001 §2.8: 'Confirm the registry genuinely rejects an
    unregistered section code (not just that a registered one works)' -
    an EXECUTED test, not an assertion in prose."""

    def test_get_unregistered_section_raises(self):
        assert "definitely-not-a-real-section" not in SECTION_REGISTRY
        with pytest.raises(UnregisteredSectionError, match="definitely-not-a-real-section"):
            get_section("definitely-not-a-real-section")

    def test_unregistered_section_never_resolves_to_a_usable_value(self):
        """Documents the "never silently None" contract directly: the
        only way to observe this section code is the exception path."""
        with pytest.raises(UnregisteredSectionError):
            get_section("still-not-registered")


class TestRegistryRejectsMalformedOrForgedSections:
    def test_rejects_section_with_no_questions(self):
        section = contract.SectionDefinition(
            section_code="acme_empty_section",
            title="Empty",
            catalogue_version="1.0.0",
            questions=(),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="at least one question"):
            register_section(section)
        assert "acme_empty_section" not in SECTION_REGISTRY

    def test_rejects_unsafe_section_code(self):
        section = contract.SectionDefinition(
            section_code="../etc/passwd",
            title="Path traversal attempt",
            catalogue_version="1.0.0",
            questions=(build_acme_test_section().questions[0],),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="lowercase identifier"):
            register_section(section)
        assert "../etc/passwd" not in SECTION_REGISTRY

    def test_rejects_question_with_forged_capability_type(self):
        """Simulates a hostile/forged definition built outside this
        module's own typed constructors - the registry must catch this
        even though no real constructor in `irene.question_engine.
        contract` can produce it today."""
        bogus_question = build_acme_test_section().questions[0]
        object.__setattr__(bogus_question, "capability_type", "execute_arbitrary_sql")
        section = contract.SectionDefinition(
            section_code="acme_evil_section",
            title="Evil",
            catalogue_version="1.0.0",
            questions=(bogus_question,),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="execute_arbitrary_sql"):
            register_section(section)
        assert "acme_evil_section" not in SECTION_REGISTRY

    def test_rejects_question_with_unregistered_explain_intent_code(self):
        question = replace(build_acme_test_section().questions[0], explain_intent_code="approve_anything")
        section = contract.SectionDefinition(
            section_code="acme_evil_section_2",
            title="Evil",
            catalogue_version="1.0.0",
            questions=(question,),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="explain_intent_code"):
            register_section(section)
        assert "acme_evil_section_2" not in SECTION_REGISTRY

    def test_rejects_duplicate_question_codes(self):
        base = build_acme_test_section()
        section = contract.SectionDefinition(
            section_code="acme_dup_section",
            title="Dup",
            catalogue_version="1.0.0",
            questions=(base.questions[0], base.questions[0]),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="duplicate question_code"):
            register_section(section)
        assert "acme_dup_section" not in SECTION_REGISTRY

    def test_rejects_empty_catalogue_version(self):
        base = build_acme_test_section()
        section = contract.SectionDefinition(
            section_code="acme_no_version_section",
            title="No version",
            catalogue_version="",
            questions=(base.questions[0],),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="catalogue_version"):
            register_section(section)
        assert "acme_no_version_section" not in SECTION_REGISTRY

    def test_rejects_stale_interaction_contract_version(self):
        """Amendment D2's separately-versioned "generic interaction
        contract" axis: a section built against a stale/foreign engine
        shape is refused at registration, never silently accepted."""
        section = build_acme_test_section(interaction_contract_version="0.0.1-stale")
        with pytest.raises(InvalidSectionDefinitionError, match="interaction_contract_version"):
            register_section(section)
        assert section.section_code not in SECTION_REGISTRY

    def test_rejects_unregistered_required_capability(self):
        base = build_acme_test_section()
        section = contract.SectionDefinition(
            section_code="acme_bad_capability_section",
            title="Bad capability",
            catalogue_version="1.0.0",
            required_capabilities=("super_admin",),
            questions=(base.questions[0],),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="super_admin"):
            register_section(section)
        assert "acme_bad_capability_section" not in SECTION_REGISTRY

    def test_rejects_delegated_workflow_with_unregistered_concept_reference(self):
        """Mirrors `irene.skill_loader`'s own "reference must point at
        something real" rigor, applied to a concept-id reference instead
        of a file path."""
        question = DelegatedWorkflowQuestion(
            question_code="acme_bad_delegation",
            title="Bad delegation",
            help_text="x",
            delegated_route_concept_id="not_a_real_concept",
            delegated_capability="tasks",
        )
        section = contract.SectionDefinition(
            section_code="acme_bad_delegation_section",
            title="Bad delegation",
            catalogue_version="1.0.0",
            questions=(question,),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="not_a_real_concept"):
            register_section(section)
        assert "acme_bad_delegation_section" not in SECTION_REGISTRY

    def test_rejects_delegated_workflow_with_unregistered_delegated_capability(self):
        question = DelegatedWorkflowQuestion(
            question_code="acme_bad_delegation_2",
            title="Bad delegation 2",
            help_text="x",
            delegated_route_concept_id="task_list",
            delegated_capability="super_admin",
        )
        section = contract.SectionDefinition(
            section_code="acme_bad_delegation_section_2",
            title="Bad delegation 2",
            catalogue_version="1.0.0",
            questions=(question,),
        )
        with pytest.raises(InvalidSectionDefinitionError, match="super_admin"):
            register_section(section)
        assert "acme_bad_delegation_section_2" not in SECTION_REGISTRY

    def test_a_failed_registration_leaves_the_registry_completely_untouched(self):
        before = dict(SECTION_REGISTRY)
        section = contract.SectionDefinition(
            section_code="acme_broken_section",
            title="Broken",
            catalogue_version="1.0.0",
            questions=(),
        )
        with pytest.raises(InvalidSectionDefinitionError):
            register_section(section)
        assert SECTION_REGISTRY == before
