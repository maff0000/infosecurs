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

M008-WI6 Finding B remediation (dell-debian Auditor, 2026-10-02)
SUPERSEDES the former M006-AUDIT-0004 "I1 fix" tests this file used to
carry from `TestReviewWarningsZero` onward. The I1 fix made
`review_warnings` actually render into the distributable PDF; a fresh
M008-WI6 Auditor proved live that this directly violates the master PID's
own binding rule (`docs/pids/M008-FOUNDATIONS-EXPERIENCE-REDESIGN.md`
§3.6: "Current state, proposed commitment and gap must remain separate,
even in polished language or a PDF") - it leaks current-state/gap
disclosure into the exact same PDF M008D-WI4's own
`implementation_status_rows` mechanism was carefully built to never
reach. `policy.pdf._build_flowables` no longer renders `review_warnings`
at all. The classes from `TestReviewWarningsNeverAppearInPdf` onward
replace the old "I1 fix" ones and prove the OPPOSITE outcome: review-
warning content, in any quantity/shape, never appears anywhere in the
extracted PDF text - zero/one/a representative 6-10 set/the maximum
realistic current `security_baseline.catalogue` set/hostile-script-shaped
text/historical integrity across supersession. `review_warnings` remains
visible IN-PRODUCT ONLY (`version_detail.html`/`approve.html` - unchanged,
out of this file's scope). The four pre-existing page-count tests above
still give their organisation a clean baseline (`_set_answers(...,
ANSWER_YES, ...)`) before approval purely so `approve_policy_directly`'s
own real recompute does not inject this organisation's real deterministic
warnings into a fixture that was never about warnings - unrelated to, and
unaffected by, this fix (that content was never going to reach the PDF
either way now).
"""
import datetime
import io

import pytest
from pypdf import PdfReader

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from policy.models import PolicyVersion
from policy.pdf import render_policy_pdf
from policy.services import (
    approve_policy_directly,
    create_new_draft_from_approved,
)
from security_baseline.catalogue import CATALOGUE_KEYS
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import ANSWER_UNKNOWN, ANSWER_YES
from security_baseline.services import save_baseline_answers


def _extract_text(pdf_bytes: bytes) -> str:
    """Real PDF text extraction (pypdf), not a raw `pdf_bytes` substring
    check - reportlab's own content-stream layout splits a rendered
    Paragraph's text into multiple `Tj` operators at markup-token
    boundaries (confirmed directly against this exact reportlab==5.0.1 by
    rendering escaped `<script>...</script>`-shaped text and inspecting
    the raw stream bytes: `(hostile <) Tj (script) Tj (>) Tj (alert\\(1\\))
    Tj (<) Tj (/script) Tj (> tag test) Tj`), so a naive `b"..." in
    pdf_bytes` check is not reliable for asserting rendered text content
    once it contains any of `<`/`>`/`&`. `pypdf`'s `extract_text()`
    correctly reconstructs the full run in reading order."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def _normalize_ws(s: str) -> str:
    """Collapse all whitespace runs (including the newlines pypdf inserts
    at every reportlab-wrapped line break within one paragraph, which are
    not present in the original stored `subject`/`detail` string) down to
    single spaces, so a `subject`/`detail` containment or ordering check
    against extracted text is not sensitive to exactly where the PDF
    happened to wrap a line."""
    return " ".join(s.split())


def _set_answers(organisation, keys, answer, actor=None):
    """Set the same baseline answer for every key in `keys`, through the
    one real write path (`security_baseline.services.save_baseline_
    answers`), mirroring `policy/tests/test_h3_review_warnings.py`'s own
    `_set_answer` singular helper but for setting several/all catalogue
    controls in one call (needed for the maximum-realistic-baseline-set
    case below)."""
    cleaned_data = {}
    for key in keys:
        cleaned_data[answer_field_name(key)] = answer
        cleaned_data[note_field_name(key)] = ""
    return save_baseline_answers(organisation, cleaned_data=cleaned_data, question_keys=keys, actor=actor)


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
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        # I1 fix: review_warnings are now actually rendered, so
        # approve_policy_directly's own real recompute (`_finalise_
        # approval` -> `compute_current_review_warnings`) would otherwise
        # inject this organisation's real current deterministic warnings
        # (every catalogue control defaults to "unknown" with no
        # BaselineAnswer row) into THIS page-count-only fixture. Keep the
        # baseline clean so this test measures section-content page count
        # in isolation - review-warnings-in-the-PDF has its own dedicated
        # test classes below.
        _set_answers(org_a, CATALOGUE_KEYS, ANSWER_YES, actor=user_a)
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
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        # I1 fix: keep the baseline clean (see the identical comment on
        # test_realistic_length_policy_renders_two_to_four_pages above) so
        # this near-empty-content fixture isn't inflated by a real
        # deterministic review-warnings set.
        _set_answers(org_a, CATALOGUE_KEYS, ANSWER_YES, actor=user_a)
        version = make_draft_version(
            org_a,
            title="Too Short Ltd Policy",
            sections=[{"section_key": "purpose_and_scope", "content": "One short sentence."}],
        )
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        _pdf_bytes, page_count = render_policy_pdf(version, org_a)
        assert page_count < 2, f"expected fewer than 2 pages for a near-empty policy, got {page_count}"
        assert not (2 <= page_count <= 4)

    def test_a_deliberately_too_long_policy_is_detected_as_over_four_pages(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        # I1 fix: keep the baseline clean (see the identical comment above).
        # Not load-bearing for THIS direction (already far over 4 pages on
        # content alone), kept for consistency/isolation with its sibling
        # test above.
        _set_answers(org_a, CATALOGUE_KEYS, ANSWER_YES, actor=user_a)
        long_paragraph = (
            "This is one deliberately repeated sentence used only to construct a policy "
            "that is far longer than any real Infosecurs policy should ever be. "
        ) * 60
        sections = [
            {"section_key": key, "content": long_paragraph} for key in ALLOWED_SECTION_KEYS
        ]
        version = make_draft_version(org_a, title="Too Long Ltd Policy", sections=sections)
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
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        # I1 fix: keep the baseline clean (see the identical comment on
        # TestPdfPageCountRealisticPolicy above) - this test's own point is
        # isolation of the page COUNTER between calls, not warnings.
        _set_answers(org_a, CATALOGUE_KEYS, ANSWER_YES, actor=user_a)

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


# --- I1 fix tests (M006-AUDIT-0004, docs/evidence/M006-AUDIT-0004.md) -----------
#
# Central Architecture's own required cases: zero warnings; one warning;
# a representative 6-10 warning set; the maximum realistic current
# baseline warning set; escaping/safety; historical integrity (a
# superseded version's PDF must keep rendering its own frozen warnings,
# never today's current state).


@pytest.mark.django_db
class TestReviewWarningsZero:
    def test_no_warnings_section_at_all_when_review_warnings_is_empty(
        self, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        # Constructed directly as already-approved (mirroring policy/tests/
        # test_h3_review_warnings.py's own `approved_v1` fixtures) rather
        # than via approve_policy_directly - that service call's own
        # `_finalise_approval` always recomputes review_warnings from this
        # organisation's REAL current security_baseline state (H3
        # correction, unchanged/out of scope here), which would silently
        # inject this organisation's real deterministic warnings instead of
        # testing "the renderer faithfully shows whatever review_warnings
        # this exact version row already has" - the one thing policy/pdf.py
        # itself is responsible for.
        version = make_draft_version(
            org_a, status=PolicyVersion.STATUS_APPROVED, review_warnings=[]
        )

        pdf_bytes, _page_count = render_policy_pdf(version, org_a)
        text = _extract_text(pdf_bytes)

        # Entirely omitted, not an empty/awkward heading with nothing under
        # it (Central Architecture's own instruction).
        assert "Review warnings" not in text
        assert "items requiring attention" not in text


@pytest.mark.django_db
class TestReviewWarningsNeverAppearInPdf:
    """
    M008-WI6 Finding B remediation (dell-debian Auditor, 2026-10-02) - the
    Auditor's own technique, reproduced as a permanent regression suite:
    generate a real PDF for a version with non-empty `review_warnings`,
    pypdf-extract its text, and assert NONE of the review-warning text
    appears anywhere in the extracted bytes, regardless of how many/which
    controls are unresolved, whether the content is hostile-script-shaped,
    or whether the version has since been superseded.
    """

    def test_single_warning_subject_and_detail_never_appear_in_pdf_text(
        self, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        version = make_draft_version(
            org_a,
            status=PolicyVersion.STATUS_APPROVED,
            sections=[{"section_key": "purpose_and_scope", "content": "Purpose section body text."}],
            review_warnings=[
                {
                    "subject": "Multi-factor authentication (admin) - mfa_privileged_accounts",
                    "detail": (
                        "Canonical current state: Not sure (Not confirmed). This control's "
                        "implementation is not fully confirmed - review before approving "
                        "this policy."
                    ),
                    "source": "deterministic",
                }
            ],
        )

        pdf_bytes, _page_count = render_policy_pdf(version, org_a)
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert "Review warnings" not in text
        assert "items requiring attention" not in text
        assert "Multi-factor authentication (admin) - mfa_privileged_accounts" not in text
        assert "Canonical current state" not in text
        # The normative section content is unaffected by this fix.
        assert "Purpose section body text." in text

    def test_representative_warning_set_entirely_absent_from_pdf_text(
        self, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        warning_keys = CATALOGUE_KEYS[:8]  # 8 - within the old 6-10 representative range
        warnings = [
            {
                "subject": f"Representative area {i} - {key}",
                "detail": f"Representative detail text for control '{key}', warning number {i}.",
                "source": "deterministic",
            }
            for i, key in enumerate(warning_keys)
        ]
        version = make_draft_version(
            org_a,
            status=PolicyVersion.STATUS_APPROVED,
            title="Fixture Ltd Information Security Policy",
            sections=_realistic_sections(),
            review_warnings=warnings,
        )

        pdf_bytes, _page_count = render_policy_pdf(version, org_a)
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert pdf_bytes[:5] == b"%PDF-"
        for warning in warnings:
            assert warning["subject"] not in text, (
                f"warning subject {warning['subject']!r} leaked into the PDF - "
                "review_warnings must never reach the distributable PDF"
            )
            assert warning["detail"] not in text, (
                f"warning detail {warning['detail']!r} leaked into the PDF - "
                "review_warnings must never reach the distributable PDF"
            )
        # Every normative section's own content is still present and
        # unaffected by this fix.
        for key in ALLOWED_SECTION_KEYS:
            assert _REALISTIC_SECTION_CONTENT[key][:40] in text

    def test_maximum_realistic_baseline_warning_set_still_entirely_absent(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        """Central Architecture's own worst case (every current
        `security_baseline.catalogue.CATALOGUE` control simultaneously
        unresolved), built via the real service path
        (`create_new_draft_from_approved` -> `approve_policy_directly`,
        exactly like `policy/tests/test_h3_review_warnings.py`'s own real
        cases) - proving the opposite outcome from the old I1 test: even
        the maximum realistic warning set leaks nothing into the PDF."""
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        _set_answers(org_a, CATALOGUE_KEYS, ANSWER_UNKNOWN, actor=user_a)

        approved_v1 = make_draft_version(
            org_a,
            version_number=1,
            status=PolicyVersion.STATUS_APPROVED,
            sections=_realistic_sections(),
        )
        draft = create_new_draft_from_approved(approved_v1, actor=user_a)
        assert len(draft.review_warnings) == len(CATALOGUE_KEYS), (
            f"expected one deterministic warning per current catalogue control "
            f"({len(CATALOGUE_KEYS)}), got {len(draft.review_warnings)} - the catalogue "
            "may have changed size since this test was written"
        )

        approved = approve_policy_directly(
            draft, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        assert len(approved.review_warnings) == len(CATALOGUE_KEYS)

        pdf_bytes, page_count = render_policy_pdf(approved, org_a)
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert pdf_bytes[:5] == b"%PDF-"
        for warning in approved.review_warnings:
            assert warning["subject"] not in text, f"warning subject {warning['subject']!r} leaked into the PDF"
            assert warning["detail"] not in text, f"warning detail {warning['detail']!r} leaked into the PDF"
        print(
            f"[M008-WI6 Finding B REPORT] maximum-realistic-baseline-warning-set "
            f"({len(CATALOGUE_KEYS)} warnings, now correctly excluded from the PDF) + "
            f"realistic 8-section policy page count = {page_count}"
        )

    def test_hostile_script_shaped_warning_text_is_simply_absent_not_merely_escaped(
        self, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        hostile_subject = "<script>alert('subject-xss')</script>"
        hostile_detail = "Detail with <img src=x onerror=alert(2)> and a raw & ampersand too."
        version = make_draft_version(
            org_a,
            status=PolicyVersion.STATUS_APPROVED,
            review_warnings=[
                {"subject": hostile_subject, "detail": hostile_detail, "source": "ai"}
            ],
        )

        pdf_bytes, _page_count = render_policy_pdf(version, org_a)

        assert pdf_bytes[:5] == b"%PDF-"
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1  # parses cleanly
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert hostile_subject not in text
        assert hostile_detail not in text
        assert "subject-xss" not in text

    def test_superseded_versions_pdf_never_renders_review_warnings_at_all(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        """Historical-integrity angle, inverted for Finding B: a
        superseded version's PDF must never render review_warnings either
        - confirming the fix applies uniformly to every PolicyVersion
        status `render_policy_pdf` is ever called against (PID §19's own
        "approved or superseded" download eligibility), not merely the
        currently-approved one. `review_warnings` itself is still
        persisted and untouched by supersession (unchanged H3 behaviour,
        out of this fix's scope) - only its PDF rendering is checked
        here."""
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        gap_control = CATALOGUE_KEYS[0]
        _set_answers(org_a, [gap_control], ANSWER_UNKNOWN, actor=user_a)

        approved_v1 = make_draft_version(
            org_a, version_number=1, status=PolicyVersion.STATUS_APPROVED
        )
        draft_v2 = create_new_draft_from_approved(approved_v1, actor=user_a)
        approved_v2 = approve_policy_directly(
            draft_v2, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        frozen_warnings = list(approved_v2.review_warnings)
        assert frozen_warnings != []
        assert any(gap_control in w["subject"] for w in frozen_warnings)

        draft_v3 = create_new_draft_from_approved(approved_v2, actor=user_a)
        approve_policy_directly(
            draft_v3, actor=user_a, next_review_date=datetime.date(2028, 1, 1)
        )
        approved_v2.refresh_from_db()
        assert approved_v2.status == PolicyVersion.STATUS_SUPERSEDED
        assert approved_v2.review_warnings == frozen_warnings  # untouched by supersession

        # Even though review_warnings is still persisted on this frozen
        # row (in-product display elsewhere still uses it), its PDF
        # rendering must never include any of this content.
        pdf_bytes, _pc = render_policy_pdf(approved_v2, org_a)
        text = _normalize_ws(_extract_text(pdf_bytes))
        for warning in frozen_warnings:
            assert warning["subject"] not in text
            assert warning["detail"] not in text
