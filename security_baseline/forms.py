from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from security_baseline.catalogue import CATALOGUE, CATALOGUE_BY_KEY
from security_baseline.models import ANSWER_CHOICES, ANSWER_UNKNOWN


def answer_field_name(question_key):
    return f"answer__{question_key}"


def note_field_name(question_key):
    return f"note__{question_key}"


class BaselineAnswerSelect(forms.Select):
    """
    Renders the real `ANSWER_CHOICES` exactly as an ordinary <select>, plus
    one extra, visibly **disabled** "Other - coming later" option appended
    to the end of the same control (Central Architecture baseline-UX
    correction, M006-AUDIT-0002 correction #1/#11).

    This option is deliberately NOT a member of `ANSWER_CHOICES` and is
    never added to this field's `choices` - it exists in the rendered HTML
    only. It carries the real HTML `disabled` attribute (so a real browser
    will not let a user select or submit it - disabled <option>s are
    excluded from form submission by the HTML spec itself) plus
    `aria-disabled="true"` for assistive-tech redundancy, since this
    codebase has no existing disabled-control-in-a-select convention to
    match. Even if a request somehow bypassed the browser and POSTed this
    option's value directly, `forms.ChoiceField.validate()` would still
    reject it as an invalid choice, because it is not a member of
    `self.choices` - there is no path, browser or otherwise, by which this
    option's value can become a stored `BaselineAnswer.answer`.

    Deliberately local to this one widget/field, not a change to
    `forms.Select` globally - every other <select> in this codebase is
    unaffected.

    No hidden text field, no backend "other" state, no schema change: this
    is exactly the low-risk, display-only portion of the structured-first
    baseline-UX decision authorised for this dispatch. The future
    "customer prose -> AI proposes mapping -> customer confirms" flow this
    option gestures at is explicitly NOT implemented here.
    """

    OTHER_VALUE = "other_coming_later"
    OTHER_LABEL = "Other - coming later"

    def render(self, name, value, attrs=None, renderer=None):
        html = super().render(name, value, attrs=attrs, renderer=renderer)
        extra_option = format_html(
            '<option value="{}" disabled aria-disabled="true">{}</option>',
            self.OTHER_VALUE,
            self.OTHER_LABEL,
        )
        # The extra option is appended just before the closing </select> tag
        # so it renders as a genuine sixth item in the same dropdown/control
        # group as the five real options, not a separate, oddly-placed
        # element. `str(html)`/`str(extra_option)` discard the SafeString
        # markers on the two already-escaped pieces before splicing them
        # together with plain str.replace() (SafeString does not override
        # .replace(), so calling it directly would silently degrade back to
        # an unmarked str and get re-escaped by the template engine) -
        # `mark_safe` on the combined result is what actually re-marks the
        # final, already-safe HTML as trusted for output.
        return mark_safe(str(html).replace("</select>", str(extra_option) + "</select>"))


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
                widget=BaselineAnswerSelect(attrs={"class": "select"}),
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
