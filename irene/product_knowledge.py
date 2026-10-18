"""
Product Knowledge Map (M010C PID §2; docs/architecture/
M010-ADVISER-TOOLS-AND-SKILLS.md §2).

A plain, code-reviewed Python dict - the EXACT same discipline
`security_tasks.source_registry.SOURCE_LOCATOR_REGISTRY` and
`entitlements.capabilities.ROUTE_NAMESPACE_TO_CAPABILITY` already use (both
named explicitly in this package's own PID as the template to follow): a
fixed allowlist, never a database-configurable or model-name-driven lookup,
never the full schema/table list handed to a model.

What a `ConceptEntry` is for: the ONLY thing `irene.tools.get_registered_route`
may resolve a safe internal URL from, and the ONLY thing `AdviserResponse.
source_links[].concept_id` may ever reference once `irene.orchestration`
has filtered the model's claimed source links against this registry (M010
threat model §1.5/§1.8: "the provider response has zero grant authority" -
a `concept_id` the model names that is NOT in this registry is silently
dropped, never resolved, never rendered).

`validate_product_knowledge_map()` is the boot-time validator M010C PID §2
asks for ("Validate every registered route/tool at boot/test, reject
unknown source/URL") - wired as a Django system check via `irene.checks`
(see that module and `irene.apps.IreneConfig.ready()` for why a system
check, not a direct `ready()` call). It proves, for every entry:

  1. `service_reference` resolves to a real, importable, callable object
     (via `importlib` - never executed, only resolved and `callable()`-
     checked).
  2. `route_name` resolves via `django.urls.reverse()` against a
     synthetic, non-existent sample organisation id (and any other sample
     kwargs the entry declares) - proving the route NAME is real and
     accepts the kwarg shape this registry expects, without ever
     requiring a real database row to exist for a boot-time/CI check.
  3. `required_capability` is one of the capability codes this codebase's
     own `entitlements.capabilities` module already recognises (every
     `ROUTE_NAMESPACE_TO_CAPABILITY`/`ORGANISATIONS_URL_NAME_TO_CAPABILITY`
     value, plus "irene"/"tasks"/"foundations"/"security" directly, since
     those are real seeded `ProductArea.code` values this registry's own
     entries use) - never an invented capability string a `ProductArea`
     row does not actually exist for.

A registered concept whose real source service/route later disappears
(deregistered module, renamed route) FAILS this check loudly at
boot/CI-check time - "an incomplete/unimplemented real domain service
prevents an optional adapter... gate that adapter off" (M010 master PID
§10) is handled by setting `availability_flag=False` on that entry (see
`irene.tools`'s own "only AVAILABLE concepts are ever offered to the
model" filter), not by leaving a broken entry for the validator to choke
on silently - the validator is intentionally NOT skipped for an
unavailable entry: a disabled concept with a genuinely broken reference
is still a bug to catch now, before it is ever re-enabled.
"""
from __future__ import annotations

import dataclasses
import importlib
import uuid
from typing import Optional

SAMPLE_ORGANISATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SAMPLE_QUESTION_KEY = "sample-question-key"
SAMPLE_TASK_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

# Mirrors entitlements.capabilities' own real capability codes
# (ROUTE_NAMESPACE_TO_CAPABILITY / ORGANISATIONS_URL_NAME_TO_CAPABILITY
# values) plus "home" - the full set of real seeded `ProductArea.code`
# values any `required_capability` below may legitimately name. Checked
# independently here (never imported from entitlements.capabilities
# itself) so a typo in ONE of that module's many string literals can never
# silently become "the known-good set" this validator checks against.
KNOWN_CAPABILITY_CODES = frozenset(
    {
        "home",
        "company",
        "foundations",
        "security",
        "policies",
        "customer_assurance",
        "tasks",
        "irene",
    }
)


@dataclasses.dataclass(frozen=True)
class ConceptEntry:
    """One Product Knowledge Map registry row (M010C PID §2's exact field
    list)."""

    concept_id: str
    label: str
    service_reference: str  # "dotted.module.path:callable_name"
    route_name: str
    relationship_type: str
    required_capability: str
    allowed_projection_fields: tuple
    availability_flag: bool
    version: str
    # Validator-only - kwargs (besides organisation_id, always supplied)
    # this route_name needs to resolve a sample URL. Never used at
    # runtime by irene.tools.get_registered_route, which always receives
    # REAL, caller-supplied object_locator kwargs for an existing, tenant-
    # owned object - see that function's own docstring.
    sample_kwargs: dict = dataclasses.field(default_factory=dict)


PRODUCT_KNOWLEDGE_MAP: dict[str, ConceptEntry] = {
    "foundations_current_question": ConceptEntry(
        concept_id="foundations_current_question",
        label="Current guided Foundations question",
        service_reference="foundations_journey.services:get_foundations_question",
        route_name="foundations_journey:guided_question",
        relationship_type="guided_journey_step",
        required_capability="security",
        allowed_projection_fields=("question_key", "title", "stage_progress_copy", "saved_option_code"),
        availability_flag=True,
        version="1.0.0",
        sample_kwargs={"question_key": SAMPLE_QUESTION_KEY},
    ),
    "foundations_manual_question_page": ConceptEntry(
        concept_id="foundations_manual_question_page",
        label="Manual Foundations question page",
        service_reference="security_baseline.stage4:offered_options",
        route_name="security_baseline:foundations_question",
        relationship_type="manual_fallback_page",
        required_capability="security",
        allowed_projection_fields=("question_key",),
        availability_flag=True,
        version="1.0.0",
        sample_kwargs={"question_key": SAMPLE_QUESTION_KEY},
    ),
    "foundations_workspace": ConceptEntry(
        concept_id="foundations_workspace",
        label="Foundations workspace (18-item completion)",
        service_reference="entitlements.metrics:get_security_foundations_completion",
        route_name="organisations:foundations",
        relationship_type="workspace_page",
        required_capability="foundations",
        allowed_projection_fields=("percentage", "completed_count", "total_count"),
        availability_flag=True,
        version="1.0.0",
    ),
    "task_list": ConceptEntry(
        concept_id="task_list",
        label="Shared Tasks list",
        service_reference="security_tasks.services:get_task_list",
        route_name="security_tasks:list",
        relationship_type="workspace_page",
        required_capability="tasks",
        allowed_projection_fields=("title", "status", "due_at", "task_group"),
        availability_flag=True,
        version="1.0.0",
    ),
    "task_detail": ConceptEntry(
        concept_id="task_detail",
        label="Task detail",
        service_reference="security_tasks.services:get_task_detail",
        route_name="security_tasks:detail",
        relationship_type="object_detail_page",
        required_capability="tasks",
        allowed_projection_fields=("title", "status", "due_at"),
        availability_flag=True,
        version="1.0.0",
        sample_kwargs={"task_id": SAMPLE_TASK_ID},
    ),
    # M010E PID §3 - the ONLY navigation this package adds: a safe link to
    # the EXISTING, real, unmodified M009 upload view. `required_capability`
    # is "customer_assurance" (tier 2, Monthly+) - the real, existing gate
    # that route already carries via `entitlements.capabilities.
    # ROUTE_NAMESPACE_TO_CAPABILITY["questionnaire"]`, unchanged by this
    # package; `irene.tools.get_registered_route`'s own `_revalidate` call
    # re-proves this independently on every resolution, so a caller whose
    # tier has since dropped gets `None` here, never a stale link. There is
    # no M009 write path anywhere near this entry - `get_registered_route`
    # only ever resolves a URL string; the actual upload still only ever
    # happens through that real view's own form POST.
    "customer_assurance_upload": ConceptEntry(
        concept_id="customer_assurance_upload",
        label="Customer Assurance questionnaire upload",
        service_reference="questionnaire.import_services:ingest_questionnaire_import",
        route_name="questionnaire:import_upload",
        relationship_type="workspace_page",
        required_capability="customer_assurance",
        allowed_projection_fields=(),
        availability_flag=True,
        version="1.0.0",
    ),
}


class ProductKnowledgeMapValidationError(Exception):
    """Raised by `validate_product_knowledge_map()` - collects every
    failing entry's reason, never stops at the first one, so a single
    `manage.py check` run reports every problem at once."""


def _resolve_service_reference(reference: str):
    module_path, _, attr_name = reference.partition(":")
    if not module_path or not attr_name:
        raise ValueError(f"service_reference {reference!r} must be 'module.path:callable_name'")
    module = importlib.import_module(module_path)
    target = getattr(module, attr_name, None)
    if target is None or not callable(target):
        raise ValueError(f"service_reference {reference!r} does not resolve to a callable")
    return target


def validate_product_knowledge_map() -> None:
    """Boot-time/test-time validator (M010C PID §2). Raises
    `ProductKnowledgeMapValidationError`, carrying every problem found, if
    any entry's `service_reference` does not resolve, any entry's
    `route_name` does not reverse, or any entry's `required_capability` is
    not a known capability code. Raises nothing (returns `None`) if the
    whole registry is valid."""
    from django.urls import NoReverseMatch, reverse

    problems: list[str] = []

    for concept_id, entry in PRODUCT_KNOWLEDGE_MAP.items():
        if entry.concept_id != concept_id:
            problems.append(f"{concept_id!r}: dict key does not match entry.concept_id {entry.concept_id!r}")

        try:
            _resolve_service_reference(entry.service_reference)
        except Exception as exc:  # noqa: BLE001 - collect every failure, never crash early
            problems.append(f"{concept_id!r}: service_reference {entry.service_reference!r} invalid: {exc}")

        kwargs = {"organisation_id": SAMPLE_ORGANISATION_ID, **entry.sample_kwargs}
        try:
            reverse(entry.route_name, kwargs=kwargs)
        except NoReverseMatch as exc:
            problems.append(f"{concept_id!r}: route_name {entry.route_name!r} does not resolve: {exc}")

        if entry.required_capability not in KNOWN_CAPABILITY_CODES:
            problems.append(
                f"{concept_id!r}: required_capability {entry.required_capability!r} is not a known capability code"
            )

    if problems:
        raise ProductKnowledgeMapValidationError("; ".join(problems))


def get_concept(concept_id: str) -> Optional[ConceptEntry]:
    """Returns the registered, AVAILABLE entry for `concept_id`, or `None`
    for an unregistered OR explicitly-disabled concept - callers (`irene.
    tools.get_registered_route`, `irene.orchestration`'s source-link
    filter) must treat both the same way: "cannot be resolved/offered",
    never distinguishing the two to a model or a cross-tenant prober."""
    entry = PRODUCT_KNOWLEDGE_MAP.get(concept_id)
    if entry is None or not entry.availability_flag:
        return None
    return entry


def available_concepts() -> tuple[ConceptEntry, ...]:
    return tuple(entry for entry in PRODUCT_KNOWLEDGE_MAP.values() if entry.availability_flag)
