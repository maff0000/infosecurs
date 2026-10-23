"""
Local fixtures for `irene` tests, mirroring `security_tasks/tests/
conftest.py`/`foundations_journey/tests/conftest.py` 1:1 (this codebase's
own established per-app fixture-duplication convention).
"""
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client

from entitlements.session import issue_context
from entitlements.tiers import TIER_MONTHLY
from organisations.models import Organisation, OrganisationMembership


@pytest.fixture
def make_user(db):
    def _make_user(username, password="a-strong-test-password-123"):
        User = get_user_model()
        return User.objects.create_user(username=username, password=password)

    return _make_user


@pytest.fixture
def org_a(db):
    return Organisation.objects.create(name="IRENE Org A Synthetic Ltd")


@pytest.fixture
def org_b(db):
    return Organisation.objects.create(name="IRENE Org B Synthetic Ltd")


@pytest.fixture
def user_a(make_user):
    return make_user("irene_user_a")


@pytest.fixture
def user_b(make_user):
    return make_user("irene_user_b")


@pytest.fixture
def member_a(db, org_a, user_a):
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_a, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def member_b(db, org_b, user_b):
    return OrganisationMembership.objects.create(
        organisation=org_b, user=user_b, role=OrganisationMembership.ROLE_OWNER
    )


@pytest.fixture
def client_a(user_a, member_a):
    c = Client()
    c.force_login(user_a)
    return c


@pytest.fixture
def client_b(user_b, member_b):
    c = Client()
    c.force_login(user_b)
    return c


@pytest.fixture
def user_c(make_user):
    """A second member of org_a."""
    return make_user("irene_user_c")


@pytest.fixture
def member_c(db, org_a, user_c):
    return OrganisationMembership.objects.create(
        organisation=org_a, user=user_c, role=OrganisationMembership.ROLE_OWNER
    )


class FakeRequest:
    """A minimal stand-in for `django.http.HttpRequest`, carrying exactly
    what `entitlements.capabilities.has_capability`/`irene.tools.
    _revalidate` read (`.session`, `.user`) - the SAME pattern
    `entitlements/tests/test_capabilities.py`'s own `FakeRequest`/
    `request_at_tier` already establish, reused here rather than
    reinvented, for tool/service-layer tests that need a real, capability-
    checkable `AuthorizedContext` without going through the full HTTP
    view stack."""

    def __init__(self, session, user):
        self.session = session
        self.user = user


def request_at_tier(user, tier=TIER_MONTHLY, organisation_id=None):
    store = SessionStore()
    store.save()
    request = FakeRequest(store, user)
    issue_context(request, user, package_tier=tier, auth_source="test_fixture", organisation_id=organisation_id)
    return request


@pytest.fixture
def idempotency_key():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# WO-IRENE-001 Increment 1 - synthetic, throwaway question-engine fixture.
# Deliberately NOT Stage 3 (WO-IRENE-001 §2.7: "a synthetic, throwaway
# section/question definition"): a fictional "Acme Test Section" exercising
# all four declared capability types, shared by `irene/tests/
# test_question_engine_registry.py` and `irene/tests/
# test_question_engine_presenter.py` so neither file has to invent its own
# copy. Pure Python/dataclasses - no `db` fixture dependency, same as
# `irene/tests/test_skills.py`'s own skill-manifest fixtures.
# ---------------------------------------------------------------------------
ACME_TEST_SECTION_CODE = "acme_test_section"


def build_acme_test_section(*, interaction_contract_version=None):
    """Builds a fresh synthetic `SectionDefinition` each call (never a
    shared mutable singleton other tests could accidentally leak state
    through). `interaction_contract_version` is overridable only so
    `test_question_engine_registry.py` can prove the registry rejects a
    section built against a stale/foreign contract version."""
    from irene.question_engine.contract import (
        DelegatedWorkflowQuestion,
        GroupedAnswerField,
        GroupedIndependentAnswerQuestion,
        LinkedRepeatableRecordQuestion,
        QuestionOption,
        RecordColumn,
        SectionDefinition,
        SingleChoiceQuestion,
    )

    kwargs = {}
    if interaction_contract_version is not None:
        kwargs["interaction_contract_version"] = interaction_contract_version

    return SectionDefinition(
        section_code=ACME_TEST_SECTION_CODE,
        title="Acme Test Section",
        catalogue_version="1.0.0",
        required_capabilities=("irene",),
        questions=(
            SingleChoiceQuestion(
                question_code="acme_widget_colour",
                title="What colour is the Acme widget?",
                help_text="Pick the widget's primary colour.",
                options=(
                    QuestionOption(code="red", label="Red"),
                    QuestionOption(code="blue", label="Blue"),
                ),
            ),
            GroupedIndependentAnswerQuestion(
                question_code="acme_widget_specs",
                title="Acme widget specifications",
                help_text="Answer each specification independently.",
                fields=(
                    GroupedAnswerField(
                        field_code="has_handle",
                        label="Has a handle?",
                        options=(
                            QuestionOption(code="yes", label="Yes"),
                            QuestionOption(code="no", label="No"),
                        ),
                    ),
                    GroupedAnswerField(
                        field_code="has_lid",
                        label="Has a lid?",
                        options=(
                            QuestionOption(code="yes", label="Yes"),
                            QuestionOption(code="no", label="No"),
                        ),
                    ),
                ),
            ),
            # "task_list" is a real, already-registered, generic
            # `irene.product_knowledge` concept (security_tasks' own
            # shared Tasks list) - reused here purely as a stand-in
            # referenceable concept so this fixture can exercise the
            # registry's real concept-id validation, never a Stage-3 or
            # `organisations`-app reference of any kind.
            LinkedRepeatableRecordQuestion(
                question_code="acme_widget_parts",
                title="Acme widget parts",
                help_text="Parts already recorded elsewhere for this widget.",
                record_columns=(
                    RecordColumn(code="part_name", label="Part name"),
                    RecordColumn(code="part_owner", label="Owner"),
                ),
                record_rows=(("Bracket", "Warehouse A"), ("Bolt", "Warehouse B")),
                manage_route_concept_id="task_list",
            ),
            DelegatedWorkflowQuestion(
                question_code="acme_widget_registration",
                title="Acme widget registration",
                help_text="Registration is handled by the Acme Registration workflow.",
                delegated_route_concept_id="task_list",
                delegated_capability="tasks",
            ),
        ),
        **kwargs,
    )


@pytest.fixture
def acme_test_section():
    return build_acme_test_section()


@pytest.fixture
def registered_acme_test_section(acme_test_section):
    from irene.question_engine.registry import deregister_section, register_section

    register_section(acme_test_section)
    try:
        yield acme_test_section
    finally:
        deregister_section(ACME_TEST_SECTION_CODE)
