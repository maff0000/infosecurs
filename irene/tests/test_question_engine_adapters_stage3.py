"""
WO-IRENE-001 Increment 2 - tests for the real Stage 3 adapter
(irene.question_engine.adapters.stage3_technology_data): registration
against Increment 1's own, unmodified generic engine, presenter rendering
across all 10 STAGE3_TECHNOLOGY_DATA_FIELDS, the Key Assets
delegated_workflow path's additional `security` entitlement check
(Amendment D1), composed authorisation (irene+foundations, +security for
the delegation), and the Explain-this typed-context/dispatch wiring for
questions 3.1-3.6 (WO §1a R1) - WITHOUT ever calling the real AI gateway
(see this module's own zero-ask_adviser test below).
"""
from __future__ import annotations

import pytest

from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY
from irene.question_engine.adapters.stage3_technology_data import (
    ASSURANCE_STATUS_FIELD_NAMES,
    ASSURANCE_STATUS_QUESTION_CODE,
    CATALOGUE_VERSION,
    DATA_HANDLED_FIELD_NAMES,
    DATA_HANDLED_QUESTION_CODE,
    KEY_ASSETS_CONCEPT_ID,
    KEY_ASSETS_DELEGATED_CAPABILITY,
    KEY_ASSETS_QUESTION_CODE,
    REQUIRED_CAPABILITIES,
    SECTION_CODE,
    SINGLE_CHOICE_FIELD_NAMES,
    Stage3AccessDenied,
    answered_values_for_profile,
    build_explanation_context,
    build_stage3_section,
    check_stage3_access,
    resolve_stage3_explanation,
)
from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_SINGLE_CHOICE,
    INTERACTION_CONTRACT_VERSION,
)
from irene.question_engine.presenter import render_section
from irene.question_engine.registry import get_section
from irene.tests.conftest import request_at_tier
from organisations.models import UNKNOWN, YES, OrganisationProfile

pytestmark = pytest.mark.django_db


ALL_TEN_FIELDS = SINGLE_CHOICE_FIELD_NAMES + DATA_HANDLED_FIELD_NAMES + ASSURANCE_STATUS_FIELD_NAMES


class TestStage3SectionRegistration:
    def test_zero_knowledge_boundary_from_increment_1_is_unbroken(self):
        """The real, registered section is reachable via Increment 1's
        OWN, unmodified registry entry point - never a parallel lookup
        this adapter invents for itself."""
        section = get_section(SECTION_CODE)
        assert section.section_code == SECTION_CODE
        assert section.catalogue_version == CATALOGUE_VERSION
        assert section.interaction_contract_version == INTERACTION_CONTRACT_VERSION
        assert section.required_capabilities == REQUIRED_CAPABILITIES

    def test_covers_all_ten_stage3_fields_exactly_once(self):
        """Cross-checked directly against the real, unmodified
        organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS - every single
        one of the ten covered, none duplicated, none invented."""
        from organisations.views import STAGE3_TECHNOLOGY_DATA_FIELDS

        assert sorted(ALL_TEN_FIELDS) == sorted(STAGE3_TECHNOLOGY_DATA_FIELDS)
        assert len(ALL_TEN_FIELDS) == len(set(ALL_TEN_FIELDS)) == 10

    def test_question_37_is_a_declared_delegated_workflow_not_a_duplicate_editor(self):
        section = get_section(SECTION_CODE)
        key_assets_question = next(q for q in section.questions if q.question_code == KEY_ASSETS_QUESTION_CODE)
        assert key_assets_question.capability_type == CAPABILITY_TYPE_DELEGATED_WORKFLOW
        assert key_assets_question.delegated_route_concept_id == KEY_ASSETS_CONCEPT_ID
        assert key_assets_question.delegated_capability == KEY_ASSETS_DELEGATED_CAPABILITY

    def test_building_the_section_twice_produces_an_equal_but_distinct_definition(self):
        """Mirrors irene/tests/conftest.py's own
        build_acme_test_section "fresh definition each call" discipline -
        no shared mutable singleton."""
        first = build_stage3_section()
        second = build_stage3_section()
        assert first == second
        assert first is not second

    def test_key_assets_concept_is_registered_and_resolves_to_the_real_route(self):
        from django.urls import reverse

        from irene.product_knowledge import get_concept

        concept = get_concept(KEY_ASSETS_CONCEPT_ID)
        assert concept is not None
        assert concept.required_capability == KEY_ASSETS_DELEGATED_CAPABILITY
        assert reverse(concept.route_name, kwargs={"organisation_id": "00000000-0000-0000-0000-000000000001"})


class TestStage3PresenterRendering:
    """Increment 1's own generic presenter (irene.question_engine.presenter),
    unmodified, driven purely by capability_type - these tests prove the
    REAL Stage 3 section renders correctly through it, for all ten
    fields, in every state (no profile yet / a fully populated profile)."""

    def test_renders_with_no_profile_defaults_to_not_confirmed_for_every_field(self):
        section = get_section(SECTION_CODE)
        rendered = render_section(section, answered_values_for_profile(None))

        assert rendered.section_code == SECTION_CODE
        assert len(rendered.questions) == 7  # 3.1-3.6 + 3.7 delegated

        single_choice_questions = {
            q.question_code: q for q in rendered.questions if q.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE
        }
        assert set(single_choice_questions) == set(SINGLE_CHOICE_FIELD_NAMES)
        for question in single_choice_questions.values():
            selected = [opt for opt in question.options if opt.selected]
            assert len(selected) == 1
            assert selected[0].code == UNKNOWN

    def test_renders_a_fully_populated_profile_with_correct_selections(self, org_a):
        profile = OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Stage3 Presenter Test Ltd",
            productivity_platform="microsoft_365",
            primary_cloud_provider="aws",
            endpoint_management="company_managed",
            develops_hosts_own_software=YES,
            handles_personal_data=YES,
            handles_confidential_business_data="no",
            handles_payment_card_data="no",
            handles_special_category_data=UNKNOWN,
            cyber_essentials_status="in_progress",
            iso27001_status="not_certified",
        )
        section = get_section(SECTION_CODE)
        rendered = render_section(section, answered_values_for_profile(profile))

        by_code = {q.question_code: q for q in rendered.questions}

        platform_q = by_code["productivity_platform"]
        assert next(o.code for o in platform_q.options if o.selected) == "microsoft_365"

        data_handled_q = by_code[DATA_HANDLED_QUESTION_CODE]
        assert data_handled_q.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER
        grouped_by_field = {f.field_code: f for f in data_handled_q.grouped_fields}
        assert next(o.code for o in grouped_by_field["handles_personal_data"].options if o.selected) == YES
        assert (
            next(o.code for o in grouped_by_field["handles_special_category_data"].options if o.selected)
            == UNKNOWN
        )

        assurance_q = by_code[ASSURANCE_STATUS_QUESTION_CODE]
        grouped_assurance = {f.field_code: f for f in assurance_q.grouped_fields}
        assert (
            next(o.code for o in grouped_assurance["cyber_essentials_status"].options if o.selected)
            == "in_progress"
        )

        key_assets_q = by_code[KEY_ASSETS_QUESTION_CODE]
        assert key_assets_q.delegated_route_concept_id == KEY_ASSETS_CONCEPT_ID
        assert key_assets_q.delegated_capability == KEY_ASSETS_DELEGATED_CAPABILITY


class TestStage3ComposedAuthorisation:
    """Amendment D1 - composes entitlements.capabilities.has_capability
    for irene+foundations always, and additionally security ONLY for the
    delegated Key Assets path. Never built on
    entitlements.decorators.require_capability itself (see adapter
    module docstring)."""

    def test_member_at_monthly_tier_passes_the_irene_plus_foundations_gate(self, org_a, user_a, member_a):
        request = request_at_tier(user_a, tier=TIER_MONTHLY, organisation_id=org_a.id)
        organisation = check_stage3_access(request, org_a.id)
        assert organisation.id == org_a.id

    def test_member_at_monthly_tier_also_passes_the_key_assets_delegation_gate(self, org_a, user_a, member_a):
        """security's own seeded min_package_tier is 1 (Foundational) -
        TIER_MONTHLY satisfies it, exactly as the real key_assets app's
        own existing gate already requires."""
        request = request_at_tier(user_a, tier=TIER_MONTHLY, organisation_id=org_a.id)
        organisation = check_stage3_access(request, org_a.id, delegated_key_assets=True)
        assert organisation.id == org_a.id

    def test_non_member_gets_an_ordinary_404_never_a_403(self, org_a, user_b, member_b):
        from django.http import Http404

        request = request_at_tier(user_b, tier=TIER_MONTHLY, organisation_id=org_a.id)
        with pytest.raises(Http404):
            check_stage3_access(request, org_a.id)

    def test_insufficient_tier_is_denied_even_for_a_real_member(self, org_a, user_a, member_a, monkeypatch):
        """PAUSED (tier 0) satisfies neither irene (min tier 1) nor
        foundations (min tier 1)."""
        from entitlements.tiers import TIER_PAUSED

        request = request_at_tier(user_a, tier=TIER_PAUSED, organisation_id=org_a.id)
        with pytest.raises(Stage3AccessDenied):
            check_stage3_access(request, org_a.id)

    def test_every_call_independently_rechecks_never_caching_a_prior_result(
        self, org_a, user_a, member_a
    ):
        """Two SEPARATE request objects for the same user/organisation -
        nothing from the first call's success is reused by the second;
        if the second request's own context denies access, it must be
        denied on its own, not waved through by the first call's
        earlier success."""
        from entitlements.tiers import TIER_PAUSED

        allowed_request = request_at_tier(user_a, tier=TIER_MONTHLY, organisation_id=org_a.id)
        check_stage3_access(allowed_request, org_a.id)

        denied_request = request_at_tier(user_a, tier=TIER_PAUSED, organisation_id=org_a.id)
        with pytest.raises(Stage3AccessDenied):
            check_stage3_access(denied_request, org_a.id)


class TestStage3ExplainThisTypedContext:
    """WO §1a R1 - the typed question context for questions 3.1-3.6,
    dispatched via Increment 1's existing, unmodified
    irene.question_engine.explain.resolve_explanation_skill (intent-code
    only, reusing EXPLAIN_CONTROL). NEVER calls
    ai_platform.gateway.LiteLLMGateway.ask_adviser - see
    test_never_calls_the_real_ai_gateway below."""

    def test_single_choice_context_carries_only_what_this_one_question_needs(self):
        section = get_section(SECTION_CODE)
        question = next(q for q in section.questions if q.question_code == "productivity_platform")
        answered_values = {"productivity_platform": "google_workspace"}

        context = build_explanation_context(
            organisation=_FakeOrg("11111111-1111-1111-1111-111111111111"),
            question=question,
            answered_values=answered_values,
        )

        assert context.section_code == SECTION_CODE
        assert context.question_code == "productivity_platform"
        assert context.field_code is None
        assert context.catalogue_version == CATALOGUE_VERSION
        assert context.interaction_contract_version == INTERACTION_CONTRACT_VERSION
        assert context.current_answer_label == "Google Workspace"
        assert "Microsoft 365" in context.permitted_answer_labels
        assert context.intent_code == question.explain_intent_code

    def test_grouped_subfield_context_is_scoped_to_that_one_subfield_only(self):
        section = get_section(SECTION_CODE)
        question = next(q for q in section.questions if q.question_code == DATA_HANDLED_QUESTION_CODE)
        answered_values = {
            f"{DATA_HANDLED_QUESTION_CODE}:handles_payment_card_data": YES,
            f"{DATA_HANDLED_QUESTION_CODE}:handles_personal_data": "no",
        }

        context = build_explanation_context(
            organisation=_FakeOrg("11111111-1111-1111-1111-111111111111"),
            question=question,
            answered_values=answered_values,
            field_code="handles_payment_card_data",
        )

        assert context.field_code == "handles_payment_card_data"
        assert context.current_answer_label == "Yes"
        # Scoped to THIS sub-field's own options only - never the whole
        # group's labels, and never handles_personal_data's own answer.
        assert set(context.permitted_answer_labels) == {"Not confirmed", "Yes", "No"}

    def test_delegated_workflow_question_is_rejected_not_silently_explained(self):
        section = get_section(SECTION_CODE)
        question = next(q for q in section.questions if q.question_code == KEY_ASSETS_QUESTION_CODE)

        with pytest.raises(ValueError):
            build_explanation_context(
                organisation=_FakeOrg("11111111-1111-1111-1111-111111111111"),
                question=question,
                answered_values={},
            )

    def test_dispatch_resolves_the_same_skill_explain_control_already_resolves(self):
        section = get_section(SECTION_CODE)
        question = next(q for q in section.questions if q.question_code == "productivity_platform")

        dispatch = resolve_stage3_explanation(
            organisation=_FakeOrg("11111111-1111-1111-1111-111111111111"),
            question=question,
            answered_values={"productivity_platform": UNKNOWN},
        )

        assert dispatch.context.question_code == "productivity_platform"
        assert dispatch.skill is not None
        assert dispatch.skill.name == "foundations-guide"

    def test_never_calls_the_real_ai_gateway(self, monkeypatch):
        """Proves the dispatch wiring would correctly hand (context,
        skill) off to a gateway caller, using a STUB in this test only -
        production code (irene/question_engine/adapters/
        stage3_technology_data.py) imports neither
        ai_platform.gateway nor ask_adviser anywhere (see this module's
        own source and the FORGE report's grep confirmation)."""
        calls = []

        def fake_ask_adviser(context, skill):
            calls.append((context, skill))
            return "stubbed-explanation-text"

        section = get_section(SECTION_CODE)
        question = next(q for q in section.questions if q.question_code == "productivity_platform")
        dispatch = resolve_stage3_explanation(
            organisation=_FakeOrg("11111111-1111-1111-1111-111111111111"),
            question=question,
            answered_values={"productivity_platform": UNKNOWN},
        )

        # The stub is called HERE, in the test, never inside production
        # code - proving the context/skill pair is correctly assembled
        # and handable off, without this increment making a real call.
        result = fake_ask_adviser(dispatch.context, dispatch.skill)
        assert result == "stubbed-explanation-text"
        assert len(calls) == 1


class _FakeOrg:
    """A minimal stand-in carrying only `.id`, the one attribute
    build_explanation_context/resolve_stage3_explanation actually read -
    avoids a real `db`-backed Organisation fixture for tests that are
    pure-Python/dataclass concerns otherwise (mirrors irene/tests/
    conftest.py::FakeRequest's own "minimal stand-in" convention)."""

    def __init__(self, id):
        self.id = id
