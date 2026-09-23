import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from policy.models import ImmutablePolicyVersionError, PolicyDocument, PolicyVersion


@pytest.fixture
def document(org_a):
    return PolicyDocument.objects.create(organisation=org_a)


def _version(document, org_a, **overrides):
    defaults = dict(
        document=document,
        organisation=org_a,
        version_number=1,
        status=PolicyVersion.STATUS_DRAFT,
        title="Org A ISP",
        sections=[{"section_key": "purpose_and_scope", "content": "x"}],
        review_warnings=[],
    )
    defaults.update(overrides)
    return PolicyVersion.objects.create(**defaults)


# --- PolicyDocument: one per organisation -------------------------------------

def test_policy_document_one_per_organisation(org_a):
    PolicyDocument.objects.create(organisation=org_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PolicyDocument.objects.create(organisation=org_a)


# --- Draft: freely editable ----------------------------------------------------

def test_draft_version_can_be_edited_freely(document, org_a):
    version = _version(document, org_a)
    version.title = "Updated title"
    version.sections = [{"section_key": "purpose_and_scope", "content": "updated"}]
    version.review_warnings = [{"subject": "s", "detail": "d"}]
    version.next_review_date = timezone.now().date()
    version.save()
    version.refresh_from_db()
    assert version.title == "Updated title"
    assert version.sections == [{"section_key": "purpose_and_scope", "content": "updated"}]


def test_draft_to_approved_transition_itself_is_allowed(document, org_a):
    """The save that MOVES a version from draft to approved must succeed -
    the guard only blocks a LATER save against an already-approved row."""
    version = _version(document, org_a)
    version.status = PolicyVersion.STATUS_APPROVED
    version.approved_at = timezone.now()
    version.save()
    version.refresh_from_db()
    assert version.status == PolicyVersion.STATUS_APPROVED


# --- Approved: protected fields frozen ------------------------------------------

def test_editing_sections_after_approval_is_rejected(document, org_a):
    version = _version(
        document, org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
    )
    version.sections = [{"section_key": "purpose_and_scope", "content": "sneaky edit"}]
    with pytest.raises(ImmutablePolicyVersionError):
        version.save()
    version.refresh_from_db()
    assert version.sections == [{"section_key": "purpose_and_scope", "content": "x"}]


def test_editing_title_after_approval_is_rejected(document, org_a):
    version = _version(
        document, org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
    )
    version.title = "sneaky new title"
    with pytest.raises(ImmutablePolicyVersionError):
        version.save()


def test_editing_review_warnings_after_approval_is_rejected(document, org_a):
    version = _version(
        document, org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
    )
    version.review_warnings = [{"subject": "x", "detail": "y"}]
    with pytest.raises(ImmutablePolicyVersionError):
        version.save()


def test_editing_next_review_date_after_approval_is_rejected(document, org_a):
    version = _version(
        document, org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
    )
    version.next_review_date = timezone.now().date()
    with pytest.raises(ImmutablePolicyVersionError):
        version.save()


def test_editing_protected_field_after_superseded_is_rejected(document, org_a):
    version = _version(document, org_a, status=PolicyVersion.STATUS_SUPERSEDED)
    version.title = "sneaky"
    with pytest.raises(ImmutablePolicyVersionError):
        version.save()


def test_non_protected_field_can_still_change_after_approval(document, org_a):
    """Only the four PID §16 fields are frozen - status transitions and
    the supersession pointer must remain writable (e.g. an approved
    version being marked superseded when a later version replaces it)."""
    version = _version(
        document, org_a, status=PolicyVersion.STATUS_APPROVED, approved_at=timezone.now()
    )
    other = _version(document, org_a, version_number=2, status=PolicyVersion.STATUS_DRAFT)
    version.status = PolicyVersion.STATUS_SUPERSEDED
    version.superseded_by = other
    version.save()
    version.refresh_from_db()
    assert version.status == PolicyVersion.STATUS_SUPERSEDED
    assert version.superseded_by_id == other.id


# --- version_number uniqueness --------------------------------------------------

def test_unique_version_number_per_document(document, org_a):
    _version(document, org_a, version_number=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _version(document, org_a, version_number=1)
