"""
M008D-WI4 - `policy.clause_library`'s own required proofs (dispatch §A):

1. `CLAUSE_LIBRARY_VERSION` is set.
2. Every one of the 12 `security_baseline.catalogue` controls has exactly
   one clause.
3. Every clause's `section_key` is one of the 8 real
   `policy.section_labels.SECTION_LABELS` keys.
4. Generating a policy for an organisation with ZERO governance role
   assignments at all does not crash, and produces the
   `[name not yet confirmed]` placeholder text - M008D-SAMPLE-POLICIES.md
   Scenario C's approved behaviour.
"""
from __future__ import annotations

import pytest

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from policy.clause_library import (
    CLAUSE_LIBRARY_VERSION,
    CLAUSES,
    UNASSIGNED_ROLE_NAME_PLACEHOLDER,
    build_normative_sections,
)
from security_baseline.catalogue import CATALOGUE_KEYS


def test_clause_library_version_is_set():
    assert isinstance(CLAUSE_LIBRARY_VERSION, str) and CLAUSE_LIBRARY_VERSION


def test_every_control_has_exactly_one_clause():
    control_clause_keys = [c.control_key for c in CLAUSES if c.control_key is not None]
    assert sorted(control_clause_keys) == sorted(CATALOGUE_KEYS)
    assert len(control_clause_keys) == len(set(control_clause_keys))


def test_every_clause_section_key_is_a_real_allowed_section_key():
    for clause in CLAUSES:
        assert clause.section_key in ALLOWED_SECTION_KEYS


@pytest.mark.django_db
class TestBuildNormativeSectionsWithNoGovernanceAssignments:
    def test_does_not_crash_with_zero_governance_assignments(self, org_a):
        assert GovernanceRoleAssignment.objects.filter(organisation=org_a).count() == 0
        sections = build_normative_sections(org_a)
        assert len(sections) == 8

    def test_unassigned_role_renders_the_placeholder_not_a_blank_or_crash(self, org_a):
        sections = build_normative_sections(org_a)
        governance_section = next(
            s for s in sections if s.section_key == "responsibilities_and_governance"
        )
        assert UNASSIGNED_ROLE_NAME_PLACEHOLDER in governance_section.content

        review_section = next(
            s for s in sections if s.section_key == "review_approval_and_document_control"
        )
        assert UNASSIGNED_ROLE_NAME_PLACEHOLDER in review_section.content

        access_section = next(
            s for s in sections if s.section_key == "security_incidents_and_reporting"
        )
        assert UNASSIGNED_ROLE_NAME_PLACEHOLDER in access_section.content

    def test_assigning_a_role_replaces_the_placeholder_with_the_real_name(self, org_a, user_a):
        person = OrganisationPerson.objects.create(
            organisation=org_a, user=user_a, full_name="Ada Holder"
        )
        assign_role(
            organisation=org_a,
            role=GovernanceRoleAssignment.ROLE_SENIOR_LEADERSHIP,
            person=person,
        )
        sections = build_normative_sections(org_a)
        governance_section = next(
            s for s in sections if s.section_key == "responsibilities_and_governance"
        )
        assert "Ada Holder" in governance_section.content
        # The security responsible role is still unassigned - still the
        # placeholder, not Ada Holder's name leaking into an unrelated role.
        assert UNASSIGNED_ROLE_NAME_PLACEHOLDER in governance_section.content

    def test_every_generated_section_key_is_one_of_the_eight_real_keys(self, org_a):
        sections = build_normative_sections(org_a)
        for section in sections:
            assert section.section_key in ALLOWED_SECTION_KEYS

    def test_exactly_eight_sections_always_produced(self, org_a):
        assert len(build_normative_sections(org_a)) == len(ALLOWED_SECTION_KEYS)
