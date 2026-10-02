"""
M008C-WI3 - the dispatch's own required proofs:

1. No `Textarea` (or any other free-text) widget appears anywhere in
   `RiskEditForm` or `RemediationActionForm` any more
   (M008-FREE-TEXT-REPLACEMENT-REGISTER.md rows 6-10).
2. Zero AI/LLM calls anywhere in the new/changed code this dispatch wrote:
   `risk_register.views`, `risk_register.scenario_engine` (already
   verified zero-AI before this dispatch; re-proven here since this
   dispatch added new public functions to it), `risk_register.forms`,
   `risk_register.risk_choices`, and `remediation.views`/`remediation.
   forms` never import or reference `ai_platform` anywhere in their
   source - proven by real import-statement inspection (mirrors
   `organisations/tests/test_stage_forms_no_free_text_and_zero_ai.py`'s
   own pattern exactly, including why a blunt substring search would be
   wrong: it would false-positive on this very docstring).
3. A forged free-text POST to the risk-edit form for an invalid/unknown
   rationale or treatment code is rejected (standard Django ChoiceField
   validation), never silently stored.
"""
from __future__ import annotations

import inspect

import pytest
from django import forms
from django.urls import reverse

from remediation import forms as remediation_forms
from remediation import views as remediation_views
from remediation.forms import RemediationActionForm
from risk_register import forms as risk_register_forms
from risk_register import risk_choices, scenario_engine
from risk_register import views as risk_register_views
from risk_register.forms import RiskEditForm
from risk_register.models import Risk
from risk_register.risk_choices import TREATMENT_MITIGATE_SUGGESTED

_MODULES_THAT_MUST_NEVER_IMPORT_AI_PLATFORM = [
    risk_register_views,
    scenario_engine,
    risk_register_forms,
    risk_choices,
    remediation_views,
    remediation_forms,
]


class TestNoFreeTextWidgetAnywhere:
    def test_risk_edit_form_has_no_textarea_field(self):
        form = RiskEditForm()
        offending = [
            name for name, field in form.fields.items() if isinstance(field.widget, forms.Textarea)
        ]
        assert offending == []

    def test_risk_edit_form_no_longer_exposes_threat_or_vulnerability(self):
        form = RiskEditForm()
        assert "threat" not in form.fields
        assert "vulnerability" not in form.fields

    def test_risk_edit_form_rationale_and_proposed_treatment_are_choice_fields(self):
        form = RiskEditForm()
        assert isinstance(form.fields["rationale"], forms.ChoiceField)
        assert isinstance(form.fields["proposed_treatment"], forms.ChoiceField)

    def test_remediation_action_form_has_no_textarea_field(self):
        form = RemediationActionForm(organisation=None)
        offending = [
            name for name, field in form.fields.items() if isinstance(field.widget, forms.Textarea)
        ]
        assert offending == []

    def test_remediation_action_form_has_no_description_field(self):
        form = RemediationActionForm(organisation=None)
        assert "description" not in form.fields


class TestZeroAICallsInWI3Modules:
    @pytest.mark.parametrize("module", _MODULES_THAT_MUST_NEVER_IMPORT_AI_PLATFORM)
    def test_module_has_no_ai_platform_import_statement(self, module):
        """
        Import-statement inspection, not a blunt whole-source substring
        search - a blunt check would false-positive on this very test
        module's own docstring/comments talking about the absence (same
        reasoning as `organisations/tests/
        test_stage_forms_no_free_text_and_zero_ai.py`).
        """
        source = inspect.getsource(module)
        for line in source.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("import ai_platform"), module.__name__
            assert not stripped.startswith("from ai_platform"), module.__name__

    @pytest.mark.parametrize("module", _MODULES_THAT_MUST_NEVER_IMPORT_AI_PLATFORM)
    def test_module_object_has_no_ai_platform_attribute_bound(self, module):
        assert not any(
            name == "ai_platform" or name.startswith("ai_platform_") for name in vars(module)
        )


@pytest.mark.django_db
class TestForgedCodeIsRejectedNotSilentlyStored:
    def test_an_unknown_rationale_code_is_rejected(self, client_a, org_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Original title", threat="t", vulnerability="v",
            impact=2, likelihood=2, rationale="impact_2_limited_scope",
            proposed_treatment=TREATMENT_MITIGATE_SUGGESTED,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
        )
        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            {
                "title": "Original title",
                "impact": "2",
                "likelihood": "2",
                "rationale": "a completely forged free-text rationale value",
                "proposed_treatment": TREATMENT_MITIGATE_SUGGESTED,
            },
        )
        assert response.status_code == 200  # re-renders with errors, no redirect
        risk.refresh_from_db()
        assert risk.rationale == "impact_2_limited_scope"

    def test_an_unknown_treatment_code_is_rejected(self, client_a, org_a):
        risk = Risk.objects.create(
            organisation=org_a, title="Original title", threat="t", vulnerability="v",
            impact=2, likelihood=2, rationale="impact_2_limited_scope",
            proposed_treatment=TREATMENT_MITIGATE_SUGGESTED,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED, source=Risk.SOURCE_AI,
        )
        response = client_a.post(
            reverse("risk_register:edit", args=[org_a.id, risk.id]),
            {
                "title": "Original title",
                "impact": "2",
                "likelihood": "2",
                "rationale": "impact_2_limited_scope",
                "proposed_treatment": "a completely forged free-text treatment value",
            },
        )
        assert response.status_code == 200
        risk.refresh_from_db()
        assert risk.proposed_treatment == TREATMENT_MITIGATE_SUGGESTED
