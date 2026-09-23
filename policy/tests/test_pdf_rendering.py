"""
PDF page-count tests (PID §10.1, §19, §26 "length/page bound tested
through the accepted rendering path" - m004-2b-policy-lifecycle dispatch).

Two directions, per the dispatch instructions' own non-vacuity discipline:
1. a REALISTIC-length approved policy renders 2-4 pages inclusive;
2. the counting mechanism can actually detect a violation in BOTH
   directions (too short -> fewer than 2 pages; too long -> more than 4).
A test suite that only ever exercised the "happy" 2-4 page case could pass
even if the page-counting mechanism were silently broken (e.g. always
returning a hardcoded "3") - these deliberately-too-short/too-long cases
are what rules that out.
"""
import datetime

import pytest

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from policy.models import PolicyVersion
from policy.pdf import render_policy_pdf
from policy.services import approve_policy_directly

# A realistic paragraph of policy prose per section - proportionate SME
# wording, similar in register/length to what the real AI prompt
# (ai_platform/prompts/policy_generation_v1.py) asks for, not padded
# boilerplate. Roughly 550-700 characters per section across all eight
# PID §10.2 subject areas.
_REALISTIC_SECTION_CONTENT = {
    "purpose_and_scope": (
        "This policy sets out how Fixture Ltd protects the information and systems it "
        "relies on to operate. It applies to every member of staff, to any contractor "
        "working on Fixture Ltd's behalf, and to every device used to access company "
        "information, whether company-owned or personal. The policy exists so that "
        "everyone understands their part in keeping the business secure, and it is "
        "reviewed regularly so it keeps matching how the company actually works."
    ),
    "responsibilities_and_governance": (
        "Overall responsibility for information security sits with the Senior Leadership "
        "Representative, who ensures this policy is resourced and kept up to date. The "
        "Security Responsible Person coordinates day-to-day security activity, including "
        "responding to incidents and tracking open remediation work. The Policy "
        "Authoriser is responsible for reviewing and formally approving this policy and "
        "any future revision of it before it takes effect."
    ),
    "access_and_authentication": (
        "Staff must use a unique account for every system that holds company or customer "
        "information, and must never share login credentials with anyone else. "
        "Multi-factor authentication must be used on all privileged and administrative "
        "accounts, and is strongly encouraged for every other account where it is "
        "available. Access to a system should be removed promptly once someone no longer "
        "needs it, for example when they change role or leave the company."
    ),
    "devices_protection_and_updates": (
        "Every device used to access company information - laptop, phone or tablet - "
        "must be protected with a screen lock and must have security updates installed "
        "promptly when they become available. Staff must not disable security software "
        "that has been installed on a company device. A lost or stolen device must be "
        "reported immediately so access from that device can be revoked."
    ),
    "information_handling_and_backup": (
        "Confidential and personal information must only be shared with people who have "
        "a genuine business need to see it, and must not be copied to personal accounts "
        "or unapproved storage services. Important business information must be backed "
        "up appropriately, and backups should be checked periodically to confirm they "
        "can actually be restored if they are ever needed."
    ),
    "workplace_and_remote_working": (
        "Staff working from home or another remote location must take the same care over "
        "screen privacy, device security and confidential conversations as they would in "
        "a shared office. Printed material containing confidential information should "
        "not be left unattended, whether at home, in an office, or in a shared or "
        "coworking space."
    ),
    "security_incidents_and_reporting": (
        "Any suspected security incident - a lost device, a suspicious email, unexpected "
        "account activity, or anything else that looks wrong - must be reported to the "
        "Security Responsible Person as soon as it is noticed. Staff will never be "
        "penalised for reporting a genuine concern in good faith, even if it turns out to "
        "be nothing. Prompt reporting is what allows an incident to be contained quickly."
    ),
    "review_approval_and_document_control": (
        "This policy is reviewed at least once every twelve months, or sooner if the "
        "business changes significantly. Each version is approved by the Policy "
        "Authoriser before it takes effect, and a record is kept of who approved it and "
        "when. Earlier approved versions are retained rather than deleted, so there is "
        "always a clear history of what the policy required at any point in time."
    ),
}


def _realistic_sections() -> list:
    return [
        {"section_key": key, "content": _REALISTIC_SECTION_CONTENT[key]}
        for key in ALLOWED_SECTION_KEYS
    ]


@pytest.mark.django_db
class TestPdfPageCountRealisticPolicy:
    def test_realistic_length_policy_renders_two_to_four_pages(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(
            org_a,
            title="Fixture Ltd Information Security Policy",
            sections=_realistic_sections(),
        )
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        pdf_bytes, page_count = render_policy_pdf(version, org_a)

        assert pdf_bytes[:5] == b"%PDF-"
        assert 2 <= page_count <= 4, f"expected 2-4 pages for a realistic policy, got {page_count}"


@pytest.mark.django_db
class TestPdfPageCountMechanismDetectsViolations:
    """Non-vacuity: prove the counting mechanism would actually catch a
    policy that is too short or too long, not just report a plausible
    number for the one realistic fixture above."""

    def test_a_deliberately_too_short_policy_is_detected_as_under_two_pages(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        version = make_draft_version(
            org_a,
            title="Too Short Ltd Policy",
            sections=[{"section_key": "purpose_and_scope", "content": "One short sentence."}],
        )
        assign_policy_authoriser(org_a, person_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        _pdf_bytes, page_count = render_policy_pdf(version, org_a)
        assert page_count < 2, f"expected fewer than 2 pages for a near-empty policy, got {page_count}"
        assert not (2 <= page_count <= 4)

    def test_a_deliberately_too_long_policy_is_detected_as_over_four_pages(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        long_paragraph = (
            "This is one deliberately repeated sentence used only to construct a policy "
            "that is far longer than any real Infosecurs policy should ever be. "
        ) * 60
        sections = [
            {"section_key": key, "content": long_paragraph} for key in ALLOWED_SECTION_KEYS
        ]
        version = make_draft_version(org_a, title="Too Long Ltd Policy", sections=sections)
        assign_policy_authoriser(org_a, person_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        _pdf_bytes, page_count = render_policy_pdf(version, org_a)
        assert page_count > 4, f"expected more than 4 pages for a padded policy, got {page_count}"
        assert not (2 <= page_count <= 4)


@pytest.mark.django_db
class TestPdfPageCountIsolatedBetweenCalls:
    """The page counter is a per-call closure, not shared class/module
    state (see policy/pdf.py's own docstring) - prove two back-to-back
    renders of very differently-sized documents each report their own
    correct count, not a count contaminated by the previous call."""

    def test_repeated_calls_do_not_leak_page_counts_between_each_other(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)

        short_version = make_draft_version(
            org_a,
            version_number=1,
            title="Short",
            sections=[{"section_key": "purpose_and_scope", "content": "Short."}],
        )
        approve_policy_directly(
            short_version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        _bytes_1, count_1 = render_policy_pdf(short_version, org_a)

        long_version_source = make_draft_version(
            org_a,
            version_number=2,
            status=PolicyVersion.STATUS_DRAFT,
            title="Long",
            sections=[
                {"section_key": key, "content": _REALISTIC_SECTION_CONTENT[key] * 4}
                for key in ALLOWED_SECTION_KEYS
            ],
        )
        # Manually mark the first approved version superseded is not the
        # point of this test - approve the second draft directly is fine
        # since this test only cares about render page counts, not
        # lifecycle correctness (covered elsewhere).
        approve_policy_directly(
            long_version_source, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        _bytes_2, count_2 = render_policy_pdf(long_version_source, org_a)

        # Re-render the SHORT version again, after the long one - if the
        # counter were leaking state, this would now report an inflated
        # count.
        _bytes_3, count_3 = render_policy_pdf(short_version, org_a)

        assert count_1 == count_3
        assert count_2 > count_1
