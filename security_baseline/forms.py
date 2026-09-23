from django import forms

from security_baseline.catalogue import CATALOGUE
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
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for item in CATALOGUE:
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
        for item in CATALOGUE:
            key = item["key"]
            note_field = note_field_name(key)
            if note_field in cleaned_data:
                cleaned_data[note_field] = cleaned_data[note_field].strip()
        return cleaned_data
