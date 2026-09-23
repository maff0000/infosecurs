"""
Forms for the Workplace onboarding wizard (PID §9.1) and the general
create/edit flow ("We have several locations" - PID §9.1: "the one path
that reasonably needs a fuller add-another-workplace flow").
"""
from django import forms

from workplace.models import Workplace


def _apply_field_css_classes(form):
    """
    Same CSS-hook convention as organisations.forms/key_assets.forms's
    helper of the same name. Duplicated rather than imported - both of
    those apps are read-only to this dispatch, and key_assets.forms's own
    copy documents the same reasoning.
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


# ---------------------------------------------------------------------------
# Onboarding step 1 - "Where do people normally work?" (PID §9.1)
# ---------------------------------------------------------------------------
PATTERN_ALL_REMOTE = "all_remote"
PATTERN_ONE_OFFICE = "one_office"
PATTERN_SHARED_COWORKING = "shared_coworking"
PATTERN_OFFICE_AND_HOME = "office_and_home"
PATTERN_SEVERAL_LOCATIONS = "several_locations"

PATTERN_CHOICES = [
    (PATTERN_ALL_REMOTE, "Everyone works from home"),
    (PATTERN_ONE_OFFICE, "We have one office"),
    (PATTERN_SHARED_COWORKING, "We use a shared/coworking office"),
    (PATTERN_OFFICE_AND_HOME, "Office + home working"),
    (PATTERN_SEVERAL_LOCATIONS, "We have several locations"),
]


class WorkplacePatternForm(forms.Form):
    """Step 1 of the onboarding wizard: just the pattern choice."""

    pattern = forms.ChoiceField(
        choices=PATTERN_CHOICES,
        widget=forms.RadioSelect,
        label="Where do people normally work?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)


class _HeadcountMixin(forms.Form):
    """Shared optional approximate-headcount field, same validator as the model."""

    def clean_approx_people_count(self):
        value = self.cleaned_data.get("approx_people_count")
        if value is not None and value < 0:
            raise forms.ValidationError("Approximate headcount cannot be negative.")
        return value


class AllRemoteOnboardingForm(_HeadcountMixin):
    """
    Step 2 for the "Everyone works from home" pattern (PID §9.1 example:
    "4 staff / Home / remote working / distributed_home / approx people:
    4"). Name/type/location are fully determined by the pattern itself -
    only headcount is a genuinely open question, so that is the only
    field asked.
    """

    approx_people_count = forms.IntegerField(
        required=False,
        min_value=0,
        label="Approximately how many people?",
        help_text="Optional. Leave blank if not known.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)


class OneOfficeOnboardingForm(_HeadcountMixin):
    """Step 2 for the "We have one office" pattern."""

    name = forms.CharField(
        max_length=255,
        initial="Office",
        label="What should we call this office?",
    )
    location_label = forms.CharField(
        max_length=255,
        required=False,
        label="Location",
        help_text='Human-level, e.g. "Woking, Surrey" or "London". Optional.',
    )
    approx_people_count = forms.IntegerField(
        required=False,
        min_value=0,
        label="Approximately how many people?",
        help_text="Optional. Leave blank if not known.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Name cannot be empty.")
        return name


class SharedCoworkingOnboardingForm(_HeadcountMixin):
    """
    Step 2 for the "We use a shared/coworking office" pattern. The single
    onboarding choice covers two distinct `Workplace.TYPE_CHOICES` values
    (shared_office / coworking_space, PID §9's own list) - this step asks
    which one, plus the same name/location/headcount fields as the
    one-office pattern (PID §9.1's own "Woking shared office" example).
    """

    SUBTYPE_CHOICES = [
        (Workplace.TYPE_SHARED_OFFICE, "Shared office"),
        (Workplace.TYPE_COWORKING_SPACE, "Coworking space"),
    ]

    subtype = forms.ChoiceField(
        choices=SUBTYPE_CHOICES,
        label="Which is it?",
        initial=Workplace.TYPE_SHARED_OFFICE,
    )
    name = forms.CharField(
        max_length=255,
        initial="Shared office",
        label="What should we call this workplace?",
    )
    location_label = forms.CharField(
        max_length=255,
        required=False,
        label="Location",
        help_text='Human-level, e.g. "Woking, Surrey" or "London". Optional.',
    )
    approx_people_count = forms.IntegerField(
        required=False,
        min_value=0,
        label="Approximately how many people?",
        help_text="Optional. Leave blank if not known.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Name cannot be empty.")
        return name


class OfficeAndHomeOnboardingForm(forms.Form):
    """
    Step 2 for the "Office + home working" pattern (PID §9.1's twenty-
    person example: "London Head Office / dedicated_office / London /
    approx people: 15" plus "Home / remote working / distributed_home /
    approx people: 5"). Creates two `Workplace` rows from one step.
    """

    office_name = forms.CharField(
        max_length=255,
        initial="Office",
        label="What should we call the office?",
    )
    office_location_label = forms.CharField(
        max_length=255,
        required=False,
        label="Office location",
        help_text='Human-level, e.g. "London". Optional.',
    )
    office_approx_people_count = forms.IntegerField(
        required=False,
        min_value=0,
        label="Approximately how many people work at the office?",
    )
    home_approx_people_count = forms.IntegerField(
        required=False,
        min_value=0,
        label="Approximately how many people work from home?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_office_name(self):
        name = self.cleaned_data["office_name"].strip()
        if not name:
            raise forms.ValidationError("Office name cannot be empty.")
        return name


# ---------------------------------------------------------------------------
# General create/edit form - the "several locations" add-another-workplace
# flow, and ordinary editing of any existing Workplace row.
# ---------------------------------------------------------------------------
class WorkplaceForm(forms.ModelForm):
    class Meta:
        model = Workplace
        fields = ["name", "type", "location_label", "approx_people_count", "is_primary"]
        labels = {
            "name": "Name",
            "type": "Type",
            "location_label": "Location",
            "approx_people_count": "Approximate headcount",
            "is_primary": "This is our main workplace",
        }
        help_texts = {
            "location_label": 'Human-level, e.g. "Woking, Surrey" or "London". Optional.',
            "approx_people_count": "Optional. Leave blank if not known.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Name cannot be empty.")
        return name
