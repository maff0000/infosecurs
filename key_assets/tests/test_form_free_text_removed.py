"""
M008-FREE-TEXT-REPLACEMENT-REGISTER.md Row 3, corrected by the
M008C-WI2a dispatch while folding this existing flow into Stage 3
(docs/design/M008B-STAGES-1-3-CATALOGUE.md §3.7): `KeyAssetForm.
description` is retired - no Textarea, and a POSTed "description" value
is silently ignored (not an error - Django's own ordinary behaviour for
a POST key with no matching form field), never persisted.
"""
from __future__ import annotations

import pytest
from django import forms
from django.urls import reverse

from key_assets.forms import KeyAssetForm
from key_assets.models import KeyAsset


def test_key_asset_form_has_no_description_field():
    form = KeyAssetForm()
    assert "description" not in form.fields


def test_no_field_on_key_asset_form_renders_as_a_textarea():
    form = KeyAssetForm()
    offending = [
        name for name, field in form.fields.items() if isinstance(field.widget, forms.Textarea)
    ]
    assert offending == []


@pytest.mark.django_db
def test_posting_a_description_value_is_ignored_not_persisted(client_a, org_a):
    response = client_a.post(
        reverse("key_assets:create", args=[org_a.id]),
        {
            "name": "Payroll system",
            "category": "business_application",
            "criticality": "high",
            "description": "This should never be saved via the form.",
        },
    )

    assert response.status_code == 302
    asset = KeyAsset.objects.get(organisation=org_a)
    assert asset.name == "Payroll system"
    assert asset.description == ""
