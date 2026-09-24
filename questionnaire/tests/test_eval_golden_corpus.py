"""
Tests for `questionnaire.eval.golden_corpus` (PID §28 - m005-3-eval-harness
dispatch): idempotency, plus the two cases (8/9) whose own tenant-state
setup makes a specific claim about `security_state.services.
get_security_state`'s derived assurance label - PROVEN here, not merely
assumed, mirroring `policy/tests/test_eval_golden_corpus.py`'s identical
precedent for its own "strong evidence-backed security state" case.
"""
import pytest

from evidence.models import EvidenceItem
from organisations.models import Organisation
from policy.models import PolicyVersion
from remediation.models import RemediationAction
from security_state.services import get_security_state

from questionnaire.eval.golden_corpus import (
    GOLDEN_CORPUS,
    _stable_id,
    ensure_case_organisation,
    ensure_case_question,
)

pytestmark = pytest.mark.django_db


class TestStableIds:
    def test_same_parts_produce_same_id(self):
        assert _stable_id("organisation", "some_case") == _stable_id("organisation", "some_case")

    def test_different_parts_produce_different_ids(self):
        assert _stable_id("organisation", "case_one") != _stable_id("organisation", "case_two")


class TestGoldenCorpusShape:
    def test_exactly_fourteen_cases(self):
        assert len(GOLDEN_CORPUS) == 14

    def test_case_keys_are_unique(self):
        keys = [case["key"] for case in GOLDEN_CORPUS]
        assert len(keys) == len(set(keys))

    def test_every_case_has_an_expected_draft(self):
        for case in GOLDEN_CORPUS:
            assert case["expected_draft"].answer_text


class TestIdempotency:
    def test_ensure_case_organisation_twice_creates_no_duplicate_rows(self):
        case = GOLDEN_CORPUS[0]
        org_first = ensure_case_organisation(case)
        count_first = Organisation.objects.filter(pk=org_first.pk).count()

        org_second = ensure_case_organisation(case)

        assert str(org_first.pk) == str(org_second.pk)
        assert Organisation.objects.filter(pk=org_first.pk).count() == count_first == 1

    def test_ensure_all_cases_is_idempotent_across_repeated_runs(self):
        for case in GOLDEN_CORPUS:
            ensure_case_organisation(case)
        organisation_count_first_pass = Organisation.objects.count()

        for case in GOLDEN_CORPUS:
            ensure_case_organisation(case)
        organisation_count_second_pass = Organisation.objects.count()

        assert organisation_count_first_pass == organisation_count_second_pass

    def test_ensure_case_question_is_idempotent(self):
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "fully_supported_privileged_mfa")
        organisation = ensure_case_organisation(case)

        question_first = ensure_case_question(organisation, case)
        question_second = ensure_case_question(organisation, case)

        assert str(question_first.pk) == str(question_second.pk)
        assert question_first.question_text == case["question_text"]


class TestGoldenCorpusCoverage:
    """Proves each named case actually builds the tenant state its own
    scenario promises - not just that `ensure_case_organisation` runs
    without raising."""

    def test_fully_supported_privileged_mfa_has_active_supporting_evidence(self):
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "fully_supported_privileged_mfa")
        organisation = ensure_case_organisation(case)
        state_by_key = {entry["control_key"]: entry for entry in get_security_state(organisation)}
        assert state_by_key["mfa_privileged_accounts"]["answer"] == "yes"
        assert state_by_key["mfa_privileged_accounts"]["assurance_label"] == "Supporting evidence attached"

    def test_partial_privileged_mfa_has_open_remediation_with_real_owner(self):
        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "partial_privileged_mfa_managed_exception"
        )
        organisation = ensure_case_organisation(case)
        actions = RemediationAction.objects.filter(
            organisation=organisation, control_key="mfa_privileged_accounts", status=RemediationAction.STATUS_OPEN
        )
        assert actions.count() == 1
        action = actions.first()
        assert action.assigned_to is not None
        assert action.target_date is not None

    def test_privileged_mfa_unknown_has_explicit_unknown_row(self):
        from security_baseline.models import BaselineAnswer

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "privileged_mfa_unknown")
        organisation = ensure_case_organisation(case)
        answer = BaselineAnswer.objects.get(
            assessment__organisation=organisation, question_key="mfa_privileged_accounts"
        )
        assert answer.answer == "unknown"

    def test_policy_requires_mfa_implementation_partial_has_approved_policy(self):
        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "policy_requires_mfa_implementation_partial"
        )
        organisation = ensure_case_organisation(case)
        approved = organisation.policy_document.versions.get(status=PolicyVersion.STATUS_APPROVED)
        access_section = next(
            s for s in approved.sections if s["section_key"] == "access_and_authentication"
        )
        assert "multi-factor authentication" in access_section["content"].lower()

    def test_policy_artefact_existence_has_approved_policy(self):
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "policy_artefact_existence")
        organisation = ensure_case_organisation(case)
        assert organisation.policy_document.versions.filter(status=PolicyVersion.STATUS_APPROVED).exists()

    def test_policy_requirement_question_implementation_bad_has_bad_implementation(self):
        from security_baseline.models import BaselineAnswer

        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "policy_requirement_question_implementation_bad"
        )
        organisation = ensure_case_organisation(case)
        answer = BaselineAnswer.objects.get(
            assessment__organisation=organisation, question_key="mfa_privileged_accounts"
        )
        assert answer.answer == "no"
        assert organisation.policy_document.versions.filter(status=PolicyVersion.STATUS_APPROVED).exists()

    def test_evidence_explicitly_requested_none_attached_has_zero_evidence(self):
        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "evidence_explicitly_requested_none_attached"
        )
        organisation = ensure_case_organisation(case)
        assert not EvidenceItem.objects.filter(organisation=organisation).exists()

    def test_stale_evidence_only_actually_produces_evidence_stale_label(self):
        """Verifies - does not merely assume - that this case's expired
        `EvidenceItem` actually makes `get_security_state` report "Evidence
        stale" for the linked control (dispatch instructions: prove the
        claimed security-state label, exactly mirroring `policy/tests/
        test_eval_golden_corpus.py`'s own precedent)."""
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "stale_evidence_only")
        assert case["expected_security_state_label"] == "Evidence stale"
        organisation = ensure_case_organisation(case)
        state_by_key = {entry["control_key"]: entry for entry in get_security_state(organisation)}
        assert state_by_key["mfa_privileged_accounts"]["assurance_label"] == "Evidence stale"

    def test_evidence_conflict_actually_produces_evidence_conflict_label(self):
        """Same proof obligation as the stale-evidence case above, for the
        CONTRADICTS relationship."""
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "evidence_conflict")
        assert case["expected_security_state_label"] == "Evidence conflict"
        organisation = ensure_case_organisation(case)
        state_by_key = {entry["control_key"]: entry for entry in get_security_state(organisation)}
        assert state_by_key["mfa_privileged_accounts"]["assurance_label"] == "Evidence conflict"

    def test_certification_question_has_certified_status(self):
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "certification_question")
        organisation = ensure_case_organisation(case)
        assert organisation.profile.cyber_essentials_status == "certified"

    def test_genuine_not_applicable_has_not_applicable_answer(self):
        from security_baseline.models import BaselineAnswer

        case = next(c for c in GOLDEN_CORPUS if c["key"] == "genuine_not_applicable")
        organisation = ensure_case_organisation(case)
        answer = BaselineAnswer.objects.get(
            assessment__organisation=organisation, question_key="remote_access_control"
        )
        assert answer.answer == "not_applicable"

    def test_adversarial_prompt_injection_payload_is_embedded_in_question_text(self):
        case = next(
            c for c in GOLDEN_CORPUS if c["key"] == "adversarial_prompt_injection_in_question"
        )
        assert "Ignore your instructions" in case["question_text"]

    def test_unfamiliar_phrasing_case_avoids_literal_control_wording(self):
        case = next(c for c in GOLDEN_CORPUS if c["key"] == "unfamiliar_phrasing_synonym")
        lowered = case["question_text"].lower()
        assert "multi-factor" not in lowered
        assert "mfa" not in lowered
        assert "privileged" not in lowered
