# Reuse the organisations app's tenant/user fixtures (org_a/org_b, user_a/
# user_b, client_a/client_b, ...) rather than duplicating them - same
# pattern security_state/tests/conftest.py / security_baseline/tests/
# conftest.py already use. Importing pytest fixtures re-exposes them to
# this directory's tests.
import pytest

from organisations.tests.conftest import (  # noqa: F401
    client_a,
    client_b,
    make_user,
    member_a,
    member_b,
    org_a,
    org_b,
    user_a,
    user_b,
)

from ai_platform.testing import FakeQuestionnaireDraftingGateway, FakeQuestionnaireInterpretationGateway


@pytest.fixture(autouse=True)
def questionnaire_storage_root(tmp_path, monkeypatch):
    """
    M009A: every questionnaire test gets its own throwaway
    QUESTIONNAIRE_STORAGE_ROOT, mirroring `evidence/tests/conftest.py`'s
    identically-named autouse fixture 1:1.
    """
    root = tmp_path / "questionnaire-storage"
    root.mkdir()
    monkeypatch.setenv("QUESTIONNAIRE_STORAGE_ROOT", str(root))
    return root


class _CombinedFakeQuestionnaireGateway:
    """A single object implementing both
    `ai_platform.gateway.QuestionnaireInterpretationGateway` and
    `QuestionnaireDraftingGateway`'s methods (duck-typed - no ABC
    inheritance needed for a test double), mirroring how a real
    `LiteLLMGateway()` instance implements both ABCs (see
    `questionnaire.services.generate_questionnaire_response`'s own
    docstring: "A single LiteLLMGateway instance implements both ABCs").

    Used by `patch_questionnaire_generation_gateways` below to monkeypatch
    `questionnaire.services.LiteLLMGateway` for HTTP-level (view-layer)
    tests that exercise `questionnaire_analyse`/`questionnaire_response_
    regenerate` without an explicit gateway kwarg - those views call
    `generate_questionnaire_response` with its default
    `interpretation_gateway=None`/`drafting_gateway=None`, which then
    construct `LiteLLMGateway()` internally.
    """

    def __init__(self, interpretation_gateway, drafting_gateway):
        self.interpretation_gateway = interpretation_gateway
        self.drafting_gateway = drafting_gateway

    def interpret_questionnaire_question(self, request, prompt_version):
        return self.interpretation_gateway.interpret_questionnaire_question(request, prompt_version)

    def draft_questionnaire_answer(self, request, prompt_version):
        return self.drafting_gateway.draft_questionnaire_answer(request, prompt_version)


def patch_questionnaire_generation_gateways(
    monkeypatch, *, interpretation_result=None, drafting_result=None, mode="valid"
):
    """Monkeypatch `questionnaire.services.LiteLLMGateway` so any HTTP-level
    call into `generate_questionnaire_response` (via
    `questionnaire:analyse`/`questionnaire:response_regenerate`) uses
    deterministic fakes instead of a live gateway. Returns
    `(interpretation_gateway, drafting_gateway)` so a test can still
    inspect `.calls` afterwards."""
    interpretation_gateway = FakeQuestionnaireInterpretationGateway(
        mode=mode, result=interpretation_result
    )
    drafting_gateway = FakeQuestionnaireDraftingGateway(mode=mode, result=drafting_result)
    combined = _CombinedFakeQuestionnaireGateway(interpretation_gateway, drafting_gateway)
    monkeypatch.setattr("questionnaire.services.LiteLLMGateway", lambda: combined)
    return interpretation_gateway, drafting_gateway


# ---------------------------------------------------------------------------
# M009B Increment 1 (WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-
# ORCHESTRATION.md §2.2/§2.12) - the Assurance Readiness Gate's test
# infrastructure.
#
# `security_baseline.readiness.evaluate_assurance_readiness` is a NEW
# cross-cutting check this increment adds to `questionnaire_import_
# upload`. Every pre-existing M009A test in this package
# (test_m009a_*.py) predates this concept entirely and exercises that
# view through bare, unconfigured `org_a`/`org_b` fixtures
# (organisations/tests/conftest.py's `Organisation.objects.create(name=...)`
# - no baseline answers, no governance/profile/workplace/assets/risk/
# policy setup at all), which is genuinely, honestly 0% Foundations-
# complete - and would therefore be BLOCKED by a real, un-stubbed
# readiness check, breaking M009A's own, unmodified test suite (a binding
# Work Order requirement, §2.12: "The existing M009A XLSX test suite
# reruns unmodified and green").
#
# Resolved the same way `_wi6_ensure_entitlements_seed_data` (the root
# conftest.py) already resolves an analogous "a new cross-cutting gate
# would otherwise break every pre-existing test" problem: an AUTOUSE
# fixture, scoped to exactly this test package, that defaults every
# organisation to READY - so no pre-existing M009A test needs to change -
# and is deliberately, trivially OVERRIDABLE: any test that genuinely
# wants to exercise the REAL gate (test_m009b_readiness_gate.py,
# test_m009b_csv_import.py's own HTTP-level tests) calls
# `monkeypatch.setattr(...)` again within its own test body, which simply
# replaces this default for that one test (ordinary pytest `monkeypatch`
# semantics - the last `setattr` call on a given target wins; this
# fixture's own patch is always applied first, during fixture setup,
# before any test body runs).
def _make_organisation_fully_assurance_ready(organisation):
    """
    Drives `entitlements.metrics.get_security_foundations_completion` to
    genuinely 100% for `organisation` - the exact same recipe
    `entitlements/tests/test_metrics.py::test_full_eighteen_item_total_
    no_double_counting` already uses and proves reaches 100% (18/18), so
    this helper is not a second, independently-invented definition of
    "ready". Used by `m009b_ready_organisation` below, and directly by
    any test that needs a genuinely, honestly ready organisation rather
    than a stubbed one.
    """
    from django.utils import timezone as django_timezone

    from governance.models import GovernanceRoleAssignment, OrganisationPerson
    from key_assets.models import CATEGORY_ENDPOINT, CRITICALITY_MEDIUM, KeyAsset
    from organisations.models import OrganisationProfile
    from policy.models import PolicyDocument, PolicyVersion
    from risk_register.models import Risk
    from security_baseline.catalogue import CATALOGUE_KEYS, CATALOGUE_VERSION
    from security_baseline.models import ANSWER_YES, BaselineAnswer, BaselineAssessment
    from workplace.models import Workplace

    assessment, _ = BaselineAssessment.objects.get_or_create(
        organisation=organisation, defaults={"catalogue_version": CATALOGUE_VERSION}
    )
    for key in CATALOGUE_KEYS:
        BaselineAnswer.objects.update_or_create(
            assessment=assessment, question_key=key, defaults={"answer": ANSWER_YES}
        )

    OrganisationProfile.objects.update_or_create(
        organisation=organisation,
        defaults=dict(
            legal_trading_name="Test Ltd",
            staff_count=12,
            endpoint_management="company_managed",
            productivity_platform="microsoft_365",
            primary_cloud_provider="none",
            develops_hosts_own_software="no",
            handles_personal_data="yes",
            handles_confidential_business_data="yes",
            handles_payment_card_data="no",
            handles_special_category_data="no",
            receives_security_questionnaires="yes",
        ),
    )

    person = OrganisationPerson.objects.create(
        organisation=organisation, full_name="Account Holder", is_active=True
    )
    for role, _label in GovernanceRoleAssignment.ROLE_CHOICES:
        GovernanceRoleAssignment.objects.get_or_create(
            organisation=organisation, role=role, defaults={"person": person}
        )

    Workplace.objects.get_or_create(
        organisation=organisation,
        name="Head office",
        defaults={"type": Workplace.TYPE_DEDICATED_OFFICE, "is_active": True},
    )

    KeyAsset.objects.get_or_create(
        organisation=organisation,
        name="Laptop fleet",
        defaults={
            "category": CATEGORY_ENDPOINT,
            "criticality": CRITICALITY_MEDIUM,
            "status": KeyAsset.STATUS_CONFIRMED,
        },
    )

    Risk.objects.get_or_create(
        organisation=organisation,
        title="Test risk",
        defaults=dict(
            threat="A threat",
            vulnerability="A gap",
            impact=1,
            likelihood=1,
            rationale="Because reasons.",
            proposed_treatment="Do something about it.",
            status=Risk.STATUS_CONFIRMED,
        ),
    )

    if not PolicyVersion.objects.filter(
        organisation=organisation, status=PolicyVersion.STATUS_APPROVED
    ).exists():
        document = PolicyDocument.objects.create(organisation=organisation)
        PolicyVersion.objects.create(
            document=document,
            organisation=organisation,
            version_number=1,
            status=PolicyVersion.STATUS_APPROVED,
            title="Information Security Policy",
            approved_at=django_timezone.now(),
        )

    return organisation


@pytest.fixture(autouse=True)
def m009b_default_assurance_readiness(monkeypatch):
    """See the module-level comment block above this fixture for the full
    "why" - defaults EVERY organisation to ready for this package's
    tests, by stubbing `security_baseline.readiness.
    evaluate_assurance_readiness` as it is imported into `questionnaire.
    upload_handler` (the one real call site this increment adds)."""
    from security_baseline.readiness import AssuranceReadinessResult

    def _always_ready(organisation):
        from entitlements.metrics import get_security_foundations_completion

        completion = get_security_foundations_completion(organisation)
        return AssuranceReadinessResult(
            organisation_id=str(organisation.id),
            is_ready=True,
            completion=completion,
            blockers=(),
        )

    monkeypatch.setattr("questionnaire.upload_handler.evaluate_assurance_readiness", _always_ready)


@pytest.fixture
def make_organisation_fully_assurance_ready():
    """Exposes `_make_organisation_fully_assurance_ready` as a fixture for
    tests that want a GENUINELY ready organisation (e.g.
    test_m009b_readiness_gate.py's own real-gate tests, which first undo
    `m009b_default_assurance_readiness`'s stub)."""
    return _make_organisation_fully_assurance_ready
