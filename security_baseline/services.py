"""
The single code path that writes `BaselineAnswer` rows.

PID.md M002 §0.5's non-negotiable rule: "there must remain exactly one
canonical stored answer per control fact even when it is surfaced from more
than one journey. Editing an answer from an asset-contextual page edits the
same canonical `security_baseline` record the general baseline page
reads/writes - never a second, asset-local, potentially contradictory
copy."

This is a small, mechanical extraction of the `update_or_create` loop that
`security_baseline.views.baseline_view` already used - not a redesign of
this app's behaviour. `baseline_view` now calls this function for the
full-catalogue case; `key_assets.views.key_asset_detail` (PID §0.5's
asset-specific protection-checks page) calls the exact same function for
its filtered subset of questions. There is no other place in the codebase
that constructs or saves a `BaselineAnswer`.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional

from django.db import transaction

from organisations.models import Organisation
from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import BaselineAnswer, BaselineAssessment


def save_baseline_answers(
    organisation: Organisation,
    cleaned_data: Mapping[str, str],
    question_keys: Optional[Iterable[str]] = None,
) -> BaselineAssessment:
    """
    Persist one `BaselineAnswer` row per key in `question_keys` (defaulting
    to every catalogue key), reading each answer/note from `cleaned_data`
    using the same `answer_field_name`/`note_field_name` keys
    `BaselineAssessmentForm` produces.

    Always stamps the assessment with the current `CATALOGUE_VERSION`
    (§6.4) - a save through the filtered asset-detail path still records
    the same version discipline as a full-catalogue save, because it is
    the same assessment row and the same code path.

    Returns the organisation's `BaselineAssessment` (created if it did not
    already exist).
    """
    keys = list(question_keys) if question_keys is not None else [
        item["key"] for item in CATALOGUE
    ]

    with transaction.atomic():
        assessment, created = BaselineAssessment.objects.get_or_create(
            organisation=organisation,
            defaults={"catalogue_version": CATALOGUE_VERSION},
        )
        if not created:
            assessment.catalogue_version = CATALOGUE_VERSION
            assessment.save(update_fields=["catalogue_version", "updated_at"])

        for key in keys:
            BaselineAnswer.objects.update_or_create(
                assessment=assessment,
                question_key=key,
                defaults={
                    "answer": cleaned_data[answer_field_name(key)],
                    "note": cleaned_data[note_field_name(key)],
                },
            )

    return assessment
