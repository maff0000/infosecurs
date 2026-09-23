import pytest

from ai_platform.interpretation_orchestration import InterpretationFailed
from ai_platform.testing import FakeInterpretationGateway
from key_assets.models import KeyAsset
from risk_register.interpretation_service import interpret_draft_risks
from risk_register.models import Risk
from risk_register.services import generate_draft_risks
from security_baseline.catalogue import CATALOGUE_VERSION
from security_baseline.models import BaselineAnswer, BaselineAssessment


def _endpoint_org_with_draft_risks(org, *, device_encryption_note=""):
    """Real, scenario-engine-produced draft risks for `org`: one confirmed
    endpoint asset + a canonical 'device_encryption' answer of 'no' (a real
    trigger for the endpoint_device_encryption_loss_theft scenario), so
    tests exercise the actual catalogue-instantiated shape interpretation
    is meant to run over, not a hand-built Risk row."""
    KeyAsset.objects.create(
        organisation=org,
        name=f"{org.name} endpoint",
        description="A staff laptop used for everyday work.",
        category="endpoint",
        criticality="medium",
        status=KeyAsset.STATUS_CONFIRMED,
    )
    assessment = BaselineAssessment.objects.create(organisation=org, catalogue_version=CATALOGUE_VERSION)
    BaselineAnswer.objects.create(
        assessment=assessment,
        question_key="device_encryption",
        answer="no",
        note=device_encryption_note,
    )
    return generate_draft_risks(org)


# --- Happy path ---------------------------------------------------------------

@pytest.mark.django_db
def test_interpret_draft_risks_updates_fields_and_sets_invocation_record(org_a):
    created = _endpoint_org_with_draft_risks(org_a)
    assert created  # sanity: real scenario-instantiated draft risks exist

    gateway = FakeInterpretationGateway(mode="valid")
    updated = interpret_draft_risks(org_a, gateway=gateway)

    assert len(updated) == len(created)
    for risk in updated:
        risk.refresh_from_db()
        assert risk.rationale.startswith("Fixture rationale for candidate")
        assert risk.proposed_treatment.startswith("Fixture proposed treatment for candidate")
        assert risk.ai_invocation_record is not None
        assert risk.status == Risk.STATUS_DRAFT_AI_SUGGESTED  # PID §2: still requires confirmation


@pytest.mark.django_db
def test_interpret_draft_risks_returns_empty_when_no_eligible_draft_risks(org_a):
    gateway = FakeInterpretationGateway(mode="valid")
    updated = interpret_draft_risks(org_a, gateway=gateway)
    assert updated == []
    assert gateway.calls == []  # never even called the gateway


@pytest.mark.django_db
def test_interpret_draft_risks_does_not_touch_confirmed_or_dismissed_risks(org_a):
    created = _endpoint_org_with_draft_risks(org_a)
    confirmed = created[0]
    confirmed.status = Risk.STATUS_CONFIRMED
    confirmed.save(update_fields=["status"])
    original_rationale = confirmed.rationale

    gateway = FakeInterpretationGateway(mode="valid")
    updated = interpret_draft_risks(org_a, gateway=gateway)

    assert confirmed.id not in [r.id for r in updated]
    confirmed.refresh_from_db()
    assert confirmed.rationale == original_rationale


# --- Failure leaves every existing Risk row untouched ------------------------

@pytest.mark.django_db
def test_interpret_draft_risks_leaves_risks_completely_untouched_on_failure(org_a):
    created = _endpoint_org_with_draft_risks(org_a)
    before = {
        r.id: (r.impact, r.likelihood, r.rationale, r.proposed_treatment, r.ai_invocation_record_id, r.updated_at)
        for r in created
    }

    gateway = FakeInterpretationGateway(mode="auth_error")  # not retryable
    with pytest.raises(InterpretationFailed):
        interpret_draft_risks(org_a, gateway=gateway)

    for risk in created:
        risk.refresh_from_db()
        after = (
            risk.impact,
            risk.likelihood,
            risk.rationale,
            risk.proposed_treatment,
            risk.ai_invocation_record_id,
            risk.updated_at,
        )
        assert after == before[risk.id]


@pytest.mark.django_db
def test_interpret_draft_risks_leaves_risks_untouched_after_retries_exhausted(org_a):
    created = _endpoint_org_with_draft_risks(org_a)
    before_rationales = {r.id: r.rationale for r in created}

    gateway = FakeInterpretationGateway(mode="always_fail_retryable")
    with pytest.raises(InterpretationFailed):
        interpret_draft_risks(org_a, gateway=gateway)

    for risk in created:
        risk.refresh_from_db()
        assert risk.rationale == before_rationales[risk.id]


# --- Candidate notes: real organisation free text, never an identifier ------

@pytest.mark.django_db
def test_candidate_notes_include_asset_description_and_relevant_baseline_note(org_a):
    _endpoint_org_with_draft_risks(org_a, device_encryption_note="Org A: encryption rollout is mid-way.")

    gateway = FakeInterpretationGateway(mode="valid")
    interpret_draft_risks(org_a, gateway=gateway)

    assert len(gateway.calls) == 1
    request, _prompt_version = gateway.calls[0]
    encryption_candidate = next(
        c for c in request.candidates if "loss or theft" in c.threat_event.lower()
    )
    assert "A staff laptop used for everyday work." in encryption_candidate.notes
    assert "Org A: encryption rollout is mid-way." in encryption_candidate.notes


@pytest.mark.django_db
def test_candidate_never_carries_a_risk_or_asset_identifier(org_a):
    created = _endpoint_org_with_draft_risks(org_a)
    real_ids = {str(r.id) for r in created} | {str(r.key_asset_id) for r in created}

    gateway = FakeInterpretationGateway(mode="valid")
    interpret_draft_risks(org_a, gateway=gateway)

    request, _prompt_version = gateway.calls[0]
    for candidate in request.candidates:
        wire = candidate.to_wire_dict()
        serialised = str(wire)
        for real_id in real_ids:
            assert real_id not in serialised


# --- Tenant isolation (PID §16, "the last item is critical") ----------------

@pytest.mark.django_db
def test_org_as_interpretation_call_never_includes_org_bs_facts(org_a, org_b):
    _endpoint_org_with_draft_risks(org_a, device_encryption_note="Org A secret note - never for org B.")
    _endpoint_org_with_draft_risks(org_b, device_encryption_note="Org B secret note - never for org A.")

    gateway = FakeInterpretationGateway(mode="valid")
    interpret_draft_risks(org_a, gateway=gateway)

    request, _prompt_version = gateway.calls[0]
    assert request.organisation_id == str(org_a.pk)
    serialised = str([c.to_wire_dict() for c in request.candidates])
    assert "Org B secret note" not in serialised
    assert str(org_b.pk) not in serialised


@pytest.mark.django_db
def test_org_as_interpretation_never_updates_org_bs_risks(org_a, org_b):
    created_a = _endpoint_org_with_draft_risks(org_a)
    created_b = _endpoint_org_with_draft_risks(org_b)
    before_b = {r.id: r.rationale for r in created_b}

    gateway = FakeInterpretationGateway(mode="valid")
    updated = interpret_draft_risks(org_a, gateway=gateway)

    assert {r.id for r in updated} == {r.id for r in created_a}
    for risk in created_b:
        risk.refresh_from_db()
        assert risk.rationale == before_b[risk.id]


@pytest.mark.django_db
def test_org_as_invocation_record_is_scoped_to_org_a_only(org_a, org_b):
    from ai_platform.models import AIInvocationRecord

    _endpoint_org_with_draft_risks(org_a)
    _endpoint_org_with_draft_risks(org_b)

    gateway = FakeInterpretationGateway(mode="valid")
    interpret_draft_risks(org_a, gateway=gateway)

    records = AIInvocationRecord.objects.filter(task_type=AIInvocationRecord.TASK_RISK_INTERPRETATION)
    assert records.count() == 1
    assert records.first().organisation_id == org_a.pk


# --- Revert-and-rerun proof (forge-engineer rule 14) -------------------------
# Measured, not assumed: interpret_draft_risks was temporarily edited to
# catch InterpretationFailed, resave every candidate Risk with
# ai_invocation_record forced to None (unchanged impact/likelihood/
# rationale/proposed_treatment, but a real .save() call), and re-raise -
# simulating a plausible "silently fall back instead of leaving state
# untouched" defect. Re-running this file's 10 tests then failed exactly 1:
# test_interpret_draft_risks_leaves_risks_completely_untouched_on_failure
# (it compares the full field tuple INCLUDING updated_at/
# ai_invocation_record_id, so the injected resave changed updated_at and
# tripped it). The other 9 passed, including
# test_interpret_draft_risks_leaves_risks_untouched_after_retries_exhausted -
# that second test is therefore disclosed as a weaker pin against this
# specific defect shape (it only compares rationale, which the injected bug
# did not change) - its real coverage is the retry-exhaustion path, not this
# guarantee; the first test is what actually carries the "leaves risks
# untouched" proof. The defect was then reverted and the full file re-ran
# green (10/10). See the dispatch report for the exact commands and counts.
