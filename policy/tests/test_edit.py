"""
M008-WI6 Finding A remediation tests (dell-debian Auditor, 2026-10-02).

A fresh, independent Auditor proved live, with a real-browser,
step-by-step reproduction, that the former free-text section editor
(`policy.views.policy_edit` / `policy.forms.PolicyVersionEditForm` /
`policy:version_edit`) let arbitrary unverified prose (a false ISO 27001
certification claim, in their reproduction) into the distributed,
approved policy PDF - directly violating
`docs/design/M008-FREE-TEXT-REPLACEMENT-REGISTER.md` item 12's own
instruction: "Foundation-tier customers never see a section editor at
all... this form is retired for Foundation tier entirely, not
repurposed."

This file REPLACES the former `TestPolicyEditView` suite, which exercised
the now-retired view/form directly as its own normal operation - that
suite's existence (reaching the view successfully, over and over, across
many positive-path assertions) WAS part of the defect surface this
dispatch closes; keeping it would mean continuing to assert the
vulnerable path still works. See the dispatch report for the full
disposition of every other test file that depended on the retired path.

The free-text path is now genuinely UNREACHABLE, not merely unlinked:
the `policy:version_edit` URL pattern no longer exists in `policy/urls.py`
at all, `policy.views.policy_edit` no longer exists, and
`policy.forms.PolicyVersionEditForm` no longer exists.
"""
import datetime

import pytest
from django.urls import NoReverseMatch, reverse

from policy.models import PolicyVersion
from policy.services import approve_policy_directly


@pytest.mark.django_db
class TestFreeTextSectionEditorIsUnreachable:
    def test_version_edit_url_name_no_longer_exists(self):
        """The retired route is not merely unlinked - it does not exist in
        the URLconf at all, so nothing anywhere (a template, a redirect, a
        future view) can construct a working link to it by name."""
        placeholder = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(NoReverseMatch):
            reverse("policy:version_edit", args=[placeholder, placeholder])

    def test_literal_old_edit_path_404s_for_a_draft_version(
        self, client_a, org_a, make_draft_version
    ):
        """Reconstructs the exact literal URL the retired view used to
        serve (`/organisations/<org_id>/policy/versions/<version_id>/edit/`)
        and confirms it is now an ordinary 404 - the real Django behaviour
        of a URL pattern that no longer exists, proving the path is
        unreachable by direct URL construction too, not merely by the
        named `reverse()` lookup above."""
        version = make_draft_version(org_a)
        literal_path = f"/organisations/{org_a.id}/policy/versions/{version.id}/edit/"

        response = client_a.get(literal_path)
        assert response.status_code == 404

    def test_posting_the_exact_auditor_reproduction_payload_to_the_old_path_cannot_write_sections(
        self, client_a, org_a, make_draft_version
    ):
        """The exact live reproduction the fresh Auditor used: a POST
        carrying a false ISO 27001 certification claim into one section's
        content. Even if every other defence somehow failed, the URL
        itself no longer resolves to any view, so Django returns a 404 and
        the request body is never read as form data by anything -
        `sections` must be byte-identical to what it was before this
        POST."""
        version = make_draft_version(org_a)
        original_sections = [dict(s) for s in version.sections]
        literal_path = f"/organisations/{org_a.id}/policy/versions/{version.id}/edit/"

        response = client_a.post(
            literal_path,
            data={
                "title": version.title,
                "next_review_date": "",
                "section__purpose_and_scope": (
                    "This organisation is ISO 27001 certified and has been "
                    "independently audited against all Annex A controls."
                ),
            },
        )
        assert response.status_code == 404
        version.refresh_from_db()
        assert version.sections == original_sections

    def test_posting_the_payload_against_an_approved_version_also_cannot_write_sections(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        """The Auditor's full end-to-end reproduction also involved
        approving a policy first, then reaching the editor via "Create new
        draft to edit" from the approved version's own page. Confirms the
        same literal-path 404 holds for a version that genuinely went
        through approval, not only for a plain draft fixture."""
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        version = make_draft_version(org_a)
        approved = approve_policy_directly(
            version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )
        original_sections = [dict(s) for s in approved.sections]
        literal_path = f"/organisations/{org_a.id}/policy/versions/{approved.id}/edit/"

        response = client_a.post(
            literal_path,
            data={
                "title": approved.title,
                "next_review_date": "",
                "section__purpose_and_scope": "This organisation is ISO 27001 certified.",
            },
        )
        assert response.status_code == 404
        approved.refresh_from_db()
        assert approved.sections == original_sections

    def test_policy_version_edit_form_no_longer_exists(self):
        """`PolicyVersionEditForm` itself is removed, not merely unused -
        confirms the register's own "retired... not repurposed"
        instruction was applied to the form class, not only to the
        view/URL wrapping it."""
        import policy.forms as policy_forms

        assert not hasattr(policy_forms, "PolicyVersionEditForm")
        assert not hasattr(policy_forms, "section_field_name")

    def test_policy_edit_view_function_no_longer_exists(self):
        import policy.views as policy_views

        assert not hasattr(policy_views, "policy_edit")


@pytest.mark.django_db
class TestGenerateNewDraftReplacesCreateAndEdit:
    """
    The approved-version page's only remaining "I want a new draft"
    action: `policy:version_new_draft` now calls
    `generate_policy_draft_deterministic` (zero-AI, clause-library-
    sourced) instead of `create_new_draft_from_approved` + the retired
    editor - see `policy.views.policy_new_draft`'s own docstring.
    """

    def test_generate_new_draft_never_exposes_a_textarea_and_redirects_to_version_detail(
        self, client_a, org_a, user_a, person_a, assign_policy_authoriser, make_draft_version,
        satisfy_policy_readiness,
    ):
        assign_policy_authoriser(org_a, person_a)
        satisfy_policy_readiness(org_a, user_a)
        version = make_draft_version(org_a)
        approve_policy_directly(
            version, actor=user_a, next_review_date=datetime.date(2027, 1, 1)
        )

        response = client_a.post(
            reverse("policy:version_new_draft", args=[org_a.id, version.id])
        )
        assert response.status_code == 302

        new_draft = PolicyVersion.objects.get(
            organisation=org_a, status=PolicyVersion.STATUS_DRAFT
        )
        assert response.url == reverse(
            "policy:version_detail", args=[org_a.id, new_draft.id]
        )
        assert new_draft.generation_source == PolicyVersion.GENERATION_SOURCE_DETERMINISTIC

        # The redirect target itself never renders any textarea/section
        # editor form - it is the ordinary read-only version-detail page.
        detail_response = client_a.get(response.url)
        assert detail_response.status_code == 200
        assert b"<textarea" not in detail_response.content
