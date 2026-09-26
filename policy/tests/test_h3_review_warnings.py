"""
H3 correction tests (M006-AUDIT-0003 finding H3,
`docs/evidence/M006-AUDIT-0003.md`): "deterministic policy warnings on
manual redrafts". Central Architecture's own four numbered test cases,
plus the immutable-history regression and the AI-generated-draft
regression the correction's own design tension implies (see
`policy.services.compute_current_review_warnings`'s docstring).

Exercises the REAL service/view functions throughout - `create_new_draft_
from_approved`, `policy.views.policy_edit` (via a real HTTP POST),
`approve_policy_directly`, `security_baseline.services.save_baseline_
answers` (the one canonical write path for a baseline answer, per that
module's own docstring) - never a raw ORM bypass of product logic, and
(Case 4) `evidence.link_services.link_evidence_to_control` for a genuine
evidence-conflict scenario, mirroring `security_state/tests/
test_services.py::TestEvidenceConflict`'s own real-evidence-link
discipline exactly, rather than re-deriving/faking assurance_label.
"""
import datetime

import pytest
from django.urls import reverse

from ai_platform.policy_contracts import PolicyGenerationResult, PolicyReviewWarning, PolicySection
from ai_platform.testing import FakePolicyGateway
from evidence import link_services
from evidence.models import ControlEvidenceLink, EvidenceItem
from policy.models import PolicyVersion
from policy.services import (
    REVIEW_WARNING_SOURCE_AI,
    REVIEW_WARNING_SOURCE_DETERMINISTIC,
    approve_policy_directly,
    compute_current_review_warnings,
    create_new_draft_from_approved,
    generate_policy_draft,
)
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import ANSWER_NO, ANSWER_PARTIAL, ANSWER_UNKNOWN, ANSWER_YES
from security_baseline.services import save_baseline_answers

# Three distinct real catalogue keys (security_baseline/catalogue.py) so
# each case's own baseline mutation can never accidentally interact with
# another case's control.
GAP_CONTROL = "mfa_user_accounts"  # Case 1 (stays a gap throughout) / Case 2 (gap -> resolved)
NEW_GAP_CONTROL = "device_encryption"  # Case 3 (clean -> becomes a gap)
EVIDENCE_CONFLICT_CONTROL = "backups"  # Case 4


def _set_answer(organisation, key, answer, actor=None):
    """The one real write path for a `BaselineAnswer` row
    (`security_baseline.services.save_baseline_answers` - see its own
    module docstring: "There is no other place in the codebase that
    constructs or saves a BaselineAnswer")."""
    return save_baseline_answers(
        organisation,
        cleaned_data={answer_field_name(key): answer, note_field_name(key): ""},
        question_keys=[key],
        actor=actor,
    )


def _subjects(warnings):
    return {w["subject"] for w in warnings}


def _has_control(subjects, control_key):
    return any(control_key in subject for subject in subjects)


@pytest.mark.django_db
class TestCase1UnchangedGaps:
    def test_manual_redraft_carries_correct_warnings_through_create_edit_approve_and_display(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, GAP_CONTROL, ANSWER_NO, actor=user_a)

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )

        # --- create manual v2 via the real service function ---
        v2 = create_new_draft_from_approved(approved_v1, actor=user_a)
        subjects_at_creation = _subjects(v2.review_warnings)
        assert v2.review_warnings != []  # the exact defect H3 names: never []
        assert _has_control(subjects_at_creation, GAP_CONTROL)
        assert all(
            w["source"] == REVIEW_WARNING_SOURCE_DETERMINISTIC for w in v2.review_warnings
        )

        # --- edit v2's prose via the real HTTP edit path ---
        edit_data = {"title": v2.title, "next_review_date": ""}
        edit_data.update(
            {f"section__{s['section_key']}": s["content"] + " Edited." for s in v2.sections}
        )
        edit_response = client_a.post(
            reverse("policy:version_edit", args=[org_a.id, v2.id]), data=edit_data
        )
        assert edit_response.status_code == 302
        v2.refresh_from_db()
        assert all("Edited." in s["content"] for s in v2.sections)
        # Warnings remain after the edit - prose is never a source of them.
        assert _subjects(v2.review_warnings) == subjects_at_creation

        # --- approve v2 via the real approval service function ---
        approved_v2 = approve_policy_directly(
            v2, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        approved_subjects = _subjects(approved_v2.review_warnings)
        assert _has_control(approved_subjects, GAP_CONTROL)

        # --- exposed through the existing accepted presentation mechanism ---
        detail_response = client_a.get(
            reverse("policy:version_detail", args=[org_a.id, approved_v2.id])
        )
        assert detail_response.status_code == 200
        assert GAP_CONTROL.encode() in detail_response.content


@pytest.mark.django_db
class TestCase2GapResolvedBeforeApproval:
    def test_stale_warning_does_not_survive_to_preview_or_approval(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, GAP_CONTROL, ANSWER_UNKNOWN, actor=user_a)

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )
        draft = create_new_draft_from_approved(approved_v1, actor=user_a)
        assert _has_control(_subjects(draft.review_warnings), GAP_CONTROL)

        # Canonical control subsequently becomes a clean confirmed "yes".
        _set_answer(org_a, GAP_CONTROL, ANSWER_YES, actor=user_a)

        # Before approval: the current (preview) warning view is refreshed.
        preview = compute_current_review_warnings(draft)
        assert not _has_control(_subjects(preview), GAP_CONTROL)

        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert not _has_control(_subjects(approved.review_warnings), GAP_CONTROL)


@pytest.mark.django_db
class TestCase3NewGapAppearsBeforeApproval:
    def test_new_warning_appears_in_preview_and_survives_to_approval(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, NEW_GAP_CONTROL, ANSWER_YES, actor=user_a)

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )
        draft = create_new_draft_from_approved(approved_v1, actor=user_a)
        assert not _has_control(_subjects(draft.review_warnings), NEW_GAP_CONTROL)

        # Canonical state becomes partial/unknown before approval.
        _set_answer(org_a, NEW_GAP_CONTROL, ANSWER_PARTIAL, actor=user_a)

        preview = compute_current_review_warnings(draft)
        assert _has_control(_subjects(preview), NEW_GAP_CONTROL)

        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert _has_control(_subjects(approved.review_warnings), NEW_GAP_CONTROL)


@pytest.mark.django_db
class TestCase4EvidenceConflictPreserved:
    def test_evidence_conflict_warning_survives_manual_draft_and_approval(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, EVIDENCE_CONFLICT_CONTROL, ANSWER_YES, actor=user_a)

        # A genuine, real, active CONTRADICTS link - same mechanism/fixture
        # shape as security_state/tests/test_services.py::TestEvidenceConflict.
        evidence = EvidenceItem.objects.create(
            organisation=org_a,
            kind=EvidenceItem.KIND_EXTERNAL_REFERENCE,
            title="Contradicting evidence",
            reference_url="https://example.test/evidence",
            recorded_by=user_a,
        )
        link_services.link_evidence_to_control(
            org_a,
            evidence,
            EVIDENCE_CONFLICT_CONTROL,
            ControlEvidenceLink.RELATIONSHIP_CONTRADICTS,
            "",
            user_a,
        )

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )
        draft = create_new_draft_from_approved(approved_v1, actor=user_a)
        assert _has_control(_subjects(draft.review_warnings), EVIDENCE_CONFLICT_CONTROL)

        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert _has_control(_subjects(approved.review_warnings), EVIDENCE_CONFLICT_CONTROL)


@pytest.mark.django_db
class TestImmutableHistoryRegression:
    def test_approved_and_superseded_versions_review_warnings_never_retroactively_change(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, GAP_CONTROL, ANSWER_UNKNOWN, actor=user_a)

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )
        draft = create_new_draft_from_approved(approved_v1, actor=user_a)
        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        frozen_warnings = list(approved.review_warnings)
        assert _has_control(_subjects(frozen_warnings), GAP_CONTROL)

        # Canonical state changes AGAIN after this version is already approved.
        _set_answer(org_a, GAP_CONTROL, ANSWER_YES, actor=user_a)
        approved.refresh_from_db()
        assert approved.review_warnings == frozen_warnings

        # Now supersede it with a second approved version.
        second_draft = create_new_draft_from_approved(approved, actor=user_a)
        approve_policy_directly(
            second_draft, actor=user_a, next_review_date=datetime.date(2028, 1, 1)
        )
        approved.refresh_from_db()
        assert approved.status == PolicyVersion.STATUS_SUPERSEDED
        assert approved.review_warnings == frozen_warnings  # unchanged by supersession itself

        # A further canonical state change after supersession must not
        # mutate the superseded row's own warnings either.
        _set_answer(org_a, GAP_CONTROL, ANSWER_NO, actor=user_a)
        approved.refresh_from_db()
        assert approved.review_warnings == frozen_warnings


@pytest.mark.django_db
class TestAiGeneratedDraftApprovalRegression:
    def test_ai_authored_warnings_are_not_discarded_by_the_approval_recompute(
        self, org_a, user_a, person_a, assign_policy_authoriser
    ):
        """Not one of Central Architecture's own 4 numbered cases, but
        implied by the design tension `compute_current_review_warnings`'s
        docstring names explicitly: an AI-generated draft's own
        AI-authored `review_warnings` entries must survive
        `_finalise_approval`'s recompute untouched, while the deterministic
        subset is still correctly current at approval time."""
        assign_policy_authoriser(org_a, person_a)
        _set_answer(org_a, GAP_CONTROL, ANSWER_UNKNOWN, actor=user_a)

        ai_subject = "AI-authored: unusual third-party data-sharing clause noticed"
        result = PolicyGenerationResult(
            policy_title="Fixture Ltd Information Security Policy",
            sections=[PolicySection(section_key="purpose_and_scope", content="Purpose text.")],
            review_warnings=[
                PolicyReviewWarning(
                    subject=ai_subject,
                    detail="Manually verify this clause before relying on it.",
                )
            ],
            resolved_model="fixture-model/fake-v1",
            prompt_version="policy_generation_v2",
        )
        gateway = FakePolicyGateway(mode="valid", result=result)
        draft = generate_policy_draft(org_a, actor=user_a, gateway=gateway)

        subjects_at_generation = _subjects(draft.review_warnings)
        assert ai_subject in subjects_at_generation
        assert _has_control(subjects_at_generation, GAP_CONTROL)
        sources_at_generation = {w["subject"]: w["source"] for w in draft.review_warnings}
        assert sources_at_generation[ai_subject] == REVIEW_WARNING_SOURCE_AI

        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        approved_subjects = _subjects(approved.review_warnings)
        # The AI-authored warning survives approval's recompute...
        assert ai_subject in approved_subjects
        # ...and the deterministic subset is still correctly current.
        assert _has_control(approved_subjects, GAP_CONTROL)
