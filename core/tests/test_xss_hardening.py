"""
M006 PID §11c - XSS / untrusted text.

Django's template auto-escaping is already global and this codebase adds
NO manual override anywhere: `grep -rn "|safe\\|mark_safe\\|format_html"`
across the whole repository (app code AND templates, outside `tests/`)
returns zero hits - confirmed as part of writing this file. So there is no
opt-out to inventory here; this module's job is to PROVE that default
escaping actually holds, end-to-end, through the real HTTP form for every
customer-editable text field PID §11c names: organisation name, a
governance person's name, a workplace name, evidence title/description,
remediation text, a policy edit, and a questionnaire question/source
label/edited answer.

Two hostile payloads are used throughout (PID §11c's own examples):

- `_SCRIPT_PAYLOAD` - a plain `<script>` tag.
- `_ATTR_BREAKOUT_PAYLOAD` - an attribute-breakout variant
  (`"><img src=x onerror=alert(1)>`), which would only be dangerous if a
  value were ever interpolated unescaped INSIDE an existing HTML attribute
  (a case plain auto-escaping still safely covers, since `"` becomes
  `&quot;`, but worth exercising separately from a bare `<script>` tag).

For each field: the payload is submitted through the real form/view (not
written directly via the ORM - the PID explicitly asks for the real
submission path), then the page(s) that render the value back are
fetched and checked. Each assertion has two halves, not one:

1. The raw, dangerous bytes (`<script`, `onerror=`) are NOT present
   anywhere in the response.
2. The auto-escaped form of the SAME payload (`&lt;script&gt;` /
   `&quot;&gt;&lt;img`) IS present - proving the value actually reached
   the page (safely encoded), not that the field was silently dropped,
   truncated, or the assertion is trivially vacuous.
"""
import pytest
from django.urls import reverse

from evidence.models import EvidenceItem
from governance.models import GovernanceRoleAssignment
from organisations.models import Organisation
from policy.models import PolicyDocument, PolicyVersion
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.tests.conftest import patch_questionnaire_generation_gateways
from remediation.models import RemediationAction
from workplace.models import Workplace

pytestmark = pytest.mark.django_db

_SCRIPT_PAYLOAD = "<script>alert(1)</script>"
_SCRIPT_PAYLOAD_ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"

_ATTR_BREAKOUT_PAYLOAD = '"><img src=x onerror=alert(1)>'
# Django's `escape()` renders `"` as `&quot;` and `<`/`>` as `&lt;`/`&gt;` -
# this is the exact escaped rendering of `_ATTR_BREAKOUT_PAYLOAD` above.
# Note deliberately NOT checked as a bare "onerror=alert(1)" substring
# marker: escaping only touches `< > & " '`, so that substring (having none
# of those characters) appears verbatim inside the SAFELY escaped form too
# - `&quot;&gt;&lt;img src=x onerror=alert(1)&gt;` is inert text, not a
# live attribute/tag, precisely because the surrounding `< > "` are
# encoded. The only bytes that would actually be dangerous are the
# complete, literal, UNESCAPED payload string appearing raw.
_ATTR_BREAKOUT_PAYLOAD_ESCAPED = "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"


def _assert_hostile_text_is_escaped(content: bytes, *, plain_html_escaped: str):
    assert b"<script>alert(1)</script>" not in content, (
        "raw, unescaped <script> payload leaked into rendered HTML - XSS"
    )
    assert _ATTR_BREAKOUT_PAYLOAD.encode() not in content, (
        "raw, unescaped attribute-breakout payload leaked into rendered HTML - XSS"
    )
    assert plain_html_escaped.encode() in content, (
        f"expected the auto-escaped form {plain_html_escaped!r} in the response - "
        f"if this is missing, the field may have been silently dropped rather than "
        f"safely rendered, which would make the raw-bytes check above meaningless"
    )


class TestOrganisationNameXSS:
    def test_organisation_name_is_escaped_on_overview_and_list(self, client_a):
        response = client_a.post(
            reverse("organisations:create"), data={"name": _SCRIPT_PAYLOAD}, follow=True
        )
        assert response.status_code == 200
        organisation = Organisation.objects.get(name=_SCRIPT_PAYLOAD)

        detail = client_a.get(reverse("organisations:detail", args=[organisation.id]))
        _assert_hostile_text_is_escaped(detail.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)

        listing = client_a.get(reverse("organisations:list"))
        _assert_hostile_text_is_escaped(listing.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)


class TestGovernancePersonNameXSS:
    def test_new_person_full_name_is_escaped(self, client_a, org_a):
        role_key = GovernanceRoleAssignment.ROLE_POLICY_AUTHORISER
        response = client_a.post(
            reverse("governance:roles", args=[org_a.id]),
            data={
                f"{role_key}-role": role_key,
                f"{role_key}-person": "",
                f"{role_key}-new_person_full_name": _ATTR_BREAKOUT_PAYLOAD,
                f"{role_key}-new_person_job_title": "",
            },
            follow=True,
        )
        assert response.status_code == 200
        _assert_hostile_text_is_escaped(
            response.content, plain_html_escaped=_ATTR_BREAKOUT_PAYLOAD_ESCAPED
        )


class TestWorkplaceNameXSS:
    def test_workplace_name_is_escaped_on_list(self, client_a, org_a):
        response = client_a.post(
            reverse("workplace:create", args=[org_a.id]),
            data={
                "name": _SCRIPT_PAYLOAD,
                "type": Workplace.TYPE_DEDICATED_OFFICE,
                "location_label": "",
                "approx_people_count": "",
                "is_primary": "on",
            },
            follow=True,
        )
        assert response.status_code == 200
        assert Workplace.objects.filter(organisation=org_a, name=_SCRIPT_PAYLOAD).exists()
        _assert_hostile_text_is_escaped(response.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)


class TestEvidenceTitleAndDescriptionXSS:
    def test_title_and_description_are_escaped_on_detail(self, client_a, org_a):
        response = client_a.post(
            reverse("evidence:add_reference", args=[org_a.id]),
            data={
                "title": _SCRIPT_PAYLOAD,
                "description": _ATTR_BREAKOUT_PAYLOAD,
                "source_label": "",
                "reference_url": "https://example.test/evidence-reference",
            },
            follow=True,
        )
        assert response.status_code == 200
        item = EvidenceItem.objects.get(organisation=org_a)
        assert item.title == _SCRIPT_PAYLOAD
        assert item.description == _ATTR_BREAKOUT_PAYLOAD

        detail = client_a.get(reverse("evidence:detail", args=[org_a.id, item.id]))
        _assert_hostile_text_is_escaped(detail.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)
        _assert_hostile_text_is_escaped(
            detail.content, plain_html_escaped=_ATTR_BREAKOUT_PAYLOAD_ESCAPED
        )

        listing = client_a.get(reverse("evidence:list", args=[org_a.id]))
        _assert_hostile_text_is_escaped(listing.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)


class TestRemediationTextXSS:
    def test_title_and_description_are_escaped_on_detail(self, client_a, org_a):
        response = client_a.post(
            reverse("remediation:create", args=[org_a.id]),
            data={
                "title": _SCRIPT_PAYLOAD,
                "description": _ATTR_BREAKOUT_PAYLOAD,
                "priority": RemediationAction.PRIORITY_MEDIUM,
                "control_key": "",
                "key_asset": "",
                "assigned_to": "",
                "target_date": "",
            },
            follow=True,
        )
        assert response.status_code == 200
        action = RemediationAction.objects.get(organisation=org_a)
        assert action.title == _SCRIPT_PAYLOAD

        detail = client_a.get(reverse("remediation:detail", args=[org_a.id, action.id]))
        _assert_hostile_text_is_escaped(detail.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)
        _assert_hostile_text_is_escaped(
            detail.content, plain_html_escaped=_ATTR_BREAKOUT_PAYLOAD_ESCAPED
        )


class TestPolicyEditXSS:
    def test_edited_title_and_section_content_are_escaped(self, client_a, org_a):
        document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
        version = PolicyVersion.objects.create(
            document=document,
            organisation=org_a,
            version_number=1,
            status=PolicyVersion.STATUS_DRAFT,
            title="Org Information Security Policy",
            sections=[{"section_key": "purpose_and_scope", "content": "Purpose text."}],
            review_warnings=[],
        )

        response = client_a.post(
            reverse("policy:version_edit", args=[org_a.id, version.id]),
            data={
                "title": _SCRIPT_PAYLOAD,
                "next_review_date": "",
                "section__purpose_and_scope": _ATTR_BREAKOUT_PAYLOAD,
            },
            follow=True,
        )
        assert response.status_code == 200
        version.refresh_from_db()
        assert version.title == _SCRIPT_PAYLOAD
        assert version.sections[0]["content"] == _ATTR_BREAKOUT_PAYLOAD

        _assert_hostile_text_is_escaped(response.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)
        _assert_hostile_text_is_escaped(
            response.content, plain_html_escaped=_ATTR_BREAKOUT_PAYLOAD_ESCAPED
        )


class TestQuestionnaireQuestionAndSourceLabelXSS:
    def test_question_text_and_source_label_are_escaped(self, client_a, org_a, monkeypatch):
        patch_questionnaire_generation_gateways(monkeypatch)

        response = client_a.post(
            reverse("questionnaire:analyse", args=[org_a.id]),
            data={"question_text": _SCRIPT_PAYLOAD, "source_label": _ATTR_BREAKOUT_PAYLOAD},
            follow=True,
        )
        assert response.status_code == 200
        question = QuestionnaireQuestion.objects.get(organisation=org_a)
        assert question.question_text == _SCRIPT_PAYLOAD
        assert question.source_label == _ATTR_BREAKOUT_PAYLOAD

        _assert_hostile_text_is_escaped(response.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)
        _assert_hostile_text_is_escaped(
            response.content, plain_html_escaped=_ATTR_BREAKOUT_PAYLOAD_ESCAPED
        )

        listing = client_a.get(reverse("questionnaire:list", args=[org_a.id]))
        _assert_hostile_text_is_escaped(listing.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)


class TestQuestionnaireEditedAnswerXSS:
    def test_edited_answer_text_is_escaped(self, client_a, org_a, user_a):
        question = QuestionnaireQuestion.objects.create(
            organisation=org_a, question_text="Do you use MFA?", created_by=user_a
        )
        response_obj = QuestionnaireResponse.objects.create(
            organisation=org_a,
            question=question,
            status=QuestionnaireResponse.STATUS_DRAFT,
            interpreted_requirement_summary="Asks about MFA.",
            intent_type="implementation",
            requirement_scope="all",
            selected_keys=["control:mfa_privileged_accounts"],
            evidence_explicitly_requested=False,
            outcome="GAP",
            ai_draft_text="No.",
            current_answer_text="No.",
            review_warnings=[],
            grounding_snapshot={"control:mfa_privileged_accounts": {"answer": "no"}},
            grounding_snapshot_hash="deadbeef",
            interpretation_prompt_version="questionnaire_interpretation_v1",
            drafting_prompt_version="questionnaire_drafting_v1",
            created_by=user_a,
        )

        response = client_a.post(
            reverse("questionnaire:response_edit", args=[org_a.id, response_obj.id]),
            data={"current_answer_text": _SCRIPT_PAYLOAD},
            follow=True,
        )
        assert response.status_code == 200
        response_obj.refresh_from_db()
        assert response_obj.current_answer_text == _SCRIPT_PAYLOAD

        _assert_hostile_text_is_escaped(response.content, plain_html_escaped=_SCRIPT_PAYLOAD_ESCAPED)
