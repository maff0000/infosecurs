from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from security_baseline.catalogue import CATALOGUE, CATALOGUE_BY_KEY
from security_baseline.models import ANSWER_CHOICES, ANSWER_UNKNOWN
from security_baseline.stage4 import QUESTION_COPY, offered_options


def answer_field_name(question_key):
    return f"answer__{question_key}"


def note_field_name(question_key):
    return f"note__{question_key}"


def option_field_name(question_key):
    return f"option__{question_key}"


def confirm_field_name(question_key):
    return f"confirm__{question_key}"


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

    M008C-WI2b note: this form class (and the per-question free-text
    `note__<key>` field it builds) is kept for `security_baseline.
    services.save_baseline_answers`'s own existing unit tests and for
    `policy`'s test fixtures (both construct it directly, never via an
    HTTP request) - it is deliberately NOT deleted. What changed is that,
    as of this WI, NO view anywhere in this codebase constructs this form
    from `request.POST` any more: `security_baseline.views.baseline_view`
    now unconditionally redirects into the new guided Stage 4 journey
    (`foundations_start`/`foundations_question`, both built on the new
    `StructuredAnswerForm` below), and `key_assets.views.key_asset_detail`
    was converted to the same `StructuredAnswerForm`. There is therefore
    no URL, in this codebase, that can turn an HTTP request into a write
    through this form any more - the free-text note path this WI's PID
    identifies as a reachable legacy bypass is genuinely unreachable, not
    merely hidden behind the new pages (see `security_baseline.views`'
    module docstring and this WI's own report for the full reasoning).

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


# M008B control 7's confirmation requirement - a required, explicit
# checkbox-style confirmation submitted in the SAME POST as
# `JML_NOT_APPLICABLE` itself (docs/design/M008B-QUESTION-CATALOGUE.md
# control 7). Deliberately specific to this one control/option_code pair,
# not a generic rule - no other control in the Revision 2 catalogue has an
# equivalent requirement (remote_access_control's NOT_APPLICABLE needs
# only the confirmed OrganisationProfile fact, no extra checkbox).
_JML_CONTROL_KEY = "joiner_mover_leaver"
_JML_NOT_APPLICABLE_OPTION_CODE = "JML_NOT_APPLICABLE"


class StructuredAnswerForm(forms.Form):
    """
    One `option_code` field (+ one confirmation checkbox field, for
    `joiner_mover_leaver` only) per control key in `question_keys`.

    This is the ONE form class every Stage 4 structured-answer write path
    in this codebase builds on: the one-question-at-a-time guided journey
    (`security_baseline.views.foundations_question`, `question_keys=[one
    key]`) and the asset-specific protection-checks page
    (`key_assets.views.key_asset_detail`, `question_keys=` that asset
    category's relevant subset) both use this exact class - mirroring
    `BaselineAssessmentForm`'s own historical "one form class, optionally
    filtered question_keys" shape, now for the structured option-code
    world.

    Each `option_code` `ChoiceField`'s `choices` are built from
    `security_baseline.stage4.offered_options(key, organisation)` ONLY -
    never from the full, ungated `security_baseline.structured_catalogue.
    STRUCTURED_OPTIONS` table, and never from anything the client sent.
    This is what makes a forged/unoffered option_code (e.g. a
    NOT_APPLICABLE option for a control that never has one, or a
    `JML_NOT_APPLICABLE` submitted when `OrganisationProfile.
    people_with_system_access_count != 1`) fail ordinary `ChoiceField`
    validation - rejected with a normal form error, nothing written,
    `security_baseline.services.record_structured_baseline_answer` never
    even called. `organisation` must be the already tenant-scoped
    `Organisation` the caller fetched via `get_member_organisation_or_404`
    - this form never looks an organisation up itself.
    """

    def __init__(self, *args, organisation, question_keys, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation
        self.question_keys = list(question_keys)
        # One per-request computation of what is actually offered - never
        # recomputed per field access, and never trusted from any earlier
        # render (a profile fact could, in principle, have changed between
        # this form's GET and this POST; re-deriving it fresh here means
        # the POST is always checked against the CURRENT facts, not a
        # stale snapshot).
        self.allowed_options_by_key = {
            key: offered_options(key, organisation) for key in self.question_keys
        }
        for key in self.question_keys:
            allowed = self.allowed_options_by_key[key]
            self.fields[option_field_name(key)] = forms.ChoiceField(
                choices=[(code, option.label) for code, option in allowed.items()],
                label=QUESTION_COPY[key]["question"],
                widget=forms.RadioSelect,
            )
            if key == _JML_CONTROL_KEY:
                self.fields[confirm_field_name(key)] = forms.BooleanField(
                    required=False,
                    label=(
                        "Confirm: no other staff, contractor, or "
                        "shared/service accounts exist for this "
                        "organisation"
                    ),
                )

    def clean(self):
        cleaned_data = super().clean()
        for key in self.question_keys:
            opt_field = option_field_name(key)
            if opt_field not in cleaned_data:
                # Already has a field-level error from ChoiceField
                # validation (missing/invalid option_code) - nothing
                # further to check for this control.
                continue
            option_code = cleaned_data[opt_field]
            if (
                key == _JML_CONTROL_KEY
                and option_code == _JML_NOT_APPLICABLE_OPTION_CODE
                and not cleaned_data.get(confirm_field_name(key))
            ):
                # Server-side enforcement, not just a hidden/pre-ticked
                # field: JML_NOT_APPLICABLE is never accepted without the
                # confirmation checkbox checked in this SAME submission,
                # even when the organisation's people_with_system_access_
                # count fact genuinely is 1 (docs/design/M008B-QUESTION-
                # CATALOGUE.md control 7).
                self.add_error(
                    opt_field,
                    "Confirm that no other staff, contractor, or "
                    "shared/service accounts exist before selecting "
                    "Not applicable.",
                )
        return cleaned_data
