"""
Policy draft-generation service (M004 PID §14-15, §22 -
m004-2a-policy-foundation dispatch): the seam between the view layer and
`ai_platform`'s policy-generation contract/gateway/orchestration, mirroring
`risk_register.interpretation_service`'s shape for the equivalent seam on
the second AI task.

`generate_policy_draft` is the single entrypoint the view calls. It:

1. builds this organisation's `PolicyGroundingPayload`
   (`policy.grounding.build_policy_grounding_payload`);
2. calls `ai_platform.policy_orchestration.generate_policy` (one call, at
   most one bounded retry for a retryable failure only - the same
   discipline `ai_platform.orchestration.generate_risks` /
   `ai_platform.interpretation_orchestration.interpret_candidates` already
   use);
3. on success, creates (or continues) this organisation's
   `PolicyDocument`, and creates a NEW `PolicyVersion`
   (`status=draft`, `generation_source=ai`, ...) - never mutates an
   existing version, so this function alone can never violate the
   immutability guarantee `policy.models.PolicyVersion.save()` enforces;
4. emits exactly one `policy_draft_generated` `ActivityEvent` (PID §22),
   in the same transaction as the `PolicyDocument`/`PolicyVersion` writes,
   mirroring `workplace.services.create_workplace`'s single-writer-plus-
   same-transaction-event discipline;
5. on failure, raises `ai_platform.policy_orchestration.
   PolicyGenerationFailed` and creates nothing at all - no
   `PolicyDocument`, no `PolicyVersion`, no activity event. This holds
   structurally: `generate_policy` either returns a fully validated
   `PolicyGenerationResult`, or raises before this function ever reaches
   its persistence step (`_persist_draft` below), so there is no
   intermediate state a caller could observe.

The AI call itself (`generate_policy`) deliberately runs OUTSIDE any
`transaction.atomic()` block - it is an external HTTP call, and the
existing `ai_platform.policy_orchestration.generate_policy` already owns
its own `AIInvocationRecord` lifecycle/commits independently of whatever
this function does afterwards (identical pattern to
`risk_register.interpretation_service.interpret_draft_risks`, which does
not wrap its own call to `interpret_candidates` in `atomic()` either).
Only the persistence step that follows a successful call is wrapped, so a
`PolicyDocument`/`PolicyVersion`/`ActivityEvent` write can never partially
apply.
"""
from __future__ import annotations

import dataclasses

from django.db import transaction

from activity.models import ActivityEvent
from activity.services import record_event
from ai_platform.gateway import LiteLLMGateway, PolicyGenerationGateway
from ai_platform.policy_contracts import PolicyGenerationResult
from ai_platform.policy_orchestration import generate_policy
from ai_platform.prompts.policy_generation_v1 import PROMPT_VERSION

from policy.models import PolicyDocument, PolicyVersion
from policy.grounding import build_policy_grounding_payload


def _next_version_number(document: PolicyDocument) -> int:
    """1 for a brand-new document, else one past this document's highest
    existing `version_number` (PID §15 "1, 2, 3... per document")."""
    latest = document.versions.order_by("-version_number").first()
    return (latest.version_number + 1) if latest is not None else 1


@transaction.atomic
def _persist_draft(organisation, result: PolicyGenerationResult, record, *, actor) -> PolicyVersion:
    document, _ = PolicyDocument.objects.get_or_create(organisation=organisation)
    version = PolicyVersion.objects.create(
        document=document,
        organisation=organisation,
        version_number=_next_version_number(document),
        status=PolicyVersion.STATUS_DRAFT,
        title=result.policy_title,
        sections=[dataclasses.asdict(section) for section in result.sections],
        review_warnings=[dataclasses.asdict(warning) for warning in result.review_warnings],
        generation_source=PolicyVersion.GENERATION_SOURCE_AI,
        prompt_version=result.prompt_version,
        ai_invocation_record=record,
        created_by=actor,
    )
    record_event(
        organisation,
        ActivityEvent.EVENT_POLICY_DRAFT_GENERATED,
        actor=actor,
        related_object_type="policy_version",
        related_object_id=str(version.id),
        metadata={"version_number": version.version_number},
    )
    return version


def generate_policy_draft(
    organisation, *, actor, gateway: PolicyGenerationGateway = None
) -> PolicyVersion:
    """Run one bounded AI policy-generation call for `organisation` and
    persist the result as a new draft `PolicyVersion`.

    Raises `ai_platform.policy_orchestration.PolicyGenerationFailed` on
    failure - see module docstring point 5: nothing is created in that
    case.

    `gateway` defaults to a real `LiteLLMGateway()` (constructed lazily
    inside this call, not at import time - PID §14: generation happens
    only on an explicit user action, mirroring `LiteLLMGateway`'s own lazy
    config-loading discipline, and `risk_register.interpretation_service.
    interpret_draft_risks`'s identical default). Tests pass
    `ai_platform.testing.FakePolicyGateway` explicitly.
    """
    grounding = build_policy_grounding_payload(organisation)
    gateway = gateway if gateway is not None else LiteLLMGateway()

    result, record = generate_policy(gateway, grounding, PROMPT_VERSION)

    return _persist_draft(organisation, result, record, actor=actor)


__all__ = ["generate_policy_draft"]
