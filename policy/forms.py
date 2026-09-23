"""
Forms for the section-based draft editor and the approval-confirmation step
(M004 PID §16-18 - m004-2b-policy-lifecycle dispatch).
"""
from __future__ import annotations

from django import forms

from ai_platform.policy_contracts import ALLOWED_SECTION_KEYS
from policy.section_labels import section_label

SECTION_FIELD_PREFIX = "section__"


def section_field_name(section_key: str) -> str:
    return f"{SECTION_FIELD_PREFIX}{section_key}"


class PolicyVersionEditForm(forms.Form):
    """
    One labelled textarea per section (PID §16 "not raw JSON/markdown
    editing... a simple section-based editor is sufficient"), plus a title
    field and a next-review-date field.

    Deliberately a plain `forms.Form`, NOT a `forms.ModelForm` bound to the
    `PolicyVersion` instance. `sections` is a JSONField holding a list of
    `{section_key, content}` dicts - it has no per-field model attribute a
    ModelForm could bind a widget to, so there is no clean ModelForm shape
    for "one field per section" here. That also means the well-known
    ModelForm trap `risk_register.views.risk_edit` documents (`is_valid()`
    -> `full_clean()` -> `_post_clean()` -> `construct_instance()` mutating
    `self.instance` in place, before `.save()` is ever called) cannot occur
    here structurally: this form is never constructed with `instance=...`,
    so it has no model instance to mutate as a side effect of validation.
    The equivalent discipline is still applied at the call site
    (`policy.views.policy_edit`): every "previous value" needed for the
    Learning Signal Capture delta is read from `version` BEFORE this form's
    `cleaned_data` is ever applied back onto it - see that view's own
    comment for why this still matters even without ModelForm's specific
    trap.

    `section_keys` (constructor-only, not a model field) fixes exactly
    which sections this instance of the form edits, and in what order -
    the caller passes them already filtered to `ALLOWED_SECTION_KEYS`
    order and restricted to the section keys the version being edited
    already contains (PID §16 is a content editor for existing sections,
    not a section add/remove tool - restructuring which subject areas a
    drafted policy covers stays an AI-generation-time decision, PID §10.2).
    """

    title = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "input"}),
    )
    next_review_date = forms.DateField(
        required=False,
        # ISO format only - matches exactly what an HTML5 <input type="date">
        # always submits regardless of browser/OS locale, independent of
        # this project's own LANGUAGE_CODE ("en-gb")/localized
        # DATE_INPUT_FORMATS, which would otherwise expect DD/MM/YYYY.
        # `input_formats` controls parsing on submit; the widget's own
        # `format=` kwarg controls rendering - without it, DateInput falls
        # back to the locale-aware DATE_INPUT_FORMATS[0] ("en-gb" ->
        # DD/MM/YYYY) for the rendered `value` attribute, which an HTML5
        # `<input type="date">` silently refuses to parse: the raw HTML
        # `value` attribute is present but the DOM `.value` property
        # renders as an empty date picker in a real browser. Both must
        # agree on ISO format for the field to round-trip correctly
        # regardless of LANGUAGE_CODE.
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
        help_text="When this policy should next be reviewed.",
    )

    def __init__(self, *args, section_keys, **kwargs):
        super().__init__(*args, **kwargs)
        # Preserve ALLOWED_SECTION_KEYS order regardless of what order the
        # caller passed section_keys in (PID §16 "in ALLOWED_SECTION_KEYS
        # order").
        self.section_keys = [key for key in ALLOWED_SECTION_KEYS if key in section_keys]
        for key in self.section_keys:
            self.fields[section_field_name(key)] = forms.CharField(
                label=section_label(key),
                required=True,
                widget=forms.Textarea(attrs={"rows": 6, "class": "textarea"}),
            )


class PolicyApprovalConfirmForm(forms.Form):
    """
    The single confirmation step shared by BOTH direct approval and
    external-recorded approval (PID §18): "Before either approval action
    completes, let the Account Holder confirm/adjust next_review_date...
    pre-filled but editable in the same confirmation form/step, not
    silently applied." The view supplies the pre-filled `initial` value
    (`policy.services.default_next_review_date()` unless the draft already
    carries one); this form only validates that whatever the Account
    Holder submits back is a real date.
    """

    next_review_date = forms.DateField(
        required=True,
        input_formats=["%Y-%m-%d"],  # see PolicyVersionEditForm.next_review_date's comment
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
        help_text="You can adjust this before confirming approval.",
    )


__all__ = [
    "PolicyVersionEditForm",
    "PolicyApprovalConfirmForm",
    "section_field_name",
    "SECTION_FIELD_PREFIX",
]
