"""
Plain `forms.Form` (not `ModelForm`) for every write path here, on
purpose: `SecurityTask` has several fields (`version`, `source_kind`/
`source_object_id`, `occurrence_key`, `idempotency_key`, event-provenance
fields) that must never be settable from an arbitrary POST body - a
`ModelForm` with an explicit `fields=[...]` allowlist would still be one
accidental refactor away from exposing one of them. Every field actually
offered to a customer is deliberately enumerated below, and every write
still goes through `security_tasks.services` (never `form.save()`), which
re-validates assignee membership and source-locator ownership itself
regardless of what this form already restricted - defence in depth, same
discipline this codebase's other forms/services pairs already use
(`risk_register.forms.RiskEditForm` + `risk_register.views`).
"""
from __future__ import annotations

from django import forms

from organisations.models import OrganisationMembership
from security_tasks.models import TaskPriority, TaskStatus
from security_tasks.source_registry import source_kind_choices


def _apply_field_css_classes(form):
    """Same CSS-hook convention as organisations.forms/risk_register.forms."""
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


class TaskFilterForm(forms.Form):
    """GET-only filter form for the Tasks list page. Every field is
    optional; an invalid/forged value is simply dropped by `is_valid()`'s
    own validation rather than ever reaching
    `security_tasks.services.get_task_list` unvalidated."""

    GROUP_CHOICES = [
        ("", "All groups"),
        ("foundations", "Foundations"),
        ("risks_actions", "Risks & Actions"),
        ("policies", "Policies"),
        ("evidence_assurance", "Evidence & Assurance"),
        ("other", "Other"),
    ]
    DUE_CHOICES = [
        ("", "Any due date"),
        ("overdue", "Overdue"),
        ("due_soon", "Due soon"),
    ]

    group = forms.ChoiceField(choices=GROUP_CHOICES, required=False)
    status = forms.ChoiceField(choices=[("", "Any status")] + list(TaskStatus.choices), required=False)
    assignee = forms.ChoiceField(choices=[], required=False, label="Assignee")
    due = forms.ChoiceField(choices=DUE_CHOICES, required=False)
    q = forms.CharField(required=False, max_length=200, label="Search")

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        member_choices = [("", "Anyone")]
        if organisation is not None:
            member_choices += [
                (str(m.user_id), str(m.user))
                for m in OrganisationMembership.objects.filter(organisation=organisation).select_related("user")
            ]
        self.fields["assignee"].choices = member_choices
        _apply_field_css_classes(self)


class TaskCreateForm(forms.Form):
    """A deliberately small subset of `SecurityTask`'s fields - the ones a
    customer may set directly when raising a manual follow-up (M010A PID
    §1 "Customer may create a simple follow-up"). `task_kind` is
    restricted to `manual_other` for this form specifically - a customer-
    raised follow-up is always `manual_other`/`human`-origin; the other
    eight kinds are reserved for deterministic/IRENE-origin creation
    (M010A PID §2's own "do not create tasks just by visiting page" and
    M010-MASTER-ARCHITECTURE.md §6's "no automatic task generation until
    M010D" - a documented scope boundary, not an oversight)."""

    title = forms.CharField(max_length=255)
    summary = forms.CharField(required=False, widget=forms.Textarea, max_length=4000)
    priority = forms.ChoiceField(choices=TaskPriority.choices, required=False, initial=TaskPriority.NORMAL)
    assignee = forms.ChoiceField(choices=[], required=False, label="Assign to")
    due_at = forms.DateTimeField(required=False, label="Due date")
    idempotency_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        member_choices = [("", "Unassigned")]
        if organisation is not None:
            member_choices += [
                (str(m.user_id), str(m.user))
                for m in OrganisationMembership.objects.filter(organisation=organisation).select_related("user")
            ]
        self.fields["assignee"].choices = member_choices
        _apply_field_css_classes(self)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        return title


class TaskTransitionForm(forms.Form):
    next_status = forms.ChoiceField(choices=TaskStatus.choices)
    reason = forms.CharField(widget=forms.Textarea, max_length=1000)
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    override_blocked = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_field_css_classes(self)


class TaskAssignForm(forms.Form):
    assignee = forms.ChoiceField(choices=[], required=False, label="Assign to")
    expected_version = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        member_choices = [("", "Unassigned")]
        if organisation is not None:
            member_choices += [
                (str(m.user_id), str(m.user))
                for m in OrganisationMembership.objects.filter(organisation=organisation).select_related("user")
            ]
        self.fields["assignee"].choices = member_choices
        _apply_field_css_classes(self)


class TaskDependencyForm(forms.Form):
    """Links another task in the SAME organisation as a predecessor
    ("blocks") of the task this form is rendered on. The queryset is
    scoped to `organisation` and excludes the current task itself - a
    genuine defence-in-depth narrowing of the dropdown, not the actual
    self-reference/cross-org/cycle enforcement, which lives entirely in
    `security_tasks.services.link_task_dependency` (this form's own
    choice-restriction can always be bypassed by a raw POST; the tests in
    `test_dependencies.py` POST directly, bypassing this form, to prove
    the service layer - not this form - is what actually rejects a bad
    edge)."""

    predecessor = forms.ChoiceField(choices=[], label="Blocked by")

    def __init__(self, *args, organisation=None, current_task=None, **kwargs):
        super().__init__(*args, **kwargs)
        from security_tasks.models import SecurityTask

        queryset = SecurityTask.objects.for_organisation(organisation) if organisation else SecurityTask.objects.none()
        if current_task is not None:
            queryset = queryset.exclude(pk=current_task.pk)
        self.fields["predecessor"].choices = [(str(t.pk), t.title) for t in queryset]
        _apply_field_css_classes(self)
