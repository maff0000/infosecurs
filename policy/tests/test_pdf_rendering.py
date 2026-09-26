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

I1 fix (M006-AUDIT-0004, `docs/evidence/M006-AUDIT-0004.md`): the classes
from `TestReviewWarningsZero` onward cover Central Architecture's own
required cases for `review_warnings` actually appearing in the rendered
PDF - zero/one/a representative 6-10 set/the maximum realistic current
`security_baseline.catalogue` set/escaping/historical integrity across
supersession. The four pre-existing page-count tests above were updated
to give their organisation a clean baseline (`_set_answers(..., ANSWER_
YES, ...)`) before approval, purely so `approve_policy_directly`'s own
existing real recompute (`_finalise_approval` -> `compute_current_review_
warnings`, H3 correction, unchanged here) does not inject this
organisation's real deterministic warnings into a fixture that was never
about warnings - this is a necessary and correct implication of I1 finally
making review_warnings visible in the PDF, not a change to the H3
recompute behaviour itself.
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
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
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
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
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
        assign_policy_authoriser(org_a, person_a)
        approve_policy_directly(version, actor=user_a, next_review_date=datetime.date(2027, 1, 1))

        _pdf_bytes, page_count = render_policy_pdf(version, org_a)
        assert page_count < 2, f"expected fewer than 2 pages for a near-empty policy, got {page_count}"
        assert not (2 <= page_count <= 4)

    def test_a_deliberately_too_long_policy_is_detected_as_over_four_pages(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
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
class TestReviewWarningsOne:
    def test_single_warning_subject_and_detail_appear_before_section_content(
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

        assert "Review warnings / items requiring attention" in text
        assert "Multi-factor authentication (admin) - mfa_privileged_accounts" in text
        assert "Canonical current state: Not sure (Not confirmed)." in text
        # Central Architecture: rendered BEFORE the main policy sections.
        assert text.index("Review warnings / items requiring attention") < text.index(
            "Purpose section body text."
        )


@pytest.mark.django_db
class TestReviewWarningsRepresentativeSet:
    def test_six_to_ten_warnings_all_present_none_silently_dropped(
        self, org_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        assign_policy_authoriser(org_a, person_a)
        warning_keys = CATALOGUE_KEYS[:8]  # 8 - within the required 6-10 range
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

        pdf_bytes, page_count = render_policy_pdf(version, org_a)
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert pdf_bytes[:5] == b"%PDF-"
        for warning in warnings:
            assert warning["subject"] in text, f"warning subject {warning['subject']!r} missing from rendered PDF"
            assert warning["detail"] in text, f"warning detail {warning['detail']!r} missing from rendered PDF"

        # Captured and reported (this dispatch's own report quotes the
        # actual number observed here), not silently asserted away either
        # direction - see this file's module docstring / the dispatch
        # report for the real result and its disposition against the
        # existing 2-4 page target.
        print(f"[I1 REPORT] 8-warning representative-set + realistic 8-section policy page count = {page_count}")


@pytest.mark.django_db
class TestReviewWarningsMaximumRealisticBaselineSet:
    def test_every_catalogue_control_unresolved_renders_every_warning_with_no_truncation(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        """Central Architecture's own worst-case instruction: construct
        the real maximum-realistic scenario (every current
        `security_baseline.catalogue.CATALOGUE` control simultaneously
        unresolved) via the real service path
        (`create_new_draft_from_approved` -> `approve_policy_directly`,
        exactly like `policy/tests/test_h3_review_warnings.py`'s own real
        cases), not a synthetic warnings list - and report the real page
        count honestly rather than forcing a fit."""
        assign_policy_authoriser(org_a, person_a)
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
            assert warning["subject"] in text, f"warning subject {warning['subject']!r} missing - silent drop"
            assert warning["detail"] in text, f"warning detail {warning['detail']!r} missing - silent drop"

        # Honest report, per Central Architecture's own explicit
        # instruction: "If the real approved Beta policy can no longer
        # remain within four pages with its warnings included, report that
        # rather than silently deleting disclosure." No forcing of a fit
        # here (content/margins/styles are unchanged from the rest of this
        # module) - see this dispatch's own report for the real number.
        print(
            f"[I1 REPORT] maximum-realistic-baseline-warning-set "
            f"({len(CATALOGUE_KEYS)} warnings) + realistic 8-section policy page count = {page_count}"
        )


@pytest.mark.django_db
class TestReviewWarningsEscaping:
    def test_hostile_script_shaped_warning_text_renders_as_inert_plain_text(
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

        # A PDF has no live script-execution model the way a browser does,
        # but confirm the same escape() discipline used for every other
        # piece of customer/AI-supplied text in this module is genuinely
        # applied: the document still parses as a well-formed PDF (a raw,
        # unescaped literal string containing an unbalanced/unescaped `(`
        # or `)` would corrupt the surrounding content-stream syntax), and
        # the hostile text comes back as inert extracted text, not markup
        # that altered the document structure.
        assert pdf_bytes[:5] == b"%PDF-"
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1  # parses cleanly - structure was not corrupted
        text = _normalize_ws(_extract_text(pdf_bytes))

        assert hostile_subject in text
        assert hostile_detail in text


@pytest.mark.django_db
class TestReviewWarningsHistoricalIntegrity:
    def test_superseded_versions_pdf_renders_its_own_frozen_warnings_never_current_state(
        self, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version
    ):
        """Directly proves the "PDF is an artefact of the approved
        historical version, not current live state" invariant (Central
        Architecture's own instruction) for the PDF artefact specifically -
        approve a version with warnings, generate its PDF, then change
        canonical state and create+approve a NEW draft from it (the real
        product action that supersedes it), and confirm regenerating the
        PDF for the ORIGINAL, now-superseded version still renders its own
        original, frozen warning set unchanged - never today's current
        warning state."""
        assign_policy_authoriser(org_a, person_a)
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

        original_pdf_bytes, _pc1 = render_policy_pdf(approved_v2, org_a)
        original_text = _normalize_ws(_extract_text(original_pdf_bytes))
        for warning in frozen_warnings:
            assert warning["subject"] in original_text
            assert warning["detail"] in original_text

        # Canonical state changes AFTER this version is already approved -
        # the control that drove the frozen warning above is now resolved.
        _set_answers(org_a, [gap_control], ANSWER_YES, actor=user_a)

        # The real product action that supersedes v2: a new draft is
        # created (against CURRENT state) and approved.
        draft_v3 = create_new_draft_from_approved(approved_v2, actor=user_a)
        approved_v3 = approve_policy_directly(
            draft_v3, actor=user_a, next_review_date=datetime.date(2028, 1, 1)
        )
        assert not any(gap_control in w["subject"] for w in approved_v3.review_warnings)

        approved_v2.refresh_from_db()
        assert approved_v2.status == PolicyVersion.STATUS_SUPERSEDED
        assert approved_v2.review_warnings == frozen_warnings  # untouched by supersession

        # Regenerate the PDF for the ORIGINAL (now superseded) version -
        # must still render its own original frozen warning, never
        # today's now-resolved state. (Not asserting the full rendered
        # text is byte/text-identical to `original_text`: `status`/
        # `get_status_display()` legitimately changed from "Approved" to
        # "Superseded" by the real supersession above - that field is NOT
        # one of `PROTECTED_WHILE_APPROVED_FIELDS` and is correctly
        # expected to differ. review_warnings is the field this invariant
        # is actually about, and it is checked explicitly below, plus
        # already confirmed unchanged at the DB level above.)
        regenerated_pdf_bytes, _pc2 = render_policy_pdf(approved_v2, org_a)
        regenerated_text = _normalize_ws(_extract_text(regenerated_pdf_bytes))
        for warning in frozen_warnings:
            assert warning["subject"] in regenerated_text
            assert warning["detail"] in regenerated_text
        # And never today's current (now-resolved) state's own warning
        # text for this control.
        assert not any(
            "not fully confirmed" in w["detail"] and gap_control in w["subject"]
            for w in approved_v3.review_warnings
        )
