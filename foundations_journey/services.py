"""
The service layer for the Foundations guided journey (M010B, docs/pids/
M010B-FOUNDATIONS-GUIDED-JOURNEY.md; docs/architecture/
M010-DATA-WORKFLOW-CONTRACTS.md §3).

This module is a THIN, VALIDATED ADAPTER - it never reimplements, never
recomputes a second completion figure, never invents a new option code
or question text. Every function here reuses the real, unmodified
`security_baseline` module it names, by direct import and direct call:

  - `security_baseline.catalogue.CATALOGUE_KEYS`/`CATALOGUE_BY_KEY` - the
    12 real control keys.
  - `security_baseline.stage4.offered_options` - the ONE place that
    decides which option_codes are currently offered for a control/
    organisation (NOT_APPLICABLE re-gating, BYOD conditioning). This
    module never re-derives that gating itself.
  - `security_baseline.stage4.QUESTION_COPY`/`explainer_for`/
    `stage4_progress`/`progress_copy` - the approved customer-facing copy
    and the deterministic post-answer explainer/progress text.
  - `security_baseline.forms.StructuredAnswerForm` - rebuilt FRESH on
    every `submit_foundations_option` call, exactly like
    `security_baseline.views.foundations_question` already does, so a
    forged/unoffered option_code is rejected by ordinary Django
    `ChoiceField` validation before anything is written - never trusted
    from a stale render.
  - `security_baseline.services.record_structured_baseline_answer` - the
    SOLE write path for a structured Stage 4 answer. This module never
    calls `BaselineAnswer.objects.update_or_create`/`AnswerSelectionDetail.
    objects.update_or_create` directly - it calls this exact function,
    the same canonical path `security_baseline.views.foundations_question`
    itself calls.
  - `entitlements.metrics.get_security_foundations_completion` - the
    SOLE source of the 18-item Foundations completion figure. This
    module never computes a second one.

Every function takes an already organisation-scoped, membership-checked
`organisation` as its first argument - the same convention `security_
tasks.services`/`risk_register.services` already use. Capability/tier
checking stays at the view/decorator layer (`@require_capability()`);
this module does not invent a second authorization mechanism.

No AI/model call anywhere in this module, and none of its imports touch
`ai_platform` at all - the entire guided journey is deterministic
(M010B PID §6's required "no model calls for the entire deterministic
flow"). `foundations_journey/tests/test_zero_ai_calls.py` proves this by
patching the one real network boundary in this codebase
(`ai_platform.gateway.LiteLLMGateway._send`) and asserting it is never
invoked across a full 12-control guided run.

Checkpoint reconciliation (M010 data contract §4's "Checkpoint: update
after answer receipt, never before"; "canonical stored answers trump an
old checkpoint" - data contract §1): `_compute_live_position` re-derives
the CURRENT real position (which control is next-unreviewed, and the
derived `CheckpointState`) directly from `AnswerSelectionDetail` rows,
every single call - it is never read off a stored `JourneyCheckpoint`
field. `get_journey_checkpoint` (a read) returns that live-reconciled
value WITHOUT persisting it (so merely viewing/resuming the journey never
writes a checkpoint "before an answer"); `_persist_reconciled_position`
(called only from `submit_foundations_option`, strictly AFTER
`record_structured_baseline_answer` has already committed, and from
`update_checkpoint`'s explicit pause/resume transition) is the only place
that actually calls `.save()` with an advanced position. Because the
position is always freshly recomputed from the real answers rather than
trusted from any client input, there is no client-settable "jump to
question N" write for two browser tabs to race in the first place; the
one genuinely client-triggered transition this module exposes (pause/
resume, via `update_checkpoint`) uses real CAS (`expected_version`) under
`select_for_update()`, exactly like `security_tasks.services.
transition_task`.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from entitlements.metrics import get_security_foundations_completion
from foundations_journey.exceptions import (
    ConcurrentCheckpointModificationError,
    InvalidFoundationsOptionError,
    NoFollowUpTaskAvailableError,
)
from foundations_journey.models import JOURNEY_CODE_FOUNDATIONS, CheckpointState, JourneyCheckpoint
from security_baseline.catalogue import CATALOGUE_BY_KEY, CATALOGUE_KEYS
from security_baseline.forms import (
    StructuredAnswerForm,
    confirm_field_name,
    option_field_name,
)
from security_baseline.models import (
    ANSWER_NO,
    ANSWER_PARTIAL,
    ANSWER_UNKNOWN,
    BaselineAssessment,
)
from security_baseline.services import record_structured_baseline_answer
from security_baseline.stage4 import (
    QUESTION_COPY,
    explainer_for,
    offered_options,
    progress_copy,
    stage4_progress,
)
from security_baseline.structured_catalogue import FOUNDATIONS_QUESTION_METHODOLOGY_VERSION
from security_tasks import services as task_services
from security_tasks.models import SecurityTask, SourceOrigin, TaskKind
from security_tasks.source_registry import SOURCE_KIND_BASELINE_ANSWER

_JML_CONTROL_KEY = "joiner_mover_leaver"

_FOLLOWUP_TASK_KIND_BY_ANSWER = {
    ANSWER_UNKNOWN: TaskKind.FOUNDATION_CONFIRM,
    ANSWER_PARTIAL: TaskKind.FOUNDATION_REMEDIATE,
    ANSWER_NO: TaskKind.FOUNDATION_REMEDIATE,
}


def _validate_question_key(question_key: str) -> None:
    if question_key not in CATALOGUE_BY_KEY:
        raise ValueError(f"{question_key!r} is not a real security_baseline control key.")


# ---------------------------------------------------------------------------
# Registered route helper (PID §2: "a registered link back to the
# existing full-page ... route — never a URL you construct by hand — use
# Django's reverse()").
# ---------------------------------------------------------------------------
def get_registered_route(route_name: str, *, organisation, question_key: Optional[str] = None) -> str:
    if question_key is not None:
        return reverse(route_name, args=[organisation.id, question_key])
    return reverse(route_name, args=[organisation.id])


# ---------------------------------------------------------------------------
# StructuredQuestionViewModel (PID §2 / data contract §3
# `get_foundations_question`).
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class StructuredQuestionViewModel:
    question_key: str
    title: str
    question_text: str
    why_it_matters: str
    options: tuple
    saved_option_code: Optional[str]
    requires_confirmation: bool
    confirmation_label: Optional[str]
    stage_index: int
    stage_total: int
    question_index: int
    question_total: int
    reviewed_count: int
    still_need_confirmation_count: int
    stage_progress_copy: str
    stage_complete: bool
    completion_percentage: int
    completion_completed_count: int
    completion_total_count: int
    explainer: Optional[str]
    manual_page_url: str
    previous_question_key: Optional[str]
    next_question_key: Optional[str]
    methodology_version: str


def get_foundations_question(organisation, user, question_key: str) -> StructuredQuestionViewModel:
    """Assembles everything one guided question card needs, entirely from
    existing, unmodified `security_baseline`/`entitlements` reads - never
    writes anything. `user` is accepted (and will be used by a future
    per-user personalisation, if any is ever added) but not currently
    needed to assemble this read-only view - every fact here is
    organisation-scoped, not user-scoped."""
    _validate_question_key(question_key)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    existing_selection = None
    if assessment is not None:
        existing_selection = assessment.selection_details.filter(question_key=question_key).first()

    allowed = offered_options(question_key, organisation)
    options = tuple((code, option.label) for code, option in allowed.items())

    saved_option_code = existing_selection.option_code if existing_selection is not None else None
    explainer = None
    if saved_option_code is not None and assessment is not None:
        answer = assessment.answers.filter(question_key=question_key).first()
        if answer is not None:
            explainer = explainer_for(question_key, saved_option_code, answer.answer)

    confirmation_label = None
    if question_key == _JML_CONTROL_KEY:
        # Read the real confirmation label off the real form rather than
        # hand-duplicating its exact wording a second time here.
        probe_form = StructuredAnswerForm(organisation=organisation, question_keys=[question_key])
        confirmation_label = probe_form.fields[confirm_field_name(question_key)].label

    progress = stage4_progress(assessment)
    completion = get_security_foundations_completion(organisation)

    index = CATALOGUE_KEYS.index(question_key)
    previous_key = CATALOGUE_KEYS[index - 1] if index > 0 else None
    next_key = CATALOGUE_KEYS[index + 1] if index + 1 < len(CATALOGUE_KEYS) else None

    copy = QUESTION_COPY[question_key]

    return StructuredQuestionViewModel(
        question_key=question_key,
        title=copy["title"],
        question_text=copy["question"],
        why_it_matters=copy["why_it_matters"],
        options=options,
        saved_option_code=saved_option_code,
        requires_confirmation=(question_key == _JML_CONTROL_KEY),
        confirmation_label=confirmation_label,
        stage_index=4,
        stage_total=6,
        question_index=index + 1,
        question_total=len(CATALOGUE_KEYS),
        reviewed_count=progress["reviewed"],
        still_need_confirmation_count=progress["still_need_confirmation"],
        stage_progress_copy=progress_copy(progress),
        stage_complete=progress["complete"],
        completion_percentage=completion.percentage,
        completion_completed_count=completion.completed_count,
        completion_total_count=completion.total_count,
        explainer=explainer,
        manual_page_url=get_registered_route(
            "security_baseline:foundations_question", organisation=organisation, question_key=question_key
        ),
        previous_question_key=previous_key,
        next_question_key=next_key,
        methodology_version=FOUNDATIONS_QUESTION_METHODOLOGY_VERSION,
    )


# ---------------------------------------------------------------------------
# submit_foundations_option (PID §2 / data contract §3).
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class AnswerReceipt:
    question_key: str
    option_code: str
    derived_answer: str
    methodology_version: str
    explainer: str
    saved_at: object
    next_question_key: Optional[str]
    stage_progress_copy: str
    stage_complete: bool
    completion_percentage: int
    completion_completed_count: int
    completion_total_count: int


def submit_foundations_option(
    organisation,
    user,
    *,
    question_key: str,
    option_code: str,
    confirmation: bool = False,
) -> AnswerReceipt:
    """Validates against a FRESH `offered_options()` call (via a newly
    constructed `StructuredAnswerForm` - never a stale option list from
    an earlier render) and, only if valid, writes through the exact same
    canonical path `security_baseline.views.foundations_question` already
    uses: `security_baseline.services.record_structured_baseline_answer`.

    Raises `InvalidFoundationsOptionError` (carrying the real form
    errors) for a forged/unoffered option_code, a missing JML
    confirmation, or any other validation failure - nothing is written,
    exactly like the existing manual view's own invalid-POST behaviour.

    The returned `next_question_key` is the ACTUAL next-unreviewed
    control derived from the real, just-committed saved state (mirroring
    `security_baseline.views.foundations_start`'s own "first unreviewed
    control, else the first control again" logic) - never a hardcoded
    "next in catalogue order".
    """
    _validate_question_key(question_key)

    data = {option_field_name(question_key): option_code}
    if question_key == _JML_CONTROL_KEY and confirmation:
        data[confirm_field_name(question_key)] = "on"

    form = StructuredAnswerForm(data, organisation=organisation, question_keys=[question_key])
    if not form.is_valid():
        raise InvalidFoundationsOptionError(form.errors)

    cleaned_option_code = form.cleaned_data[option_field_name(question_key)]

    recorded = record_structured_baseline_answer(
        organisation, question_key, cleaned_option_code, actor=user
    )

    explainer = explainer_for(question_key, cleaned_option_code, recorded.answer.answer)

    checkpoint, _created = JourneyCheckpoint.objects.get_or_create(
        organisation=organisation, user=user, journey_code=JOURNEY_CODE_FOUNDATIONS
    )
    checkpoint = _persist_reconciled_position(checkpoint, organisation)

    progress = stage4_progress(recorded.assessment)
    completion = get_security_foundations_completion(organisation)

    next_question_key = (
        None if checkpoint.checkpoint_state == CheckpointState.JOURNEY_COMPLETE
        else checkpoint.current_question_key
    )

    return AnswerReceipt(
        question_key=question_key,
        option_code=cleaned_option_code,
        derived_answer=recorded.answer.answer,
        methodology_version=recorded.selection_detail.methodology_version,
        explainer=explainer,
        saved_at=recorded.selection_detail.recorded_at,
        next_question_key=next_question_key,
        stage_progress_copy=progress_copy(progress),
        stage_complete=progress["complete"],
        completion_percentage=completion.percentage,
        completion_completed_count=completion.completed_count,
        completion_total_count=completion.total_count,
    )


# ---------------------------------------------------------------------------
# Task handoff (PID §5). Deliberately NEVER called automatically from
# `get_foundations_question`/`submit_foundations_option` above - this is
# always a SEPARATE, explicit user action (its own POST endpoint; see
# `foundations_journey/views.py`).
# ---------------------------------------------------------------------------
def offer_foundations_followup_task(
    organisation, user, *, question_key: str, idempotency_key: str
) -> SecurityTask:
    """Explicit, user-triggered task handoff. Re-reads the CURRENT
    canonical `BaselineAnswer`/`AnswerSelectionDetail` fresh (never trusts
    a value the caller claims) and raises `NoFollowUpTaskAvailableError`
    for an unanswered control or a YES/NOT_APPLICABLE answer - there is
    nothing to confirm or remediate for those.

    Deduplicated via `occurrence_key` (`security_tasks.services.
    create_task`'s own partial-unique-constraint-backed dedupe, scoped to
    (organisation, source_origin, task_kind, occurrence_key)) - calling
    this twice for the same control/answer/option returns the SAME task,
    never a duplicate. `source_origin=SourceOrigin.HUMAN`: this is always
    a person clicking an explicit "add a follow-up task" control IRENE's
    guided card renders, not an autonomous model decision - no AI call is
    made anywhere in this function."""
    _validate_question_key(question_key)

    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    answer = assessment.answers.filter(question_key=question_key).first() if assessment is not None else None
    selection = (
        assessment.selection_details.filter(question_key=question_key).first()
        if assessment is not None
        else None
    )

    if answer is None or selection is None:
        raise NoFollowUpTaskAvailableError(
            f"{question_key!r} has not been answered yet - nothing to offer a follow-up task for."
        )

    kind = _FOLLOWUP_TASK_KIND_BY_ANSWER.get(answer.answer)
    if kind is None:
        raise NoFollowUpTaskAvailableError(
            f"{question_key!r}'s current answer ({answer.answer!r}) needs no follow-up task."
        )

    title_prefix = "Confirm" if kind == TaskKind.FOUNDATION_CONFIRM else "Remediate"
    title = f"{title_prefix}: {QUESTION_COPY[question_key]['title']}"
    summary = (
        f"Foundations control '{question_key}' is currently recorded as "
        f"'{answer.answer}' (selected option {selection.option_code!r})."
    )
    occurrence_key = f"foundations:{question_key}:{answer.answer}:{selection.option_code}"

    task = task_services.create_task(
        organisation,
        actor=user,
        kind=kind,
        title=title,
        summary=summary,
        idempotency_key=idempotency_key,
        source_origin=SourceOrigin.HUMAN,
        source_kind=SOURCE_KIND_BASELINE_ANSWER,
        source_object_id=str(answer.pk),
        occurrence_key=occurrence_key,
    )

    checkpoint, _created = JourneyCheckpoint.objects.get_or_create(
        organisation=organisation, user=user, journey_code=JOURNEY_CODE_FOUNDATIONS
    )
    checkpoint.pending_task = task
    checkpoint.last_interaction_at = timezone.now()
    checkpoint.version += 1
    checkpoint.save(update_fields=["pending_task", "last_interaction_at", "version", "updated_at"])

    return task


# ---------------------------------------------------------------------------
# Checkpoint (PID §4 / data contract §1/§3/§4).
# ---------------------------------------------------------------------------
def _compute_live_position(organisation):
    """Returns `(next_key, state, progress)`, re-derived from the REAL
    `AnswerSelectionDetail` rows, every call. Never reads or writes a
    `JourneyCheckpoint` row itself - callers decide whether/when to
    persist what this returns. `next_key` mirrors `security_baseline.
    views.foundations_start`'s own "first unreviewed control, else the
    first control again" exactly."""
    assessment = BaselineAssessment.objects.filter(organisation=organisation).first()
    reviewed_keys = set()
    if assessment is not None:
        reviewed_keys = set(
            assessment.selection_details.filter(question_key__in=CATALOGUE_KEYS).values_list(
                "question_key", flat=True
            )
        )
    next_key = next((key for key in CATALOGUE_KEYS if key not in reviewed_keys), CATALOGUE_KEYS[0])
    progress = stage4_progress(assessment)
    if progress["complete"]:
        state = CheckpointState.JOURNEY_COMPLETE
    elif reviewed_keys:
        state = CheckpointState.ACTIVE
    else:
        state = CheckpointState.NEW
    return next_key, state, progress


def _persist_reconciled_position(checkpoint: JourneyCheckpoint, organisation) -> JourneyCheckpoint:
    """The ONLY place this module advances a checkpoint's stored
    position/state - called strictly AFTER a successful `record_
    structured_baseline_answer` commit (from `submit_foundations_option`)
    or an explicit `update_checkpoint` "resume" transition. Never called
    from a plain read (`get_journey_checkpoint`) - see that function's
    own docstring."""
    next_key, state, progress = _compute_live_position(organisation)
    checkpoint.current_question_key = next_key
    checkpoint.checkpoint_state = state
    checkpoint.stage_code = "stage_4"
    checkpoint.methodology_version = FOUNDATIONS_QUESTION_METHODOLOGY_VERSION
    checkpoint.last_domain_revision = f"{progress['reviewed']}:{progress['still_need_confirmation']}"
    checkpoint.last_interaction_at = timezone.now()
    checkpoint.version += 1
    checkpoint.save()
    return checkpoint


def get_journey_checkpoint(
    organisation, user, *, journey_code: str = JOURNEY_CODE_FOUNDATIONS
) -> JourneyCheckpoint:
    """READ-ONLY (M010 data contract §4: "Checkpoint: update after answer
    receipt, never before"). Creates the row on first visit if it does
    not exist yet - an empty `JourneyCheckpoint` IS the "new" state, not
    a write that needs an answer first - but never advances an EXISTING
    row's stored position here.

    The returned object's `current_question_key`/`checkpoint_state`
    reflect the LIVE, just-recomputed truth (canonical stored answers
    always trump a stale checkpoint - M010 data contract §1) even when
    that differs from what is currently persisted - this is what
    "reconcile with the real domain answer on resume" means in practice;
    it does not require writing anything merely because the journey was
    looked at again. The in-memory object is NOT saved by this function.

    An explicit `paused`/`waiting` state is a user decision that must
    survive a mere reconciling read - it is returned as-is, never
    silently resumed just because the journey was viewed again
    (M010-UX-CUSTOMER-JOURNEYS.md §4: "Skip for now: checkpoint waiting
    or paused ... do not create a false... [state]").
    """
    checkpoint, _created = JourneyCheckpoint.objects.get_or_create(
        organisation=organisation, user=user, journey_code=journey_code
    )
    if checkpoint.checkpoint_state in (CheckpointState.PAUSED, CheckpointState.WAITING):
        return checkpoint

    next_key, state, _progress = _compute_live_position(organisation)
    checkpoint.current_question_key = next_key
    checkpoint.checkpoint_state = state
    return checkpoint


def update_checkpoint(
    organisation,
    user,
    *,
    journey_code: str = JOURNEY_CODE_FOUNDATIONS,
    expected_version: int,
    transition: str,
) -> JourneyCheckpoint:
    """The one genuinely client-triggered checkpoint state change
    (`transition` in `{"pause", "resume"}`) - real optimistic-concurrency
    CAS under `select_for_update()`, exactly like `security_tasks.
    services.transition_task`'s own pattern. Raises
    `ConcurrentCheckpointModificationError` on a version mismatch -
    never a silent overwrite."""
    if transition not in ("pause", "resume"):
        raise ValueError(f"Unsupported checkpoint transition {transition!r}.")

    with transaction.atomic():
        checkpoint = (
            JourneyCheckpoint.objects.select_for_update()
            .filter(organisation=organisation, user=user, journey_code=journey_code)
            .first()
        )
        if checkpoint is None:
            checkpoint = JourneyCheckpoint.objects.create(
                organisation=organisation, user=user, journey_code=journey_code
            )

        if checkpoint.version != expected_version:
            raise ConcurrentCheckpointModificationError(
                f"Expected version {expected_version}, checkpoint is at {checkpoint.version}."
            )

        if transition == "pause":
            checkpoint.checkpoint_state = CheckpointState.PAUSED
        else:
            next_key, state, _progress = _compute_live_position(organisation)
            checkpoint.current_question_key = next_key
            checkpoint.checkpoint_state = state

        checkpoint.last_interaction_at = timezone.now()
        checkpoint.version += 1
        checkpoint.save()
        return checkpoint
