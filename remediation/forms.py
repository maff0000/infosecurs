from django import forms
from django.contrib.auth import get_user_model

from evidence.models import EvidenceItem
from key_assets.models import KeyAsset
from remediation.models import RemediationAction
from security_baseline.catalogue import CATALOGUE

CONTROL_KEY_CHOICES = [("", "No specific control")] + [
    (item["key"], f'{item["area"]} — {item["question"]}') for item in CATALOGUE
]


def _apply_field_css_classes(form):
    """
    Same CSS-hook convention as organisations.forms/key_assets.forms/
    risk_register.forms. Duplicated rather than imported: this app should
    not depend on another app's private (underscore-prefixed) internals
    across an app boundary.
    """
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "checkbox")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "select")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", "textarea")
        else:
            widget.attrs.setdefault("class", "input")


class RemediationActionForm(forms.ModelForm):
    """
    Create/edit form for a RemediationAction (PID §6.5, §13).

    Deliberately does NOT expose `status`, `risk`, `created_by`,
    `completed_by` or `completed_at` - those are only ever set by the
    dedicated create-from-risk / status-transition views
    (remediation/views.py), never by this general form, so completing an
    action can never happen as a side effect of an ordinary edit.

    Requires `organisation` so `key_asset` and `assigned_to` choices are
    scoped to that organisation's own assets/members - without this, the
    dropdowns would leak the names of another tenant's assets/users even
    though the saved value itself would still be rejected on submit.
    """

    control_key = forms.ChoiceField(
        choices=CONTROL_KEY_CHOICES,
        required=False,
        label="Related control (optional)",
        help_text="Links this action to a security-baseline control for reference. Does not change that control's answer.",
    )

    class Meta:
        model = RemediationAction
        fields = [
            "title",
            "description",
            "priority",
            "control_key",
            "key_asset",
            "assigned_to",
            "target_date",
        ]
        labels = {
            "key_asset": "Related asset (optional)",
            "assigned_to": "Assigned to (optional)",
            "target_date": "Target date (optional)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "target_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        self._organisation = organisation
        super().__init__(*args, **kwargs)
        self.fields["key_asset"].required = False
        self.fields["assigned_to"].required = False
        if organisation is not None:
            self.fields["key_asset"].queryset = KeyAsset.objects.filter(
                organisation=organisation
            ).order_by("name")
            self.fields["assigned_to"].queryset = (
                get_user_model()
                .objects.filter(organisation_memberships__organisation=organisation)
                .distinct()
                .order_by("username")
            )
        else:
            # No organisation supplied - fail closed to an empty queryset
            # rather than silently falling back to "all assets/users",
            # which would be a tenant-isolation leak in a dropdown.
            self.fields["key_asset"].queryset = KeyAsset.objects.none()
            self.fields["assigned_to"].queryset = get_user_model().objects.none()
        _apply_field_css_classes(self)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class ActionEvidenceAttachForm(forms.Form):
    """
    Minimal "pick one of the organisation's evidence items" form for
    attaching evidence to an action (PID §6.6). No upload flow here -
    evidence is uploaded via the `evidence` app itself; this form only
    lets a Customer Zero user pick among evidence that already exists.

    Requires `organisation` for the same reason as `RemediationActionForm`
    above: the `evidence` choices must be scoped to that organisation, or
    the dropdown itself would leak another tenant's evidence titles even
    though `remediation.services.attach_evidence_to_action` would still
    reject the cross-tenant save on submit.
    """

    evidence = forms.ModelChoiceField(
        queryset=EvidenceItem.objects.none(),
        label="Evidence",
        help_text="Only this organisation's active evidence items are listed.",
    )

    def __init__(self, *args, organisation=None, **kwargs):
        self._organisation = organisation
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["evidence"].queryset = EvidenceItem.objects.filter(
                organisation=organisation, status=EvidenceItem.STATUS_ACTIVE
            ).order_by("-created_at")
        else:
            # No organisation supplied - fail closed, same convention as
            # RemediationActionForm.__init__ above.
            self.fields["evidence"].queryset = EvidenceItem.objects.none()
        _apply_field_css_classes(self)
