from django import forms

from evidence.models import ControlEvidenceLink
from security_baseline.catalogue import CATALOGUE

CONTROL_KEY_CHOICES = [
    (item["key"], f'{item["area"]} — {item["question"]}') for item in CATALOGUE
]


def _apply_field_css_classes(form):
    """
    Same CSS-hook convention as organisations.forms/key_assets.forms - see
    key_assets/forms.py's identical helper for why this is duplicated
    rather than imported (organisations/key_assets are read-only to this
    dispatch, and their helpers are private/underscore-prefixed).
    """
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "checkbox")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            widget.attrs.setdefault("class", "select")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", "textarea")
        else:
            widget.attrs.setdefault("class", "input")


class _EvidenceCommonFieldsMixin(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False
    )
    source_label = forms.CharField(
        max_length=255,
        required=False,
        label="Source / origin",
        help_text="Where this evidence came from, e.g. 'Microsoft 365 admin centre export'.",
    )
    observed_at = forms.DateField(
        required=False,
        label="Observed / captured date",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank if not known.",
    )
    valid_until = forms.DateField(
        required=False,
        label="Valid until (optional)",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Leave blank if this evidence has no known expiry.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class EvidenceFileUploadForm(_EvidenceCommonFieldsMixin):
    file = forms.FileField(
        help_text="PDF, PNG, JPEG or plain text only, up to 10 MiB. Checked by content, not filename.",
    )


class EvidenceExternalReferenceForm(_EvidenceCommonFieldsMixin):
    reference_url = forms.URLField(
        max_length=2048,
        label="Reference / URL",
        help_text="A link to where this evidence lives. Infosecurs does not fetch or crawl it.",
    )


class ControlEvidenceLinkForm(forms.Form):
    """
    Link one evidence item to one catalogue control (PID §6.4, §18).

    Deliberately a plain `forms.Form`, not a `ModelForm`: `organisation`,
    `evidence` and `linked_by` are never user-submitted values - they come
    from the tenant-scoped view (the evidence item and the authenticated
    user), exactly like `evidence.link_services.link_evidence_to_control`'s
    signature expects. Only the fields a Customer Zero user actually
    chooses appear here.
    """

    control_key = forms.ChoiceField(choices=CONTROL_KEY_CHOICES, label="Control")
    relationship = forms.ChoiceField(
        choices=ControlEvidenceLink.RELATIONSHIP_CHOICES,
        help_text="Does this evidence support, contradict, or just add context to the control's answer?",
    )
    rationale = forms.CharField(
        max_length=500,
        required=False,
        label="Rationale (optional)",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)
