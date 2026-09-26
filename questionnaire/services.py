"""
Minimal end-to-end questionnaire-assurance generation pipeline (M005 PID §4,
§22 - m005-1-foundation dispatch), plus the review/accept/regenerate
lifecycle functions the m005-2-review-history dispatch adds below
(`accept_questionnaire_response`, `edit_questionnaire_response_text` - see
their own docstrings; `questionnaire.views.questionnaire_response_regenerate`
reuses `generate_questionnaire_response` itself for regeneration, no
separate service function needed for that path).

`generate_questionnaire_response` is the single entrypoint the view layer
calls, wiring together every piece this dispatch built:

1. interpret the raw question against the full `questionnaire.catalogue`
   (bounded retry, `AIInvocationRecord` - `ai_platform.
   questionnaire_interpretation_orchestration.
   interpret_questionnaire_question`);
2. assemble the bounded grounding snapshot for the validated
   `selected_keys` (`questionnaire.grounding.
   build_questionnaire_grounding_snapshot`);
3. derive the application-owned outcome (`questionnaire.outcome.
   derive_outcome`) - deterministic, no AI call;
4. draft a concise answer constrained by that FIXED outcome (bounded
   retry, `AIInvocationRecord` - `ai_platform.
   questionnaire_drafting_orchestration.draft_questionnaire_answer`);
5. persist exactly one new `QuestionnaireResponse(status=draft, ...)` in a
   single atomic block.

Both AI calls happen OUTSIDE `transaction.atomic()` (they are external HTTP
calls, and each already owns its own `AIInvocationRecord` lifecycle/commit
independently of this function - identical discipline to
`policy.services.generate_policy_draft`/`risk_register.
interpretation_service.interpret_draft_risks`). Only the final persistence
step is wrapped, so a `QuestionnaireResponse` write can never partially
apply.

== Failure-mode scope (PID §22) - two deliberate simplifications, recorded
here explicitly rather than silently implemented ==

**Interpretation unavailable/invalid** (PID §22 "Save raw question; show
recoverable failure; do not fabricate mapping/outcome"): this function
never creates the `QuestionnaireQuestion` itself - the caller
(`questionnaire.views.questionnaire_analyse`) creates and persists that row
FIRST, independently of whether generation subsequently succeeds, so a
failed interpretation still leaves the raw question saved. On
`QuestionnaireInterpretationFailed`, this function creates no
`QuestionnaireResponse` at all and lets the exception propagate - the view
is responsible for showing a recoverable-failure message.

**Drafting unavailable** (PID §22 "Preserve interpretation/outcome/
grounding and allow retry"): PID's ideal behaviour is a genuine two-phase
resume that persists the interpretation/outcome/grounding even if drafting
subsequently fails, so a retry does not have to re-run interpretation. For
this dispatch's minimal scope, `generate_questionnaire_response` does NOT
do this - on `QuestionnaireDraftingFailed`, it persists nothing at all (no
`QuestionnaireResponse` row, interpretation/outcome/grounding included) and
lets the exception propagate; a caller must retry the WHOLE
`generate_questionnaire_response` call, which re-runs interpretation too.
This is a deliberate, documented scope simplification (per the dispatch's
own explicit instruction) - not an accidental gap. A later dispatch may
optimise this into a genuine two-phase resume if real product usage shows
the extra interpretation re-run cost matters.
"""
from __future__ import annotations

import hashlib
import json

from django.db import transaction
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_event

from ai_platform.gateway import LiteLLMGateway, QuestionnaireDraftingGateway, QuestionnaireInterpretationGateway
from ai_platform.prompts.questionnaire_drafting_v1 import PROMPT_VERSION as DRAFTING_PROMPT_VERSION
from ai_platform.prompts.questionnaire_interpretation_v1 import (
    PROMPT_VERSION as INTERPRETATION_PROMPT_VERSION,
)
from ai_platform.questionnaire_drafting_contracts import OUTCOME_CONFIRM, QuestionnaireDraftingRequest
from ai_platform.questionnaire_drafting_orchestration import draft_questionnaire_answer
from ai_platform.questionnaire_interpretation_contracts import QuestionnaireInterpretationRequest
from ai_platform.questionnaire_interpretation_orchestration import (
    interpret_questionnaire_question,
)

from questionnaire.catalogue import CATALOGUE
from questionnaire.grounding import build_questionnaire_grounding_snapshot
from questionnaire.models import QuestionnaireQuestion, QuestionnaireResponse
from questionnaire.outcome import derive_outcome


# M006 audit finding I2 (originally LOW, reclassified MEDIUM by Central
# Architecture, `docs/evidence/M006-AUDIT-0004.md`): for outcome ==
# OUTCOME_CONFIRM, the deterministic outcome badge is correct (the
# underlying canonical security state is genuinely unconfirmed/unknown),
# but the AI-drafted prose can still read as an unqualified implementation
# claim (e.g. "Staff receive regular security awareness training.") that a
# customer could copy verbatim into a real vendor questionnaire and
# unintentionally misrepresent an unconfirmed control as implemented. The
# deterministic badge does not make that wording acceptable, so the
# application - not the drafting model - owns the customer-facing initial
# wording for this one outcome.
#
# This is a FIXED, deterministic sentence, never string-formatted with any
# raw question text, interpretation summary or AI output (Central
# Architecture's explicit instruction: "Do not insert untrusted raw
# question prose into this deterministic status sentence" - the existing
# separate "Why this answer?" panel already supplies question-specific
# context). Its semantics are binding, independent of the exact wording:
# no yes; no no; no implemented-state assertion; no certification/
# compliance assertion; makes uncertainty explicit; tells the customer
# confirmation is still required.
CONFIRM_APPLICATION_SAFE_ANSWER_TEXT = (
    "Not yet confirmed. The current security record does not contain enough "
    "confirmed information to answer this requirement definitively. Please "
    "review the underlying security state before sending a final response."
)


def _initial_current_answer_text(outcome: str, draft) -> str:
    """The APPLICATION-owned initial value for
    `QuestionnaireResponse.current_answer_text` (M006 I2 fix).

    For every outcome other than `OUTCOME_CONFIRM` (SUPPORTED, GAP,
    NOT_APPLICABLE), this is unchanged from the original behaviour: the raw
    AI-drafted text, exactly as before this fix - PID §12.5's outcome
    aggregation already keeps those three paths' meaning safe, and Central
    Architecture's own finding is scoped to CONFIRM only (do not
    over-generalise - section F).

    For `OUTCOME_CONFIRM`, the raw AI draft is NEVER used as the initial
    customer-facing text, regardless of what the drafting model returned -
    `draft.answer_text` is intentionally not read here at all. The raw
    model output remains fully preserved, unmodified, in
    `ai_draft_text` (see `_persist_response` below) for provenance/
    evaluation; only what initialises the customer-facing
    `current_answer_text` changes. The Account Holder can still freely edit
    this initial value afterwards via `edit_questionnaire_response_text` -
    this function only controls the STARTING value.
    """
    if outcome == OUTCOME_CONFIRM:
        return CONFIRM_APPLICATION_SAFE_ANSWER_TEXT
    return draft.answer_text


def _hash_grounding_snapshot(grounding_snapshot: dict) -> str:
    """SHA-256 hex digest of the grounding snapshot, mirroring
    `AIInvocationRecord.hash_grounding`/`hash_policy_grounding`'s own
    canonical-JSON convention - an immutable fingerprint of exactly what
    this response's answer was grounded in, without needing a second copy
    of the same discipline duplicated as a model method (this hash is
    stored on `QuestionnaireResponse.grounding_snapshot_hash`, not on an
    `AIInvocationRecord`, since the grounding snapshot itself is assembled
    by deterministic application code, not returned by either AI call)."""
    canonical = json.dumps(grounding_snapshot, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def _persist_response(
    organisation,
    question: QuestionnaireQuestion,
    *,
    interpretation,
    interpretation_record,
    outcome: str,
    outcome_warnings: list,
    grounding_snapshot: dict,
    draft,
    drafting_record,
    actor,
) -> QuestionnaireResponse:
    review_warnings = list(outcome_warnings)
    if draft.customer_review_note:
        review_warnings.append(draft.customer_review_note)

    new_response = QuestionnaireResponse.objects.create(
        organisation=organisation,
        question=question,
        status=QuestionnaireResponse.STATUS_DRAFT,
        interpreted_requirement_summary=interpretation.requirement_summary,
        intent_type=interpretation.intent_type,
        requirement_scope=interpretation.requirement_scope,
        selected_keys=list(interpretation.selected_keys),
        evidence_explicitly_requested=interpretation.evidence_explicitly_requested,
        outcome=outcome,
        ai_draft_text=draft.answer_text,
        current_answer_text=_initial_current_answer_text(outcome, draft),
        review_warnings=review_warnings,
        grounding_snapshot=grounding_snapshot,
        grounding_snapshot_hash=_hash_grounding_snapshot(grounding_snapshot),
        interpretation_prompt_version=interpretation.prompt_version,
        drafting_prompt_version=draft.prompt_version,
        interpretation_invocation_record=interpretation_record,
        drafting_invocation_record=drafting_record,
        created_by=actor,
    )
    # Emitted inside this same atomic block as the create (PID §24) - this
    # codebase's established "emit inside the same transaction as the state
    # change" discipline (see e.g. policy.views.policy_edit's
    # EVENT_POLICY_DRAFT_EDITED emission inside its own atomic block).
    record_event(
        organisation,
        ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_GENERATED,
        actor=actor,
        related_object_type="questionnaire_response",
        related_object_id=str(new_response.id),
        metadata={"outcome": outcome, "review_warning_count": len(review_warnings)},
    )
    return new_response


def generate_questionnaire_response(
    organisation,
    question: QuestionnaireQuestion,
    *,
    actor,
    interpretation_gateway: QuestionnaireInterpretationGateway = None,
    drafting_gateway: QuestionnaireDraftingGateway = None,
) -> QuestionnaireResponse:
    """Run one full interpret -> ground -> derive-outcome -> draft ->
    persist pipeline for `question` (which must already exist and belong to
    `organisation` - see module docstring on why this function never
    creates the `QuestionnaireQuestion` itself).

    Raises `ai_platform.questionnaire_interpretation_orchestration.
    QuestionnaireInterpretationFailed` or `ai_platform.
    questionnaire_drafting_orchestration.QuestionnaireDraftingFailed` on
    failure - see module docstring for exactly what is (and is not)
    persisted in each case.

    `interpretation_gateway`/`drafting_gateway` default to a real
    `LiteLLMGateway()` each (constructed lazily inside this call, not at
    import time - PID §14/§21: generation happens only on an explicit user
    action, mirroring every other AI-adapter service's identical default).
    Tests pass `ai_platform.testing.FakeQuestionnaireInterpretationGateway`/
    `FakeQuestionnaireDraftingGateway` explicitly. A single `LiteLLMGateway`
    instance implements both ABCs, so in production the same real gateway
    object may be passed for both, or two independent ones - this function
    does not care which.
    """
    interpretation_gateway = (
        interpretation_gateway if interpretation_gateway is not None else LiteLLMGateway()
    )
    drafting_gateway = drafting_gateway if drafting_gateway is not None else LiteLLMGateway()

    interpretation_request = QuestionnaireInterpretationRequest(
        organisation_id=str(organisation.pk),
        question_text=question.question_text,
        source_label=question.source_label,
        available_keys=CATALOGUE,
    )
    interpretation, interpretation_record = interpret_questionnaire_question(
        interpretation_gateway, interpretation_request, INTERPRETATION_PROMPT_VERSION
    )
    # Plain create, NOT wrapped in `_persist_response`'s atomic block below -
    # interpretation may succeed even if drafting subsequently fails (PID
    # §22's "interpretation succeeded" is independently true regardless of
    # what happens next), so this event must not be rolled back by a later
    # drafting failure.
    record_event(
        organisation,
        ActivityEvent.EVENT_QUESTION_INTERPRETED,
        actor=actor,
        related_object_type="questionnaire_question",
        related_object_id=str(question.id),
        metadata={
            "intent_type": interpretation.intent_type,
            "requirement_scope": interpretation.requirement_scope,
            "selected_keys": list(interpretation.selected_keys),
            "evidence_explicitly_requested": interpretation.evidence_explicitly_requested,
        },
    )

    grounding_snapshot = build_questionnaire_grounding_snapshot(
        organisation, interpretation.selected_keys
    )
    outcome, outcome_warnings = derive_outcome(interpretation, grounding_snapshot)

    drafting_request = QuestionnaireDraftingRequest(
        organisation_id=str(organisation.pk),
        question_text=question.question_text,
        interpretation=interpretation,
        outcome=outcome,
        grounding_snapshot=grounding_snapshot,
    )
    draft, drafting_record = draft_questionnaire_answer(
        drafting_gateway, drafting_request, DRAFTING_PROMPT_VERSION
    )

    return _persist_response(
        organisation,
        question,
        interpretation=interpretation,
        interpretation_record=interpretation_record,
        outcome=outcome,
        outcome_warnings=outcome_warnings,
        grounding_snapshot=grounding_snapshot,
        draft=draft,
        drafting_record=drafting_record,
        actor=actor,
    )


def accept_questionnaire_response(response: QuestionnaireResponse, *, actor) -> QuestionnaireResponse:
    """
    PID §17/§18: accept `response` (must currently be `status=draft` - the
    view is responsible for that check and the friendly redirect; this
    function trusts its caller, matching `policy.services.
    approve_policy_directly`'s own "caller already checked eligibility"
    discipline for a sibling lifecycle transition).

    Supersedes whichever OTHER response for the SAME question currently
    holds `status=accepted`, if any - there should be at most one such
    response given this function is the only path to `accepted`, but the
    lookup below uses `.first()` defensively, not `.get()`.
    """
    with transaction.atomic():
        previous_accepted = (
            QuestionnaireResponse.objects.filter(
                question=response.question, status=QuestionnaireResponse.STATUS_ACCEPTED
            )
            .exclude(pk=response.pk)
            .first()
        )

        response.status = QuestionnaireResponse.STATUS_ACCEPTED
        response.accepted_by = actor
        response.accepted_at = timezone.now()
        # Fine under the model's immutability guard: status/accepted_by/
        # accepted_at are not in PROTECTED_WHILE_DRAFT_FIELDS, and the row
        # being transitioned is still persisted as `draft` at the moment
        # this specific save runs.
        response.save(update_fields=["status", "accepted_by", "accepted_at"])

        record_event(
            response.organisation,
            ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_ACCEPTED,
            actor=actor,
            related_object_type="questionnaire_response",
            related_object_id=str(response.id),
            metadata={"outcome": response.outcome, "question_id": str(response.question_id)},
        )

        if previous_accepted is not None:
            previous_accepted.status = QuestionnaireResponse.STATUS_SUPERSEDED
            previous_accepted.superseded_by = response
            # Again fine under the guard - only status/superseded_by
            # change, not any PROTECTED_WHILE_DRAFT_FIELDS entry, so the
            # OLD response's answer text/outcome/grounding/selected_keys
            # are byte-identical before and after this save (proven
            # explicitly in questionnaire/tests/test_review_workflow.py,
            # not just "no exception raised").
            previous_accepted.save(update_fields=["status", "superseded_by"])
            record_event(
                response.organisation,
                ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_SUPERSEDED,
                actor=actor,
                related_object_type="questionnaire_response",
                related_object_id=str(previous_accepted.id),
                metadata={"superseded_by": str(response.id)},
            )

    return response


def edit_questionnaire_response_text(
    response: QuestionnaireResponse, *, new_text: str, actor
) -> QuestionnaireResponse:
    """
    PID §17: the Account Holder may edit wording (`current_answer_text`
    ONLY - never `outcome`, `selected_keys` or `grounding_snapshot`; this
    function does not accept or touch those under any circumstance, and
    does not derive them from `new_text` in any way). Trusts the caller
    that `response.status == STATUS_DRAFT` (the view's job to check/
    redirect first, matching `policy.views.policy_edit`'s exact pattern).

    If `new_text == response.current_answer_text` (no real change): does
    nothing, fires no event, returns `response` unchanged - mirrors
    `policy_edit`'s "only if changed" discipline exactly (see
    `policy/views.py::policy_edit`'s
    `if changed_sections or title_changed or next_review_date_changed:`
    branch).
    """
    if new_text == response.current_answer_text:
        return response

    with transaction.atomic():
        response.current_answer_text = new_text
        response.save(update_fields=["current_answer_text", "updated_at"])
        # Deliberately does NOT put the old/new text into metadata (PID
        # §12/§24, `activity.models.ActivityEvent.EVENT_POLICY_DRAFT_EDITED`
        # precedent: only a structural changed-or-not boolean, never the
        # text content itself - "never duplicate large text where
        # canonical rows already hold it").
        record_event(
            response.organisation,
            ActivityEvent.EVENT_QUESTIONNAIRE_RESPONSE_EDITED,
            actor=actor,
            related_object_type="questionnaire_response",
            related_object_id=str(response.id),
            metadata={"answer_text_changed": True},
        )

    return response


__all__ = [
    "generate_questionnaire_response",
    "accept_questionnaire_response",
    "edit_questionnaire_response_text",
    "CONFIRM_APPLICATION_SAFE_ANSWER_TEXT",
]
