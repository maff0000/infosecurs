"""
Allowlisted, same-organisation-verified source registry for
`SecurityTask.source_kind`/`source_object_id` (and the parallel
`completion_evidence_source_kind`/`completion_evidence_source_object_id`
pair) - M010A PID §2 ("Foreign source links through allowlisted registry;
verify ownership/tenant before linking; no arbitrary model references from
untrusted input"), M010 data contract §1 ("source_locator registered (app,
model, key) plus verified relation; never a model-provided arbitrary table
name"), M010 threat model §2 ("No generic execute_query, get_object,
fetch_url... A product-knowledge registry is an allowlist of domain-
specific service calls... not a database schema dumped into the model").

This is a plain Python dict, the same shape/discipline as entitlements.
capabilities.ROUTE_NAMESPACE_TO_CAPABILITY: a fixed, code-reviewed
allowlist, never a database-configurable or model-name-driven lookup.
Every resolver filters by the organisation BEFORE returning anything, so a
`source_object_id` belonging to a different organisation, or that does not
exist at all, can never resolve to a real object - `resolve_source_locator`
deliberately cannot distinguish "wrong organisation" from "does not exist"
to its caller (both return `None`), matching this codebase's established
non-disclosing convention for cross-tenant probes.

Each resolver is a lazy (function-local) import of the target app's model -
this module must not create an import-time dependency from `security_tasks`
onto `key_assets`/`risk_register`/`remediation`/`policy`/`evidence`/
`security_baseline` (none of which import `security_tasks`, so there is no
real circular-import risk today, but a lazy import keeps this registry
cheap to extend without reasoning about app-loading order every time a new
kind is added - the same lazy-import discipline `entitlements.decorators`
already uses for its own cross-app call).

Registered today: six existing tenant-owned models this package's own test
suite exercises. Adding a new source kind later is a one-line dict entry
plus a resolver function - never a schema change to `SecurityTask` itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from security_tasks.models import SOURCE_KIND_NONE

SOURCE_KIND_KEY_ASSET = "key_assets.keyasset"
SOURCE_KIND_RISK = "risk_register.risk"
SOURCE_KIND_REMEDIATION_ACTION = "remediation.remediationaction"
SOURCE_KIND_POLICY_VERSION = "policy.policyversion"
SOURCE_KIND_EVIDENCE_ITEM = "evidence.evidenceitem"
SOURCE_KIND_BASELINE_ANSWER = "security_baseline.baselineanswer"


@dataclass(frozen=True)
class SourceLocatorSpec:
    label: str
    resolver: Callable[[object, str], Optional[object]]


def _resolve_key_asset(organisation, key):
    from key_assets.models import KeyAsset

    return KeyAsset.objects.filter(organisation=organisation, pk=key).first()


def _resolve_risk(organisation, key):
    from risk_register.models import Risk

    return Risk.objects.filter(organisation=organisation, pk=key).first()


def _resolve_remediation_action(organisation, key):
    from remediation.models import RemediationAction

    return RemediationAction.objects.filter(organisation=organisation, pk=key).first()


def _resolve_policy_version(organisation, key):
    from policy.models import PolicyVersion

    return PolicyVersion.objects.filter(organisation=organisation, pk=key).first()


def _resolve_evidence_item(organisation, key):
    from evidence.models import EvidenceItem

    return EvidenceItem.objects.filter(organisation=organisation, pk=key).first()


def _resolve_baseline_answer(organisation, key):
    from security_baseline.models import BaselineAnswer

    # BaselineAnswer has no direct `organisation` FK (it hangs off
    # BaselineAssessment, which does) - see security_baseline/models.py.
    # The `assessment__organisation` hop is the correct, existing
    # relation, not a new shortcut this app invents.
    return BaselineAnswer.objects.filter(assessment__organisation=organisation, pk=key).first()


SOURCE_LOCATOR_REGISTRY: dict[str, SourceLocatorSpec] = {
    SOURCE_KIND_KEY_ASSET: SourceLocatorSpec("Key asset", _resolve_key_asset),
    SOURCE_KIND_RISK: SourceLocatorSpec("Risk", _resolve_risk),
    SOURCE_KIND_REMEDIATION_ACTION: SourceLocatorSpec("Remediation action", _resolve_remediation_action),
    SOURCE_KIND_POLICY_VERSION: SourceLocatorSpec("Policy version", _resolve_policy_version),
    SOURCE_KIND_EVIDENCE_ITEM: SourceLocatorSpec("Evidence item", _resolve_evidence_item),
    SOURCE_KIND_BASELINE_ANSWER: SourceLocatorSpec("Baseline answer", _resolve_baseline_answer),
}


class UnregisteredSourceKindError(ValueError):
    """Raised when a caller supplies a `source_kind` that is neither
    `SOURCE_KIND_NONE` nor a key in `SOURCE_LOCATOR_REGISTRY` - fail loud
    at the point something tries to PERSIST an unregistered kind (never a
    silent accept, per the threat model's "no arbitrary model references"
    rule). Resolving an EXISTING row's `source_kind` that has since been
    deregistered is a separate, display-time concern - see `resolve_
    source_locator`'s own docstring for why that path returns `None`
    instead of raising."""


def resolve_source_locator(organisation, source_kind, source_object_id, *, strict: bool = True):
    """
    Returns the resolved, organisation-owned object, or `None` if
    `source_kind == SOURCE_KIND_NONE`, `source_object_id` is falsy, the
    object does not exist, or it belongs to a different organisation.

    `strict=True` (the default, used by `security_tasks.services.
    create_task` before persisting a new link) raises
    `UnregisteredSourceKindError` for any `source_kind` not in the
    registry - fail closed before anything is ever written.

    `strict=False` (used by `get_task_detail`/`get_task_list` when
    displaying an EXISTING, already-persisted task) instead returns
    `None` for an unregistered kind, so a task whose source kind was
    later deregistered still renders as "Source unavailable" rather than
    raising a 500 - M010 data contract §1's "If source is deleted/hidden,
    show 'Source unavailable' without revealing other tenants" extends
    naturally to "if the kind itself is no longer registered".
    """
    if source_kind == SOURCE_KIND_NONE or not source_object_id:
        return None
    spec = SOURCE_LOCATOR_REGISTRY.get(source_kind)
    if spec is None:
        if strict:
            raise UnregisteredSourceKindError(
                f"{source_kind!r} is not a registered source_locator kind."
            )
        return None
    try:
        return spec.resolver(organisation, source_object_id)
    except (ValueError, TypeError):
        # A malformed key for this kind's primary-key type (e.g. a
        # non-UUID string against a UUID-keyed model) is "not found",
        # never a 500 and never a hint to the caller about why.
        return None


def source_kind_choices():
    """Form/template choice list: `SOURCE_KIND_NONE` first, then every
    registered kind's human label - never the raw registry dict exposed
    directly to a template or form field."""
    choices = [(SOURCE_KIND_NONE, "No linked source")]
    choices += [(key, spec.label) for key, spec in SOURCE_LOCATOR_REGISTRY.items()]
    return choices


__all__ = [
    "SOURCE_KIND_NONE",
    "SOURCE_KIND_KEY_ASSET",
    "SOURCE_KIND_RISK",
    "SOURCE_KIND_REMEDIATION_ACTION",
    "SOURCE_KIND_POLICY_VERSION",
    "SOURCE_KIND_EVIDENCE_ITEM",
    "SOURCE_KIND_BASELINE_ANSWER",
    "SourceLocatorSpec",
    "SOURCE_LOCATOR_REGISTRY",
    "UnregisteredSourceKindError",
    "resolve_source_locator",
    "source_kind_choices",
]
