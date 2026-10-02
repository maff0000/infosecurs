"""
M008A - service-level tests for `organisations.reset_service.
reset_customer_zero_organisation` (docs/evidence/M008A-RESET-DELETION-
MANIFEST.md).

These tests call the service function directly (not through HTTP) - see
`organisations/tests/test_reset_views.py` for the view-level/HTTP-surface
adversarial tests (same-name impostor, forged UUID, environment gates,
CSRF/confirmation discipline, access control).
"""
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from activity.models import ActivityEvent
from ai_platform.models import AIInvocationRecord
from ai_platform.questionnaire_drafting_contracts import OUTCOME_GAP
from ai_platform.questionnaire_interpretation_contracts import INTENT_IMPLEMENTATION, SCOPE_ALL
from evidence import link_services, storage
from evidence.models import ControlEvidenceLink, EvidenceItem
from governance.models import GovernanceRoleAssignment, OrganisationPerson
from governance.services import assign_role
from key_assets.models import CATEGORY_ENDPOINT, CRITICALITY_MEDIUM, KeyAsset
from organisations.models import (
    AuditEvent,
    CustomerZeroFixture,
    OrganisationMembership,
    OrganisationProfile,
)
from organisations.reset_service import (
    EXPECTED_DELETE_DIRECT_FK_MODELS,
    EXPECTED_PRESERVE_DIRECT_FK_MODELS,
    ModelDriftError,
    ResetAuthorityError,
    reset_customer_zero_organisation,
)
from policy.models import PolicyDocument, PolicyVersion
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from remediation.models import ActionEvidenceLink, RemediationAction
from risk_register.models import Risk
from security_baseline.models import (
    ANSWER_YES,
    AnswerSelectionDetail,
    BaselineAnswer,
    BaselineAssessment,
)
from security_baseline.services import record_structured_baseline_answer
from workplace.models import Workplace

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _upload(name="evidence.pdf"):
    return SimpleUploadedFile(name, MINIMAL_PDF, content_type="application/pdf")


def _create_evidence_item(organisation, user):
    """Real file on disk, via the real storage module - not a hand-waved
    DB row with no backing bytes."""
    stored_filename = storage.store_uploaded_file(organisation.id, _upload(), "pdf")
    return EvidenceItem.objects.create(
        organisation=organisation,
        kind=EvidenceItem.KIND_FILE,
        title="MFA screenshot",
        original_filename="evidence.pdf",
        stored_filename=stored_filename,
        file_type=EvidenceItem.FILE_TYPE_PDF,
        byte_size=len(MINIMAL_PDF),
        sha256="0" * 64,
        recorded_by=user,
    )


def _populate_every_delete_target(organisation, user):
    """
    Populates at least one row in every DELETE-classified model from the
    manifest, including one non-Account-Holder `OrganisationPerson` and
    one non-Account-Holder `GovernanceRoleAssignment` (by reassigning one
    of the Account Holder's three default roles away to a second person -
    the only way such a row can exist in this codebase, since
    `ensure_account_holder_person` always assigns all three to the Account
    Holder on genuine first bootstrap). Returns a dict of created objects
    for the caller's own assertions.
    """
    profile = OrganisationProfile.objects.create(
        organisation=organisation, legal_trading_name="Acme Synthetic Ltd"
    )
    audit_event = AuditEvent.objects.create(
        organisation=organisation, action=AuditEvent.ACTION_PROFILE_CREATED, actor=user
    )

    assessment = BaselineAssessment.objects.create(organisation=organisation, catalogue_version="v1")
    answer = BaselineAnswer.objects.create(
        assessment=assessment, question_key="mfa_user_accounts", answer=ANSWER_YES
    )
    # M008B WI1: a real AnswerSelectionDetail row, created via the real
    # service function (record_structured_baseline_answer) - not a
    # hand-rolled equivalent - mirroring this helper's own existing
    # "real file on disk via the real storage module" discipline above.
    recorded = record_structured_baseline_answer(
        organisation, "mfa_user_accounts", "MFA_USER_ALL_REQUIRED", actor=user
    )
    selection_detail = recorded.selection_detail

    workplace = Workplace.objects.create(
        organisation=organisation, name="HQ", type=Workplace.TYPE_DEDICATED_OFFICE
    )

    key_asset = KeyAsset.objects.create(
        organisation=organisation,
        name="Company laptop fleet",
        category=CATEGORY_ENDPOINT,
        criticality=CRITICALITY_MEDIUM,
    )

    risk = Risk.objects.create(
        organisation=organisation,
        title="Lost/stolen laptop",
        threat="Device theft",
        vulnerability="No full-disk encryption",
        rationale="Portable devices leave controlled premises.",
        proposed_treatment="Enable BitLocker on all laptops.",
        impact=3,
        likelihood=3,
        key_asset=key_asset,
    )

    evidence_item = _create_evidence_item(organisation, user)
    control_link = link_services.link_evidence_to_control(
        organisation=organisation,
        evidence=evidence_item,
        control_key="mfa_user_accounts",
        relationship=ControlEvidenceLink.RELATIONSHIP_SUPPORTS,
        rationale="",
        linked_by=user,
    )

    action = RemediationAction.objects.create(
        organisation=organisation, title="Roll out BitLocker", created_by=user
    )
    action_link = ActionEvidenceLink.objects.create(
        organisation=organisation, action=action, evidence=evidence_item, linked_by=user
    )

    document = PolicyDocument.objects.create(organisation=organisation)
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=1,
        title="Information Security Policy",
        sections=[{"section_key": "purpose_and_scope", "content": "Purpose."}],
        review_warnings=[],
        generation_source=PolicyVersion.GENERATION_SOURCE_MANUAL,
        created_by=user,
    )

    question = QuestionnaireQuestion.objects.create(
        organisation=organisation, question_text="Do you encrypt laptops?", created_by=user
    )
    response = QuestionnaireResponse.objects.create(
        organisation=organisation,
        question=question,
        intent_type=INTENT_IMPLEMENTATION,
        requirement_scope=SCOPE_ALL,
        outcome=OUTCOME_GAP,
        created_by=user,
    )

    activity_event = ActivityEvent.objects.create(
        organisation=organisation, event_type=ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED, actor=user
    )

    ai_record = AIInvocationRecord.objects.create(
        organisation=organisation,
        prompt_version="risk_generation_v1",
        model_alias="trinity-core",
        input_snapshot_hash="a" * 64,
    )

    account_holder_person = OrganisationPerson.objects.get(organisation=organisation, user=user)
    second_person = OrganisationPerson.objects.create(organisation=organisation, full_name="Jane Doe")
    reassigned = assign_role(
        organisation=organisation,
        role=GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER,
        person=second_person,
        assigned_by=user,
    )

    return {
        "profile": profile,
        "audit_event": audit_event,
        "assessment": assessment,
        "answer": answer,
        "selection_detail": selection_detail,
        "workplace": workplace,
        "key_asset": key_asset,
        "risk": risk,
        "evidence_item": evidence_item,
        "control_link": control_link,
        "action": action,
        "action_link": action_link,
        "document": document,
        "version": version,
        "question": question,
        "response": response,
        "activity_event": activity_event,
        "ai_record": ai_record,
        "account_holder_person": account_holder_person,
        "second_person": second_person,
        "reassigned_role_assignment": reassigned,
    }


@pytest.mark.django_db
class TestFullRoundTrip:
    def test_every_delete_target_removed_and_evidence_file_gone(
        self, customer_zero_bootstrap, evidence_storage_root
    ):
        user, organisation = customer_zero_bootstrap
        created = _populate_every_delete_target(organisation, user)
        file_path = os.path.join(
            str(evidence_storage_root), str(organisation.id), created["evidence_item"].stored_filename
        )
        assert os.path.isfile(file_path)

        reset_customer_zero_organisation(organisation, performed_by=user)

        assert not OrganisationProfile.objects.filter(organisation=organisation).exists()
        assert not AuditEvent.objects.filter(organisation=organisation).exists()
        assert not BaselineAssessment.objects.filter(organisation=organisation).exists()
        assert not BaselineAnswer.objects.filter(assessment=created["assessment"]).exists()
        # M008B WI1: AnswerSelectionDetail has no direct FK to Organisation
        # at all (only to BaselineAssessment) - it cascades automatically
        # when its parent BaselineAssessment row is deleted, exactly like
        # BaselineAnswer, and is not touched by any explicit organisation-
        # scoped delete call of its own.
        assert not AnswerSelectionDetail.objects.filter(
            pk=created["selection_detail"].pk
        ).exists()
        assert not AnswerSelectionDetail.objects.filter(assessment=created["assessment"]).exists()
        assert not Workplace.objects.filter(organisation=organisation).exists()
        assert not KeyAsset.objects.filter(organisation=organisation).exists()
        assert not Risk.objects.filter(organisation=organisation).exists()
        assert not EvidenceItem.objects.filter(organisation=organisation).exists()
        assert not ControlEvidenceLink.objects.filter(organisation=organisation).exists()
        assert not RemediationAction.objects.filter(organisation=organisation).exists()
        assert not ActionEvidenceLink.objects.filter(organisation=organisation).exists()
        assert not PolicyVersion.objects.filter(organisation=organisation).exists()
        assert not PolicyDocument.objects.filter(organisation=organisation).exists()
        assert not QuestionnaireQuestion.objects.filter(organisation=organisation).exists()
        assert not QuestionnaireResponse.objects.filter(organisation=organisation).exists()
        assert not ActivityEvent.objects.filter(organisation=organisation).exists()
        assert not AIInvocationRecord.objects.filter(organisation=organisation).exists()
        assert not OrganisationPerson.objects.filter(pk=created["second_person"].pk).exists()
        assert not GovernanceRoleAssignment.objects.filter(
            pk=created["reassigned_role_assignment"].pk
        ).exists()
        assert not os.path.exists(file_path)
        assert not os.path.isdir(os.path.join(str(evidence_storage_root), str(organisation.id)))

    def test_preserve_rows_unchanged(self, customer_zero_bootstrap):
        user, organisation = customer_zero_bootstrap
        created = _populate_every_delete_target(organisation, user)

        password_hash_before = user.password
        org_id_before = organisation.id
        org_name_before = organisation.name
        membership_pk = OrganisationMembership.objects.get(
            organisation=organisation, user=user
        ).pk
        fixture_pk = CustomerZeroFixture.objects.get(organisation=organisation).pk
        account_holder_pk = created["account_holder_person"].pk
        untouched_role_pks = set(
            GovernanceRoleAssignment.objects.filter(
                organisation=organisation, person=created["account_holder_person"]
            ).values_list("pk", flat=True)
        )
        assert len(untouched_role_pks) == 2  # the 2 NOT reassigned away

        reset_customer_zero_organisation(organisation, performed_by=user)

        user.refresh_from_db()
        organisation.refresh_from_db()
        assert user.password == password_hash_before
        assert organisation.id == org_id_before
        assert organisation.name == org_name_before
        assert OrganisationMembership.objects.filter(pk=membership_pk).exists()
        assert CustomerZeroFixture.objects.filter(pk=fixture_pk).exists()
        assert OrganisationPerson.objects.filter(pk=account_holder_pk).exists()
        for pk in untouched_role_pks:
            assignment = GovernanceRoleAssignment.objects.get(pk=pk)
            assert assignment.person_id == account_holder_pk


@pytest.mark.django_db
class TestRepeatability:
    def test_second_reset_is_a_safe_no_op_with_identical_end_state(self, customer_zero_bootstrap):
        user, organisation = customer_zero_bootstrap
        _populate_every_delete_target(organisation, user)

        reset_customer_zero_organisation(organisation, performed_by=user)

        account_holder_pk_after_first = OrganisationPerson.objects.get(
            organisation=organisation, user=user
        ).pk
        role_pks_after_first = set(
            GovernanceRoleAssignment.objects.filter(organisation=organisation).values_list(
                "pk", flat=True
            )
        )

        # Second reset against the already-reset organisation.
        reset_customer_zero_organisation(organisation, performed_by=user)

        assert (
            OrganisationPerson.objects.get(organisation=organisation, user=user).pk
            == account_holder_pk_after_first
        )
        role_pks_after_second = set(
            GovernanceRoleAssignment.objects.filter(organisation=organisation).values_list(
                "pk", flat=True
            )
        )
        assert role_pks_after_second == role_pks_after_first
        assert not OrganisationProfile.objects.filter(organisation=organisation).exists()
        assert not EvidenceItem.objects.filter(organisation=organisation).exists()


@pytest.mark.django_db
class TestSecondTenantUntouched:
    def test_other_organisations_rows_and_files_are_byte_for_byte_unchanged(
        self, customer_zero_bootstrap, org_a, user_a, member_a, evidence_storage_root
    ):
        cz_user, cz_org = customer_zero_bootstrap
        _populate_every_delete_target(cz_org, cz_user)

        other_key_asset = KeyAsset.objects.create(
            organisation=org_a,
            name="Org A's own laptop fleet",
            category=CATEGORY_ENDPOINT,
            criticality=CRITICALITY_MEDIUM,
        )
        other_evidence = _create_evidence_item(org_a, user_a)
        other_file_path = os.path.join(
            str(evidence_storage_root), str(org_a.id), other_evidence.stored_filename
        )
        with open(other_file_path, "rb") as fh:
            other_file_bytes_before = fh.read()

        reset_customer_zero_organisation(cz_org, performed_by=cz_user)

        assert KeyAsset.objects.filter(pk=other_key_asset.pk).exists()
        assert EvidenceItem.objects.filter(pk=other_evidence.pk).exists()
        assert os.path.isfile(other_file_path)
        with open(other_file_path, "rb") as fh:
            assert fh.read() == other_file_bytes_before


@pytest.mark.django_db
class TestModelDriftFailsClosed:
    def test_unexpected_organisation_fk_model_aborts_before_any_delete(
        self, customer_zero_bootstrap, monkeypatch
    ):
        user, organisation = customer_zero_bootstrap
        created = _populate_every_delete_target(organisation, user)

        import organisations.reset_service as reset_service_module

        real_live_labels = reset_service_module._live_organisation_direct_fk_model_labels

        def _fake_live_labels():
            return real_live_labels() | {"not_a_real_app.NotARealModel"}

        monkeypatch.setattr(
            reset_service_module, "_live_organisation_direct_fk_model_labels", _fake_live_labels
        )

        with pytest.raises(ModelDriftError):
            reset_customer_zero_organisation(organisation, performed_by=user)

        # Zero rows deleted - every populated row is still exactly there.
        assert OrganisationProfile.objects.filter(organisation=organisation).exists()
        assert EvidenceItem.objects.filter(organisation=organisation).exists()
        assert OrganisationPerson.objects.filter(pk=created["second_person"].pk).exists()
        assert GovernanceRoleAssignment.objects.filter(
            pk=created["reassigned_role_assignment"].pk
        ).exists()

    def test_the_real_unmodified_model_graph_passes_preflight(self):
        """
        Sanity check that the manifest-derived expected sets in
        `organisations.reset_service` actually match the REAL, unmodified
        model graph today - i.e. this dispatch's own manifest
        transcription is not itself already drifted. Guards against the
        above drift test passing only because it is comparing against a
        broken baseline.
        """
        from organisations.reset_service import _live_organisation_direct_fk_model_labels

        live = _live_organisation_direct_fk_model_labels()
        expected = EXPECTED_PRESERVE_DIRECT_FK_MODELS | EXPECTED_DELETE_DIRECT_FK_MODELS
        assert live - expected == set()


@pytest.mark.django_db
class TestBootstrapInvariantsSurviveByteForByte:
    def test_fresh_bootstrap_survives_a_reset_with_nothing_else_populated(
        self, customer_zero_bootstrap
    ):
        user, organisation = customer_zero_bootstrap

        password_before = user.password
        org_id_before = organisation.id
        membership_before = OrganisationMembership.objects.get(organisation=organisation, user=user)
        fixture_before = CustomerZeroFixture.objects.get(organisation=organisation)
        account_holder_before = OrganisationPerson.objects.get(organisation=organisation, user=user)
        role_assignments_before = {
            assignment.role: (assignment.pk, assignment.person_id)
            for assignment in GovernanceRoleAssignment.objects.filter(organisation=organisation)
        }
        assert len(role_assignments_before) == 3

        reset_customer_zero_organisation(organisation, performed_by=user)

        user.refresh_from_db()
        organisation.refresh_from_db()
        assert user.password == password_before
        assert organisation.id == org_id_before
        assert OrganisationMembership.objects.filter(pk=membership_before.pk).exists()
        assert CustomerZeroFixture.objects.filter(pk=fixture_before.pk).exists()
        assert OrganisationPerson.objects.filter(pk=account_holder_before.pk).exists()

        role_assignments_after = {
            assignment.role: (assignment.pk, assignment.person_id)
            for assignment in GovernanceRoleAssignment.objects.filter(organisation=organisation)
        }
        assert role_assignments_after == role_assignments_before


@pytest.mark.django_db
class TestAuthorityGuard:
    def test_refuses_an_organisation_that_is_not_the_fixture(self, org_a, user_a, member_a):
        with pytest.raises(ResetAuthorityError):
            reset_customer_zero_organisation(org_a, performed_by=user_a)
        # Nothing was deleted (there's nothing to delete here, but the
        # membership/organisation itself must obviously still exist).
        assert OrganisationMembership.objects.filter(organisation=org_a, user=user_a).exists()
