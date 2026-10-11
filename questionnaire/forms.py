"""
The questionnaire-response wording-edit form (PID §17 - m005-2-review-history
dispatch).

Deliberately a plain `forms.Form`, NOT a `forms.ModelForm` bound to the
`QuestionnaireResponse` instance - mirroring `policy.forms.
PolicyVersionEditForm`'s own reasoning exactly (see that form's docstring):
a ModelForm bound with `instance=response` would give `is_valid()` ->
`full_clean()` -> `_post_clean()` -> `construct_instance()` the ability to
mutate `response` in place, field-by-field, from whatever the form declares
- even fields never rendered in this form's HTML, if the ModelForm's own
`Meta.fields`/`exclude` were ever misconfigured. That risk is structurally
unacceptable here: `outcome`/`selected_keys`/`grounding_snapshot` are
exactly the fields PID §17 says the Account Holder "must not be able to...
bypass canonical truth by upgrading" - GAP/CONFIRM -> SUPPORTED - by editing
wording. A plain `forms.Form` with exactly one field has no model instance
to mutate as a side effect of validation at all; there is no field on this
form a caller could accidentally read `outcome`/`selected_keys`/
`grounding_snapshot` from, because this form never binds to the model and
never declares those fields.

`questionnaire.views.questionnaire_response_edit` reads ONLY
`form.cleaned_data["current_answer_text"]` and passes it to
`questionnaire.services.edit_questionnaire_response_text` - it never reads
`outcome`/`selected_keys`/`grounding_snapshot`/anything else from
`request.POST` directly, so even a hostile POST body that includes an
`outcome` field alongside a legitimate `current_answer_text` change has
zero effect (see `questionnaire/tests/test_review_workflow.py`'s hostile
test for an HTTP-level proof, not just a reading of this form's field
list).
"""
from __future__ import annotations

from django import forms


class QuestionnaireResponseEditForm(forms.Form):
    """Exactly one field - the editable answer wording (PID §17: "The
    Account Holder may edit wording... They may: improve wording; add
    context; make the response more conservative; decline the draft.").
    No other field exists on this form, by design - see module docstring.
    """

    current_answer_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8, "class": "textarea"}), required=True
    )


class QuestionnaireImportUploadForm(forms.Form):
    """
    M009A (WO-M009A-SECURE-INGESTION-XLSX.md "Minimal real customer entry
    surface", Correction 15) - deliberately a plain `forms.Form` with
    exactly one field. `questionnaire.views.questionnaire_import_upload`
    reads ONLY `form.cleaned_data["file"]` and passes it straight to
    `questionnaire.import_services.ingest_questionnaire_import`, which
    performs its OWN content-sniffing/size-streaming/security-gate
    validation (this form never pre-judges file type by extension or
    client-supplied Content-Type - WO-M009A: "No parser/extractor of any
    kind may run before the pre-parse security gate accepts the file",
    and this form is not a parser, just a required-field presence check).
    """

    file = forms.FileField(
        help_text="XLSX only, up to 10 MiB. The file's actual content is checked by the "
        "security gate - not its filename or browser-reported type.",
    )


__all__ = ["QuestionnaireResponseEditForm", "QuestionnaireImportUploadForm"]
