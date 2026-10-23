"""
Stage 3 "Your Technology & Data" domain adapter for IRENE's generic
question engine (WO-IRENE-001 §3.2; PID Amendment D1/D3).

Builds a REAL `irene.question_engine.contract.SectionDefinition` against
the existing, unmodified `organisations.views.STAGE3_TECHNOLOGY_DATA_FIELDS`
(ten `OrganisationProfile` fields), registers it at this module's own
import time via `irene.question_engine.registry.register_section` -
`irene.apps.IreneConfig.ready()` imports this module (mirroring the
precedent that same `ready()` already sets for `irene.checks`: a system-
check-time import, not a direct call, is Increment 1's own convention;
this module needs no deferred-`reverse()` trick, so a plain import at
`ready()` time is sufficient and simplest), so the section is always
registered before any real request can reach it.

Zero duplication of Increment 1's generic engine: `contract.py`,
`registry.py`, `presenter.py`, `explain.py` are imported here, never
modified. Zero duplication of `organisations.forms.
OrganisationProfileStage3Form`'s own canonical validation or
`organisations.views.organisation_stage3_technology_data`'s own save
path - the guarded save path this adapter uses lives in
`organisations.services` (a new, separate file), and this adapter never
writes to `OrganisationProfile` directly itself.

Question mapping (WO §3.1/§3.2, cross-checked directly against
`organisations/templates/organisations/stage3_technology_data.html`'s own
three `<fieldset>` groupings and `organisations.forms.
OrganisationProfileStage3Form`'s own field list/labels - six questions,
3.1-3.6, over the ten `STAGE3_TECHNOLOGY_DATA_FIELDS`, plus 3.7 Key
Assets as a `delegated_workflow`):

  3.1 productivity_platform              - single_choice
  3.2 primary_cloud_provider             - single_choice
  3.3 endpoint_management                - single_choice
  3.4 develops_hosts_own_software        - single_choice
  3.5 "What kinds of data..."            - grouped_independent_answer
      (handles_personal_data, handles_confidential_business_data,
       handles_payment_card_data, handles_special_category_data)
  3.6 "Do you hold... Cyber Essentials/ISO 27001" - grouped_independent_answer
      (cyber_essentials_status, iso27001_status)
  3.7 Key assets                         - delegated_workflow

Every single-choice question's own `question_code` is DELIBERATELY the
same string as the underlying `OrganisationProfile` field name, and every
grouped question's own `GroupedAnswerField.field_code` is likewise the
real model field name - a plain, direct-naming convention (not required
by Increment 1's generic contract, which never inspects these strings
itself) chosen so this adapter's own `answered_values_for_profile`/
`organisations.services.save_stage3_fields` never need a second,
hand-maintained question-code -> field-name translation table.

Authorisation (Amendment D1): `check_stage3_access` below composes
`entitlements.capabilities.has_capability` (never
`entitlements.decorators.require_capability` itself - see that
function's own docstring for why: it is a single-capability-per-route
Django view decorator, not a function several codes can be threaded
through in one call) for `irene` + `foundations` (to reach Stage 3
through IRENE at all) and, additionally, `security` ONLY for the
delegated Key Assets path (question 3.7) - never a new capability/
entitlement code of any kind. Every call re-runs tenant membership and
every capability check independently; nothing is cached across calls.
"""
from __future__ import annotations

import dataclasses
from typing import Mapping, Optional, Sequence

from irene.product_knowledge import get_concept
from irene.question_engine.contract import (
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_SINGLE_CHOICE,
    INTERACTION_CONTRACT_VERSION,
    DelegatedWorkflowQuestion,
    GroupedAnswerField,
    GroupedIndependentAnswerQuestion,
    QuestionOption,
    SectionDefinition,
    SingleChoiceQuestion,
)
from irene.question_engine.explain import resolve_explanation_skill
from irene.question_engine.registry import register_section

SECTION_CODE = "stage3_technology_data"

# This section's OWN question-catalogue version (Amendment D2's first
# versioning axis) - following the `CATALOGUE_VERSION`-constant
# convention `security_baseline.catalogue`/`questionnaire.catalogue`/
# `risk_register.methodology` already use, independent of
# `INTERACTION_CONTRACT_VERSION` (Increment 1's own, separately-versioned
# generic engine-shape axis, imported above and used as-is, never
# redefined here).
CATALOGUE_VERSION = "1.0.0"

# Amendment D1: BOTH `irene` and `foundations` are required to reach this
# section through IRENE at all - matches
# `entitlements.capabilities.ORGANISATIONS_URL_NAME_TO_CAPABILITY["stage3_technology_data"]
# == "foundations"` (the manual page's own existing gate), composed with
# IRENE's own `irene` gate, never a substitute for either.
REQUIRED_CAPABILITIES = ("irene", "foundations")

# Amendment D1's THIRD, independently-checked gate - on top of, never
# instead of, the pair above - enforced only for question 3.7's delegated
# Key Assets path. `entitlements.capabilities.
# ROUTE_NAMESPACE_TO_CAPABILITY["key_assets"] == "security"` - the EXACT
# existing code the real Key Assets app itself already requires; no new
# code is introduced.
KEY_ASSETS_DELEGATED_CAPABILITY = "security"

# The one new `irene.product_knowledge` concept this adapter needs
# (instructions item 11: "you may add ONE new concept entry to this
# existing, generic map") - added to that module directly, not here; see
# `irene/product_knowledge.py`'s own `PRODUCT_KNOWLEDGE_MAP["key_assets_manage"]`.
KEY_ASSETS_CONCEPT_ID = "key_assets_manage"

# The real `OrganisationProfile` field names each grouped question (3.5,
# 3.6) submits together - used both to build the `SectionDefinition`
# below and by `answered_values_for_profile`/tests, so the two question
# groupings are declared exactly once.
DATA_HANDLED_QUESTION_CODE = "stage3_q5_data_handled"
DATA_HANDLED_FIELD_NAMES = (
    "handles_personal_data",
    "handles_confidential_business_data",
    "handles_payment_card_data",
    "handles_special_category_data",
)
ASSURANCE_STATUS_QUESTION_CODE = "stage3_q6_assurance_status"
ASSURANCE_STATUS_FIELD_NAMES = ("cyber_essentials_status", "iso27001_status")

KEY_ASSETS_QUESTION_CODE = "stage3_q7_key_assets"

# Every single-choice question's own question_code, in declared order -
# each one IS the real OrganisationProfile field name (module docstring).
SINGLE_CHOICE_FIELD_NAMES = (
    "productivity_platform",
    "primary_cloud_provider",
    "endpoint_management",
    "develops_hosts_own_software",
)


def _options(choice_pairs: Sequence[tuple]) -> tuple:
    return tuple(QuestionOption(code=code, label=label) for code, label in choice_pairs)


def build_stage3_section() -> SectionDefinition:
    """Builds a fresh `SectionDefinition` for Stage 3 - called once, at
    this module's own import time, to populate
    `irene.question_engine.registry.SECTION_REGISTRY` (see module
    docstring). Also called directly by this adapter's own tests, which
    need a definition instance independent of whatever import-time
    registration already did (mirrors
    `irene/tests/conftest.py::build_acme_test_section`'s own "builds a
    fresh definition each call" discipline)."""
    from organisations.models import (
        ASSURANCE_STATUS_CHOICES,
        CLOUD_PROVIDER_CHOICES,
        ENDPOINT_MANAGEMENT_CHOICES,
        PRODUCTIVITY_PLATFORM_CHOICES,
        TRI_STATE_CHOICES,
    )

    return SectionDefinition(
        section_code=SECTION_CODE,
        title="Your Technology & Data",
        catalogue_version=CATALOGUE_VERSION,
        required_capabilities=REQUIRED_CAPABILITIES,
        questions=(
            SingleChoiceQuestion(
                question_code="productivity_platform",
                title="Which productivity/email platform do you mainly use?",
                help_text="",
                options=_options(PRODUCTIVITY_PLATFORM_CHOICES),
            ),
            SingleChoiceQuestion(
                question_code="primary_cloud_provider",
                title=(
                    "Do you use any cloud infrastructure providers - for "
                    "example for hosting, servers or storage - beyond your "
                    "productivity platform?"
                ),
                help_text="",
                options=_options(CLOUD_PROVIDER_CHOICES),
            ),
            SingleChoiceQuestion(
                question_code="endpoint_management",
                title="How are the devices staff use for work managed?",
                help_text="",
                options=_options(ENDPOINT_MANAGEMENT_CHOICES),
            ),
            SingleChoiceQuestion(
                question_code="develops_hosts_own_software",
                title=(
                    "Does your business develop or host its own software or "
                    "service - for example a product you sell, or a "
                    "customer-facing application?"
                ),
                help_text="",
                options=_options(TRI_STATE_CHOICES),
            ),
            GroupedIndependentAnswerQuestion(
                question_code=DATA_HANDLED_QUESTION_CODE,
                title="What kinds of data does your business handle?",
                help_text=(
                    "Select the answer that applies to each - all independent, "
                    "so answer each on its own."
                ),
                fields=(
                    GroupedAnswerField(
                        field_code="handles_personal_data",
                        label="Personal data about customers or individuals",
                        options=_options(TRI_STATE_CHOICES),
                    ),
                    GroupedAnswerField(
                        field_code="handles_confidential_business_data",
                        label=(
                            "Confidential business information (e.g. financial "
                            "records, contracts)"
                        ),
                        options=_options(TRI_STATE_CHOICES),
                    ),
                    GroupedAnswerField(
                        field_code="handles_payment_card_data",
                        label="Payment card data",
                        options=_options(TRI_STATE_CHOICES),
                    ),
                    GroupedAnswerField(
                        field_code="handles_special_category_data",
                        label=(
                            "Special category data (e.g. health, biometric, or "
                            "similarly sensitive personal data)"
                        ),
                        options=_options(TRI_STATE_CHOICES),
                    ),
                ),
            ),
            GroupedIndependentAnswerQuestion(
                question_code=ASSURANCE_STATUS_QUESTION_CODE,
                title="Do you hold, or are you working towards, any of the following?",
                help_text="",
                fields=(
                    GroupedAnswerField(
                        field_code="cyber_essentials_status",
                        label="Cyber Essentials",
                        options=_options(ASSURANCE_STATUS_CHOICES),
                    ),
                    GroupedAnswerField(
                        field_code="iso27001_status",
                        label="ISO 27001",
                        options=_options(ASSURANCE_STATUS_CHOICES),
                    ),
                ),
            ),
            DelegatedWorkflowQuestion(
                question_code=KEY_ASSETS_QUESTION_CODE,
                title="Key assets",
                help_text=(
                    "What are your business's key assets - the systems, "
                    "devices, information or services that matter most if "
                    "something goes wrong? This opens a short, separate list; "
                    "come back here when you're done."
                ),
                delegated_route_concept_id=KEY_ASSETS_CONCEPT_ID,
                delegated_capability=KEY_ASSETS_DELEGATED_CAPABILITY,
            ),
        ),
    )


# Registered at IMPORT TIME (module docstring) - the one real section
# Increment 1's registry ships with zero of. `irene.apps.IreneConfig.
# ready()` imports this module so this line always runs before any real
# request can reach it; this module's own tests additionally
# deregister/re-register around themselves where they need a clean slate
# (mirroring `irene/tests/conftest.py::registered_acme_test_section`'s own
# fixture pattern), since this module-level call only runs once per
# process/test-session.
register_section(build_stage3_section())


class Stage3AccessDenied(Exception):
    """Raised by `check_stage3_access` when the requesting user IS a
    member of `organisation_id` (so no `Http404` applies) but fails one
    or more of the required composed capability checks. Callers map this
    to `django.core.exceptions.PermissionDenied` themselves - mirroring
    `entitlements.decorators.enforce_capability_gate`'s own generic,
    reason-free 403 behaviour - rather than this module importing
    `PermissionDenied` itself and coupling to Django's view-layer error
    handling from a non-view module."""


def check_stage3_access(request, organisation_id, *, delegated_key_assets: bool = False):
    """
    Composed authorisation gate for the Stage 3 IRENE adapter (Amendment
    D1). Returns the tenant-scoped `Organisation` on success.

    Always requires BOTH `irene` and `foundations` (`REQUIRED_CAPABILITIES`
    above). When `delegated_key_assets=True` (the question 3.7 delegated-
    workflow path ONLY - never for 3.1-3.6), ALSO independently requires
    `security` (`KEY_ASSETS_DELEGATED_CAPABILITY`) - on top of, never
    instead of, the irene+foundations pair.

    Deliberately NOT built on `entitlements.decorators.require_capability`
    itself: that decorator checks exactly ONE capability code per call
    (resolved from the current route, or one explicit `capability_code`
    argument) and is a Django view decorator, not a function several
    codes can be composed through in one call for a non-view call site.
    This function instead calls the SAME underlying primitives that
    decorator itself is built on -
    `organisations.views.get_member_organisation_or_404` (tenant
    membership, the exact existing non-disclosure convention: a non-
    member gets `Http404`, never distinguishable from "does not exist")
    and `entitlements.capabilities.has_capability` (PID §9's one central
    entitlement decision) - composed here for MULTIPLE codes, in the
    exact "compose the existing checks" shape the Work Order asks for,
    never a new/parallel authorisation mechanism and never a new
    capability/entitlement code.

    Every call independently re-runs BOTH the membership check and every
    capability check - nothing from an earlier call in the same request/
    session is cached or reused (Amendment D1: "no caching an earlier
    check's result"). Call sites (a future real adapter view, and this
    module's own tests) must call this on every read, explain, save, and
    resume request - never once per session and never once per page
    load covering several subsequent actions.
    """
    from entitlements.capabilities import has_capability
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(request.user, organisation_id)

    required = list(REQUIRED_CAPABILITIES)
    if delegated_key_assets:
        required.append(KEY_ASSETS_DELEGATED_CAPABILITY)

    missing = [code for code in required if not has_capability(request, code)]
    if missing:
        raise Stage3AccessDenied(
            f"Stage 3 IRENE access denied for organisation {organisation_id!r} - "
            f"missing required capability/capabilities: {missing!r}"
        )
    return organisation


def answered_values_for_profile(profile) -> dict:
    """Builds the `answered_values` mapping
    `irene.question_engine.presenter.render_section` expects for this
    section, read straight through from the real, existing
    `OrganisationProfile` instance - `profile=None` for an organisation
    with no profile row yet, in which case every field reads as its own
    model default (e.g. `UNKNOWN`), exactly like the manual Stage 3
    form's own blank-instance rendering (`organisations.views.
    organisation_stage3_technology_data`'s `instance = ... .first()`,
    `is_new = instance is None`).

    A pure read-through, never a second, re-derived shadow of the
    canonical data (WO §1a R3: "Question-level state shown inside IRENE
    is read from the existing authoritative `OrganisationProfile` field
    data only").
    """
    from organisations.services import canonical_field_default

    def value(name):
        return getattr(profile, name) if profile is not None else canonical_field_default(name)

    values = {name: value(name) for name in SINGLE_CHOICE_FIELD_NAMES}
    for name in DATA_HANDLED_FIELD_NAMES:
        values[f"{DATA_HANDLED_QUESTION_CODE}:{name}"] = value(name)
    for name in ASSURANCE_STATUS_FIELD_NAMES:
        values[f"{ASSURANCE_STATUS_QUESTION_CODE}:{name}"] = value(name)
    return values


# ---------------------------------------------------------------------------
# Explain-this wiring (WO §1a R1; Increment 2 scope item C) - questions
# 3.1-3.6 only. Deliberately does NOT call `ai_platform.gateway.
# LiteLLMGateway.ask_adviser` anywhere below, and does NOT set
# `IRENE_ADVISER_MODE_ENABLED` - see module docstring and the Work Order's
# own explicit scope boundary for this increment. This section builds and
# proves the TYPED CONTEXT and the skill-dispatch wiring only; actually
# invoking the real gateway is a separate, future, explicitly-gated
# activity.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Stage3QuestionExplanationContext:
    """The typed, minimised context WO §1a R1 requires for an on-demand
    explanation of one of questions 3.1-3.6 (or one grouped question's
    own sub-field): the approved question wording, the permitted answer
    labels, stable section/question identifiers, the catalogue version,
    and a minimised, authorised business context (`current_answer_label`
    only - NEVER the raw `OrganisationProfile` row, never any field
    beyond what this one question/sub-field needs). This is the server-
    supplied grounding a real `ai_platform.adviser_contracts.
    AdviserRequest`'s own `tenant_context`/prompt content would ultimately
    be built from in a future increment - this dataclass itself has no
    DB access and makes no gateway call."""

    organisation_id: str
    section_code: str
    question_code: str
    field_code: Optional[str]
    catalogue_version: str
    interaction_contract_version: str
    question_title: str
    permitted_answer_labels: tuple
    current_answer_label: Optional[str]
    intent_code: str


def _label_for_code(options: Sequence, selected_code) -> Optional[str]:
    if selected_code is None:
        return None
    for option in options:
        if option.code == selected_code:
            return option.label
    return None


def _grouped_field_by_code(question, field_code: str) -> GroupedAnswerField:
    for field in question.fields:
        if field.field_code == field_code:
            return field
    raise ValueError(
        f"{question.question_code!r} has no grouped field with field_code {field_code!r}"
    )


def build_explanation_context(
    *,
    organisation,
    question,
    answered_values: Mapping[str, object],
    field_code: Optional[str] = None,
) -> Stage3QuestionExplanationContext:
    """Builds the typed, minimised explanation context for ONE of
    questions 3.1-3.6 (never 3.7 - Key Assets is a `delegated_workflow`,
    out of scope for this dataclass; see `DelegatedWorkflowQuestion`'s
    own docstring). `answered_values` is the SAME mapping
    `answered_values_for_profile`/`irene.question_engine.presenter` use -
    the caller is responsible for having built it from a real,
    authorised read of `OrganisationProfile`, never passed raw here.

    For a `single_choice` question, `field_code` must be `None` - the
    whole question has exactly one current answer. For a
    `grouped_independent_answer` question, `field_code=None` explains the
    WHOLE grouped question (permitted labels drawn from every sub-field,
    no single current answer - `current_answer_label=None`); a specific
    `field_code` scopes the explanation to that ONE sub-field's own
    permitted labels and current answer only - never more than that one
    sub-field needs (WO §1a R1: "never more than the specific question
    being explained needs").
    """
    if question.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE:
        if field_code is not None:
            raise ValueError("field_code must be None for a single_choice question.")
        permitted_labels = tuple(option.label for option in question.options)
        selected_code = answered_values.get(question.question_code)
        current_label = _label_for_code(question.options, selected_code)
    elif question.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER:
        if field_code is None:
            permitted_labels = tuple(
                option.label for field in question.fields for option in field.options
            )
            current_label = None
        else:
            field = _grouped_field_by_code(question, field_code)
            permitted_labels = tuple(option.label for option in field.options)
            selected_code = answered_values.get(f"{question.question_code}:{field_code}")
            current_label = _label_for_code(field.options, selected_code)
    else:
        raise ValueError(
            "build_explanation_context only supports questions 3.1-3.6 "
            f"(single_choice/grouped_independent_answer); got capability_type "
            f"{question.capability_type!r} for {question.question_code!r}"
        )

    return Stage3QuestionExplanationContext(
        organisation_id=str(organisation.id),
        section_code=SECTION_CODE,
        question_code=question.question_code,
        field_code=field_code,
        catalogue_version=CATALOGUE_VERSION,
        interaction_contract_version=INTERACTION_CONTRACT_VERSION,
        question_title=question.title,
        permitted_answer_labels=permitted_labels,
        current_answer_label=current_label,
        intent_code=question.explain_intent_code,
    )


@dataclasses.dataclass(frozen=True)
class Stage3ExplanationDispatch:
    """What `resolve_stage3_explanation` hands back: the typed context
    (above) paired with whichever `irene.skill_loader.LoadedSkill`
    Increment 1's existing, unmodified
    `irene.question_engine.explain.resolve_explanation_skill`/`irene.
    skill_router.select_skill` resolved for this question's own
    `explain_intent_code` - `skill=None` under the exact same fail-closed
    conditions `select_skill` already documents (an unclear/unrecognised
    intent code, or a skill that fails its own manifest validation).
    Carrying both together is this module's whole job for Increment 2's
    Explain-this scope item - handing (context, skill) to a real gateway
    call is a future increment's responsibility, not this one's."""

    context: Stage3QuestionExplanationContext
    skill: object


def resolve_stage3_explanation(
    *,
    organisation,
    question,
    answered_values: Mapping[str, object],
    field_code: Optional[str] = None,
) -> Stage3ExplanationDispatch:
    """Builds the typed context (`build_explanation_context`) and
    resolves the dispatch-by-intent-code-only skill
    (`irene.question_engine.explain.resolve_explanation_skill`, Increment
    1's own, unmodified entry point) for one of questions 3.1-3.6.
    Returns both together, calling NEITHER
    `ai_platform.gateway.LiteLLMGateway.ask_adviser` NOR anything else
    that would make a real AI-gateway call - see module docstring."""
    context = build_explanation_context(
        organisation=organisation,
        question=question,
        answered_values=answered_values,
        field_code=field_code,
    )
    skill = resolve_explanation_skill(question)
    return Stage3ExplanationDispatch(context=context, skill=skill)


__all__ = [
    "SECTION_CODE",
    "CATALOGUE_VERSION",
    "REQUIRED_CAPABILITIES",
    "KEY_ASSETS_DELEGATED_CAPABILITY",
    "KEY_ASSETS_CONCEPT_ID",
    "DATA_HANDLED_QUESTION_CODE",
    "DATA_HANDLED_FIELD_NAMES",
    "ASSURANCE_STATUS_QUESTION_CODE",
    "ASSURANCE_STATUS_FIELD_NAMES",
    "KEY_ASSETS_QUESTION_CODE",
    "SINGLE_CHOICE_FIELD_NAMES",
    "build_stage3_section",
    "Stage3AccessDenied",
    "check_stage3_access",
    "answered_values_for_profile",
    "Stage3QuestionExplanationContext",
    "build_explanation_context",
    "Stage3ExplanationDispatch",
    "resolve_stage3_explanation",
]
