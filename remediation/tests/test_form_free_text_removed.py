"""
M008-FREE-TEXT-REPLACEMENT-REGISTER.md row 10, closed by the M008C-WI3
dispatch: `RemediationActionForm.description` is retired entirely - no
Textarea, and a POSTed "description" value is silently ignored (not an
error - Django's own ordinary behaviour for a POST key with no matching
form field), never persisted - for all three routes this form serves
(`remediation:create`, `remediation:create_from_risk`, `remediation:edit`).

Mirrors `key_assets/tests/test_form_free_text_removed.py`'s own pattern
exactly (form-field assertion, widget-type assertion, and a real
POST-with-a-forged-free-text-value-is-ignored assertion).
"""
from __future__ import annotations

import pytest
from django import forms
from django.urls import reverse

from remediation.forms import RemediationActionForm
from remediation.models import RemediationAction


def test_remediation_action_form_has_no_description_field():
    form = RemediationActionForm(organisation=None)
    assert "description" not in form.fields


def test_no_field_on_remediation_action_form_renders_as_a_textarea():
    form = RemediationActionForm(organisation=None)
    offending = [
        name for name, field in form.fields.items() if isinstance(field.widget, forms.Textarea)
    ]
    assert offending == []


@pytest.mark.django_db
def test_posting_a_description_value_to_create_is_ignored_not_persisted(client_a, org_a):
    response = client_a.post(
        reverse("remediation:create", args=[org_a.id]),
        {
            "title": "Review supplier access",
            "description": "This should never be saved via the form.",
            "priority": "medium",
            "control_key": "",
            "key_asset": "",
            "assigned_to": "",
            "target_date": "",
        },
    )
    assert response.status_code == 302
    action = RemediationAction.objects.get(organisation=org_a)
    assert action.title == "Review supplier access"
    assert action.description == ""


@pytest.mark.django_db
def test_posting_a_description_value_to_edit_is_ignored_not_persisted(client_a, org_a, user_a):
    action = RemediationAction.objects.create(
        organisation=org_a,
        title="Original title",
        created_by=user_a,
        description="Programmatically-set, pre-existing description.",
    )
    client_a.post(
        reverse("remediation:edit", args=[org_a.id, action.id]),
        {
            "title": "Original title",
            "description": "This should never overwrite the existing description.",
            "priority": "medium",
            "control_key": "",
            "key_asset": "",
            "assigned_to": "",
            "target_date": "",
        },
    )
    action.refresh_from_db()
    assert action.description == "Programmatically-set, pre-existing description."
