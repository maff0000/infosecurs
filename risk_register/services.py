"""
Generation service: the seam between the Risk-domain view layer and
`ai_platform.orchestration.generate_risks` (M002 PID §14, §15).

`generate_draft_risks` is the single entrypoint the view calls. It accepts
the gateway as a constructor-style argument (default `None`, meaning
"construct the real `LiteLLMGateway`") so a test can call this exact
function with a `FakeGateway` and observe the exact same behaviour/response
contract the view depends on - no separate test-only code path.

Failure handling (PID §14): if `generate_risks` raises `GenerationFailed`,
this function does not catch it - it propagates to the caller. Nothing in
this module writes a `Risk` row until generation has fully succeeded, so a
gateway outage leaves the existing `Risk` table completely untouched; the
caller (the view) is responsible for turning that exception into a clear
user-facing error.

Regeneration safety (PID §15): this function only ever calls
`Risk.objects.create(...)` - it never queries for, updates, or deletes an
existing `Risk` row, confirmed or otherwise. Calling it again after risks
already exist therefore cannot overwrite or mutate a confirmed risk by
construction, not merely by convention.
"""
from __future__ import annotations

import re
import uuid

from ai_platform.gateway import DEFAULT_MODEL_ALIAS, LiteLLMGateway, RiskGenerationGateway
from ai_platform.orchestration import GenerationFailed, generate_risks
from ai_platform.prompts.risk_generation_v3 import PROMPT_VERSION

from key_assets.models import KeyAsset
from risk_register.grounding import build_grounding_payload
from risk_register.models import Risk

_ASSET_REF_RE = re.compile(r"^asset:(?P<id>.+)$")


def _resolve_key_asset(organisation, asset_reference: str):
    """Resolve a candidate's raw `asset_reference` string to a real,
    tenant-owned `KeyAsset`, or `None` if it doesn't (yet) resolve to one.

    Deliberately re-scoped to `organisation` here, not merely trusted from
    the grounding payload that was sent: even if a generated
    `asset_reference` happened to be a syntactically valid UUID belonging to
    a *different* organisation's asset (a hallucination, not something this
    adapter's grounding could have supplied - see risk_register.grounding),
    the `organisation=organisation` filter below means it can never be
    linked via this FK. A `Risk.key_asset` can only ever point at an asset
    that belongs to the same organisation as the `Risk` itself.
    """
    match = _ASSET_REF_RE.match(asset_reference or "")
    if not match:
        return None
    try:
        asset_id = uuid.UUID(match.group("id"))
    except ValueError:
        return None
    return KeyAsset.objects.filter(organisation=organisation, id=asset_id).first()


def generate_draft_risks(organisation, gateway: RiskGenerationGateway = None, *, model_alias: str = DEFAULT_MODEL_ALIAS):
    """Build grounding for `organisation`, run one generation, and persist
    each returned candidate as a new draft `Risk` row.

    Returns `(created_risks, invocation_record)` on success.

    Raises `ai_platform.orchestration.GenerationFailed` on any generation
    failure - propagated, not swallowed, so the caller can distinguish
    "no risks generated because nothing happened yet" from "generation was
    attempted and failed" and show the right message; either way, no `Risk`
    row is created.
    """
    if gateway is None:
        gateway = LiteLLMGateway()

    grounding = build_grounding_payload(organisation)
    result, invocation_record = generate_risks(
        gateway, grounding, PROMPT_VERSION, model_alias=model_alias
    )

    created = []
    for candidate in result.candidates:
        risk = Risk.objects.create(
            organisation=organisation,
            key_asset=_resolve_key_asset(organisation, candidate.asset_reference),
            asset_reference=candidate.asset_reference,
            title=candidate.title,
            threat=candidate.threat,
            vulnerability=candidate.vulnerability,
            impact=candidate.suggested_impact,
            likelihood=candidate.suggested_likelihood,
            rationale=candidate.rationale,
            proposed_treatment=candidate.proposed_treatment,
            grounding_refs=list(candidate.grounding_refs),
            assumptions=list(candidate.assumptions),
            source=Risk.SOURCE_AI,
            status=Risk.STATUS_DRAFT_AI_SUGGESTED,
            ai_invocation_record=invocation_record,
        )
        created.append(risk)

    return created, invocation_record


__all__ = ["generate_draft_risks", "GenerationFailed"]
