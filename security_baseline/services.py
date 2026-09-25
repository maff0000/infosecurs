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

M003 PID §12 additionally makes this the shared baseline save path that
must emit a `control_answer_changed` activity event on a genuine canonical
answer change - see the before/after comparison in the loop below and
`activity.services.record_event`.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from organisations.models import Organisation
from security_baseline.catalogue import CATALOGUE, CATALOGUE_VERSION
from security_baseline.forms import answer_field_name, note_field_name
from security_baseline.models import ANSWER_UNKNOWN, BaselineAnswer, BaselineAssessment


def save_baseline_answers(
    organisation: Organisation,
    cleaned_data: Mapping[str, str],
    question_keys: Optional[Iterable[str]] = None,
    actor=None,
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

    `actor` is the user making this change (both current call sites pass
    `request.user`) - recorded on any `control_answer_changed` activity
    event this save emits (M003 PID §12). `None` is accepted for a
    save with no identifiable actor (not expected on either current call
    site, but a management command or future system-initiated save is
    free to omit it).

    For each key, a `control_answer_changed` event (M003 PID §12) is
    recorded if - and only if - the *answer* actually changes:
    - the previous stored `BaselineAnswer.answer` for this
      (organisation, key) is read before the `update_or_create` call
      below, so there is a real "before" value to compare against;
    - when no `BaselineAnswer` row exists yet for this key, the implicit
      "before" value is treated as `ANSWER_UNKNOWN` - the model's own
      default (`security_baseline.models.BaselineAnswer.answer`) and
      exactly what the baseline/asset-detail forms already pre-fill an
      unanswered question with (see `baseline_view`/`key_asset_detail`'s
      `initial[...] = existing.answer if existing else ANSWER_UNKNOWN`).
      This matters in practice: without it, the *first* full-catalogue
      save of a brand-new assessment - where most questions are simply
      being submitted at their pre-filled "Not sure" default -
      would otherwise emit a spurious `control_answer_changed` event for
      every single catalogue question, not just the ones the customer
      actually set. Treating "no row yet" as the same UNKNOWN state the
      UI already shows keeps "genuine change" honest in both directions:
      submitting the default again is not a change, but a real first-time
      answer (e.g. UNKNOWN -> "yes") still is, and is still recorded.
    - a note-only edit (same answer, different note) does not, by itself,
      emit an event - only whether the note *changed* is recorded, as a
      boolean, on an answer-change event; the note's content is never
      duplicated into the event log (PID §12, explicit).

    The event write happens inside this function's existing
    `transaction.atomic()` block, alongside the `BaselineAnswer` write it
    documents, so a rolled-back save can never leave an orphaned event
    behind (PID §17).

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
            previous = BaselineAnswer.objects.filter(
                assessment=assessment, question_key=key
            ).first()
            previous_answer = previous.answer if previous is not None else ANSWER_UNKNOWN
            previous_note = previous.note if previous is not None else ""

            new_answer = cleaned_data[answer_field_name(key)]
            new_note = cleaned_data[note_field_name(key)]

            BaselineAnswer.objects.update_or_create(
                assessment=assessment,
                question_key=key,
                defaults={
                    "answer": new_answer,
                    "note": new_note,
                },
            )

            if new_answer != previous_answer:
                record_event(
                    organisation,
                    ActivityEvent.EVENT_CONTROL_ANSWER_CHANGED,
                    actor=actor,
                    control_key=key,
                    metadata={
                        "previous_answer": previous_answer,
                        "new_answer": new_answer,
                        "note_changed": new_note != previous_note,
                    },
                )

    return assessment
