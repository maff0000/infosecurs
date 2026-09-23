from django import forms

from governance.models import GovernanceRoleAssignment, OrganisationPerson


def _apply_field_css_classes(form):
    """
    Same CSS-hook convention as organisations.forms/evidence.forms/
    key_assets.forms - see evidence/forms.py's identical helper for why
    this is duplicated rather than imported (organisations is read-only to
    this app, and the other apps' helpers are private/underscore-
    prefixed).
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


class RoleAssignmentForm(forms.Form):
    """
    Reassign one governance role (PID §8.1's "Role UX"). Deliberately a
    plain `forms.Form`, not a `ModelForm`: `organisation` is never a
    user-submitted value - it comes from the tenant-scoped view - and the
    real write goes through `governance.services.assign_role`, exactly
    like `evidence.forms.ControlEvidenceLinkForm` defers to
    `evidence.link_services.link_evidence_to_control`.

    `role` is a hidden field (one form per role-row on the page, per PID
    §8.1 "keep this simple... a single page listing the three roles...
    and a way to reassign each") rather than a free `ChoiceField` the user
    picks - which role is being reassigned is determined by which of the
    page's three forms was submitted, not chosen inside the form itself.

    Exactly one of `person` (an existing active OrganisationPerson) or
    `new_person_full_name` (create one inline) must be supplied - see
    `clean()`. This is PID §8.1's "allow the Account Holder to create/
    select another named person" in one control, instead of a separate
    person-management CRUD subsystem the dispatch explicitly said not to
    build.
    """

    role = forms.ChoiceField(choices=GovernanceRoleAssignment.ROLE_CHOICES, widget=forms.HiddenInput)
    person = forms.ModelChoiceField(
        queryset=OrganisationPerson.objects.none(),
        required=False,
        label="Assign to an existing person",
    )
    new_person_full_name = forms.CharField(
        max_length=255,
        required=False,
        label="Or create a new person - full name",
    )
    new_person_job_title = forms.CharField(
        max_length=255,
        required=False,
        label="Job title (optional)",
    )

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation is not None:
            self.fields["person"].queryset = OrganisationPerson.objects.filter(
                organisation=organisation, is_active=True
            )
        _apply_field_css_classes(self)

    def clean(self):
        cleaned_data = super().clean()
        person = cleaned_data.get("person")
        new_full_name = (cleaned_data.get("new_person_full_name") or "").strip()

        if person and new_full_name:
            raise forms.ValidationError(
                "Choose an existing person or create a new one, not both."
            )
        if not person and not new_full_name:
            raise forms.ValidationError(
                "Choose an existing person, or provide a full name to create a new one."
            )

        cleaned_data["new_person_full_name"] = new_full_name
        return cleaned_data
