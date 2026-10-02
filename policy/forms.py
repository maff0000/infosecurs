"""
Forms for the approval-confirmation step (M004 PID §16-18 -
m004-2b-policy-lifecycle dispatch).

`PolicyVersionEditForm`/`section_field_name`/`SECTION_FIELD_PREFIX` (the
one-textarea-per-section free-text draft editor) were REMOVED here
(M008-WI6 Finding A, dell-debian Auditor, 2026-10-02) - a fresh,
independent Auditor proved live that this Foundation-tier-reachable form
let arbitrary unverified prose (a false ISO 27001 certification claim, in
their reproduction) into the distributed, approved policy PDF, exactly the
gap `docs/design/M008-FREE-TEXT-REPLACEMENT-REGISTER.md` item 12 already
named: "Foundation-tier customers never see a section editor at all...
this form is retired for Foundation tier entirely, not repurposed." The
corresponding view (`policy.views.policy_edit`) and URL
(`policy:version_edit`) are removed too (see `policy/urls.py`/
`policy/views.py`) - the free-text path is genuinely unreachable, not
merely unlinked. The underlying `PolicyVersion.sections` JSON field, its
schema, and its immutability guard (`PolicyVersion.save()`) are UNCHANGED;
the only way `sections` content can change now is via
`policy.services.generate_policy_draft_deterministic`/
`generate_policy_draft` regenerating it wholesale, never a partial,
customer-authored edit. See `policy/tests/test_edit.py` for the regression
tests proving this path is closed.
"""
from __future__ import annotations

from django import forms


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
    "PolicyApprovalConfirmForm",
]
