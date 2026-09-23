from django import forms

from security_baseline.catalogue import CATALOGUE, CATALOGUE_BY_KEY
from security_baseline.models import ANSWER_CHOICES, ANSWER_UNKNOWN


def answer_field_name(question_key):
    return f"answer__{question_key}"


def note_field_name(question_key):
    return f"note__{question_key}"


class BaselineAssessmentForm(forms.Form):
    """
    One answer + one optional note per catalogue question.

    Deliberately a plain Form rather than a ModelForm: BaselineAnswer is a
    per-question row (organisations/models.py's OrganisationProfileForm has
    one field per model field; here the field set is driven by the
    versioned catalogue in security_baseline/catalogue.py instead), and the
    view maps each field back onto its own BaselineAnswer row.

    Every answer ChoiceField has no empty option and defaults to
    ANSWER_UNKNOWN - matching organisations/forms.py's tri-state discipline:
    a <select> always submits a value, so "not answered" is impossible to
    represent; "unknown" is the deliberate, visible default instead.

    `question_keys`: optional iterable of catalogue `key` values to build
    fields for, instead of the full catalogue. Added for the asset-specific
    protection-checks page (PID §0.5), which surfaces only the control
    questions relevant to one KeyAsset's category - it reuses this exact
    form class (same field names, choices, tri-state discipline) rather
    than a second, asset-local question model. Defaults to the full
    catalogue, so the general Security Baseline page's behaviour is
    unchanged.
    """

    def __init__(self, *args, question_keys=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = (
            CATALOGUE if question_keys is None
            else [CATALOGUE_BY_KEY[key] for key in question_keys]
        )
        for item in self.items:
            key = item["key"]
            self.fields[answer_field_name(key)] = forms.ChoiceField(
                choices=ANSWER_CHOICES,
                initial=ANSWER_UNKNOWN,
                label=item["question"],
                widget=forms.Select(attrs={"class": "select"}),
            )
            self.fields[note_field_name(key)] = forms.CharField(
                required=False,
                label="Note (optional)",
                widget=forms.Textarea(attrs={"class": "textarea", "rows": 2}),
            )

    def clean(self):
        cleaned_data = super().clean()
        for item in self.items:
            key = item["key"]
            note_field = note_field_name(key)
            if note_field in cleaned_data:
                cleaned_data[note_field] = cleaned_data[note_field].strip()
        return cleaned_data
