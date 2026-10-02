from django import forms

from risk_register.models import IMPACT_CHOICES, LIKELIHOOD_CHOICES, Risk
from risk_register.risk_choices import (
    IMPACT_RATIONALE_CHOICES,
    LIKELIHOOD_RATIONALE_CHOICES,
    TREATMENT_CATEGORY_CHOICES,
)


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
    Edit a risk's 1-5 impact/likelihood ratings, and the closed-form
    rationale/treatment selections that go with them, before confirmation
    (PID §3 "edit a suggested risk", §8.2 "the customer can change them
    before confirmation").

    M008-FREE-TEXT-REPLACEMENT-REGISTER.md rows 6-9 (M008C-WI3 dispatch):

    - `threat`/`vulnerability` (rows 6-7) are REMOVED from this form
      entirely - they are read-only display of the matched scenario's own
      `threat_event`/`vulnerability` wording on the risk-edit/detail
      templates now, never a textarea here. The customer selects/confirms/
      dismisses a risk; they never rewrite the methodology's own threat/
      vulnerability wording. The underlying `Risk.threat`/`.vulnerability`
      columns are untouched - still populated at instantiation time by
      `risk_register.scenario_engine`, still read by
      `risk_register.interpretation_service._build_candidate` exactly as
      before (confirmed no behaviour change there).
    - `rationale` (row 8) is now a `ChoiceField`, not a `Textarea`: a small,
      versioned set of predefined rationale codes
      (`risk_register.risk_choices`), filtered to the codes relevant to
      whichever impact/likelihood rating is currently selected on THIS
      submission (see `_rationale_choices` below) - not a free-text note.
      The underlying column is unchanged; it now stores the selected code's
      stable string instead of open prose.
    - `proposed_treatment` (row 9) is now a `ChoiceField` over the fixed
      `risk_choices.TREATMENT_CATEGORY_CHOICES` (Accept / Mitigate via the
      suggested treatment / Mitigate via a different already-created
      action / Transfer) - again the same underlying column, now storing a
      selected category code.

    Legacy-value handling (both `rationale` and `proposed_treatment`,
    M008-FREE-TEXT-REPLACEMENT-REGISTER.md's own "old free-text values on
    existing rows stay visible read-only, never force-migrated" rule, item
    5's pattern, reused here): if the risk's CURRENTLY STORED value for
    either field is not one of the current catalogue's codes - e.g. the
    deterministic provenance sentence `scenario_engine._build_rationale`
    writes at instantiation time, the scenario's own `suggested_treatment`
    sentence written at instantiation time, a pre-M008C-WI3 customer
    free-text edit, OR (a conflict this dispatch's report flags
    explicitly) free text written by the optional, separate AI
    interpretation feature (`risk_register.interpretation_service.
    interpret_draft_risks`, which still writes its own prose straight into
    these same two columns and is out of this dispatch's scope to change) -
    that exact stored value is injected as one extra, clearly-labelled
    choice, so the form never crashes or silently drops it. Saving the form
    without explicitly picking a different option keeps that legacy value
    exactly as it was (needed for "no actual change -> no edit event"
    round-tripping); picking a different option replaces it with a real
    code going forward.

    Deliberately does NOT expose `status`, `source`, `grounding_refs`,
    `assumptions` or any confirm/dismiss actor/timestamp field - those are
    only ever changed by the dedicated confirm/dismiss views
    (risk_register/views.py), never by this general edit form, so "AI draft
    cannot silently become confirmed" holds regardless of what a caller
    submits here.
    """

    impact = forms.TypedChoiceField(choices=IMPACT_CHOICES, coerce=int)
    likelihood = forms.TypedChoiceField(choices=LIKELIHOOD_CHOICES, coerce=int)
    rationale = forms.ChoiceField(
        choices=[],
        label="Rationale for this rating",
        help_text=(
            "Pick the statement that best explains your impact or "
            "likelihood rating. The list below reflects the rating values "
            "currently selected above."
        ),
    )
    proposed_treatment = forms.ChoiceField(
        choices=[],
        label="Treatment",
        help_text="How you plan to treat this risk.",
    )

    class Meta:
        model = Risk
        fields = ["title", "impact", "likelihood", "rationale", "proposed_treatment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rationale"].choices = self._rationale_choices()
        self.fields["proposed_treatment"].choices = self._treatment_choices()
        _apply_field_css_classes(self)

    def _current_impact_likelihood(self):
        """
        The impact/likelihood pair the rationale choice-list should be built
        against: the SUBMITTED values when this form is bound (so a single
        submission that changes impact/likelihood AND rationale together
        validates against the newly-chosen rating, not the stale one), or
        the instance's current stored values on an unbound (GET) form.
        Falls back to the instance's value if the submitted value is
        missing/invalid - `fields["impact"]`/`["likelihood"]`'s own
        validation independently rejects a genuinely bad submission; this
        helper only needs *a* number to build a non-empty choice list, not
        to itself be the source of truth for validation.
        """
        instance_impact = getattr(self.instance, "impact", None)
        instance_likelihood = getattr(self.instance, "likelihood", None)
        if not self.is_bound:
            return instance_impact, instance_likelihood

        def _coerce(field_name, fallback):
            raw = self.data.get(self.add_prefix(field_name))
            try:
                return int(raw)
            except (TypeError, ValueError):
                return fallback

        return (
            _coerce("impact", instance_impact),
            _coerce("likelihood", instance_likelihood),
        )

    def _rationale_choices(self):
        impact, likelihood = self._current_impact_likelihood()
        choices = list(IMPACT_RATIONALE_CHOICES.get(impact, []))
        seen = {code for code, _label in choices}
        for code, label in LIKELIHOOD_RATIONALE_CHOICES.get(likelihood, []):
            if code not in seen:
                choices.append((code, label))
                seen.add(code)
        return self._with_legacy_value(choices, "rationale")

    def _treatment_choices(self):
        return self._with_legacy_value(list(TREATMENT_CATEGORY_CHOICES), "proposed_treatment")

    def _with_legacy_value(self, choices, field_name):
        """
        See this class's own docstring, "Legacy-value handling" - prepends
        the instance's current stored value as an extra choice when it
        isn't already one of the real catalogue codes, so it is never
        silently dropped/crashes the widget, and an unchanged resubmission
        of the form round-trips cleanly.
        """
        existing = getattr(self.instance, field_name, "") or ""
        known_codes = {code for code, _label in choices}
        if existing and existing not in known_codes:
            label = f"Existing note (not from this structured list): {existing}"
            choices = [(existing, label)] + choices
        return choices

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title
