"""Two deliberately tiny forms - every real option_code/confirmation
validation for the guided card itself still happens inside
`foundations_journey.services.submit_foundations_option`'s own freshly
constructed `security_baseline.forms.StructuredAnswerForm`, never here.
These two forms exist only for the idempotency-key round-trip (task
handoff) and the optimistic-concurrency round-trip (pause/resume) - the
same "small, explicit, hidden-field" shape `security_tasks.forms.
TaskCreateForm`/`TaskAssignForm` already use for the same purpose."""
from __future__ import annotations

from django import forms


class OfferFollowUpTaskForm(forms.Form):
    idempotency_key = forms.CharField(widget=forms.HiddenInput)


class CheckpointTransitionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
