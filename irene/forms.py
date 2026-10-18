"""Plain Django forms for IRENE's Ask tab (M010C PID §5). Same discipline
as `security_tasks.forms`: ordinary `ChoiceField`/`CharField` validation,
no free-text alternative to a canonical field."""
from __future__ import annotations

from django import forms

from ai_platform.adviser_contracts import MAX_USER_MESSAGE_LENGTH
from irene.models import IntentCode


class AskForm(forms.Form):
    message = forms.CharField(
        max_length=MAX_USER_MESSAGE_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Ask IRENE",
    )
    intent_code = forms.ChoiceField(choices=IntentCode.choices, initial=IntentCode.UNCLEAR)


class ConfirmTaskForm(forms.Form):
    action_id = forms.UUIDField()
