from django import forms

from risk_register.models import IMPACT_CHOICES, LIKELIHOOD_CHOICES, Risk


def _apply_field_css_classes(form):
    """
    Same CSS-hook convention as organisations.forms/key_assets.forms.
    Duplicated rather than imported: both source apps are read-only to this
    dispatch and are private (underscore-prefixed) helpers not meant to be
    imported across app boundaries.
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


class RiskEditForm(forms.ModelForm):
    """
    Edit a risk's content and 1-5 impact/likelihood ratings before
    confirmation (PID §3 "edit a suggested risk", §8.2 "the customer can
    change them before confirmation").

    Deliberately does NOT expose `status`, `source`, `grounding_refs`,
    `assumptions` or any confirm/dismiss actor/timestamp field - those are
    only ever changed by the dedicated confirm/dismiss views
    (risk_register/views.py), never by this general edit form, so "AI draft
    cannot silently become confirmed" holds regardless of what a caller
    submits here.
    """

    impact = forms.TypedChoiceField(choices=IMPACT_CHOICES, coerce=int)
    likelihood = forms.TypedChoiceField(choices=LIKELIHOOD_CHOICES, coerce=int)

    class Meta:
        model = Risk
        fields = [
            "title",
            "threat",
            "vulnerability",
            "impact",
            "likelihood",
            "rationale",
            "proposed_treatment",
        ]
        widgets = {
            "threat": forms.Textarea(attrs={"rows": 2}),
            "vulnerability": forms.Textarea(attrs={"rows": 2}),
            "rationale": forms.Textarea(attrs={"rows": 3}),
            "proposed_treatment": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title
