"""
IRENE modal views (M010C PID §1/§5). Same established convention as
`security_tasks.views`/`foundations_journey.views`: `@login_required` +
`@require_capability()` + `get_member_organisation_or_404` as every view's
own first action; every mutation goes through `irene.services`/`irene.
tools`, never a direct model write here.

`build_modal_context` is the ONE place the four-tab modal's server-
rendered content is assembled - called by `organisations.views.
organisation_detail` (Home) so the modal appears "after authenticated
Home render" exactly as M010C PID §1 describes, with NO separate fetch/
AJAX round-trip and no SPA framework (ADR-0001) - all four tab panels are
present in the same page's DOM from the start; only CSS/`static/irene/js/
modal.js` toggle which panel is visible. This also means "manual app
works without JS" holds trivially: with JS disabled, the modal section is
simply an ordinary, always-visible part of the Home page rather than an
overlay - still fully readable/usable, never a dead end (M010-UX-
CUSTOMER-JOURNEYS.md §1's "Modal closed or provider offline -> complete
manual workflow remains accessible").
"""
from __future__ import annotations

import dataclasses

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse

from entitlements.decorators import require_capability
from irene import orchestration
from irene import services as conversation_services
from irene import tools as irene_tools
from irene.exceptions import ActionProposalExpiredError
from irene.forms import AskForm, ConfirmTaskForm
from irene.models import ActionDecisionState, AssistantAction
from irene.question_engine.adapters.stage3_technology_data import (
    SECTION_CODE as STAGE3_SECTION_CODE,
)
from irene.question_engine.adapters.stage3_technology_data import (
    Stage3AccessDenied,
    answered_values_for_profile,
    check_stage3_access,
    resolve_stage3_explanation,
)
from irene.question_engine.contract import (
    CAPABILITY_TYPE_DELEGATED_WORKFLOW,
    CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER,
    CAPABILITY_TYPE_SINGLE_CHOICE,
)
from irene.question_engine.presenter import render_section
from irene.question_engine.registry import UnregisteredSectionError, get_section
from irene.question_engine.stage3_orchestration import ask_irene_stage3_explain

# M010C PID §2 ("Task List available without modal via sidebar") - bounded
# fragment sizes, never the full paginated page a dedicated sidebar visit
# would show.
MODAL_TASK_LIST_SIZE = 5
MODAL_ACTIVITY_LIST_SIZE = 8

# WO-IRENE-001 Increment 2 (browser-wiring) - the session key a pending
# "Explain this" result for one Stage 3 question is stashed under between
# the explain POST's redirect and the next render of the Stage 3 tab/panel
# (a plain post/redirect/get flash, same no-AJAX/no-SPA convention every
# other IRENE modal action already uses - ADR-0001). Popped (read-once) by
# `_build_stage3_tab_context` below, never left to linger across an
# unrelated later page view.
STAGE3_EXPLANATION_SESSION_KEY = "irene_stage3_pending_explanation"


@dataclasses.dataclass(frozen=True)
class ModalContext:
    irene_enabled: bool
    auto_open: bool
    continue_tab: dict
    tasks_tab: dict
    activity_tab: dict
    ask_tab: dict
    # WO-IRENE-001 Increment 2 (browser-wiring) - additive, optional: a
    # 5th tab, `None` whenever the requesting session fails Stage 3's own
    # composed `irene`+`foundations` gate (Amendment D1) - the existing
    # four tabs/fields above are untouched, both in shape and in every
    # existing call site that already constructs a `ModalContext` without
    # naming this field.
    stage3_tab: "dict | None" = None


def build_modal_context(request, organisation) -> "ModalContext | None":
    """Returns `None` if `settings.IRENE_ENABLED` is off or this session
    does not hold the `irene` capability - the caller (`organisations.
    views.organisation_detail`) then simply omits the modal from the
    template context, same as any other entitlement-gated section."""
    from django.conf import settings

    from entitlements.capabilities import has_capability
    from foundations_journey.services import get_foundations_question, get_journey_checkpoint
    from security_tasks.models import SecurityTaskEvent
    from security_tasks.services import get_task_list

    if not getattr(settings, "IRENE_ENABLED", True):
        return None
    if not has_capability(request, "irene"):
        return None

    user = request.user

    # Continue tab - M010C PID §1 "Continue always presents server-
    # computed next work, no empty general chat landing" (M010-MASTER-
    # PID-ROADMAP.md invariant 8/M010C evidence item).
    checkpoint = get_journey_checkpoint(organisation, user)
    question = None
    if checkpoint.current_question_key:
        view_model = get_foundations_question(organisation, user, checkpoint.current_question_key)
        question = {
            "question_key": view_model.question_key,
            "title": view_model.title,
            "stage_progress_copy": view_model.stage_progress_copy,
            "manual_page_url": view_model.manual_page_url,
            "completion_percentage": view_model.completion_percentage,
        }
    continue_tab = {"checkpoint_state": checkpoint.checkpoint_state, "question": question}

    # Tasks tab - a bounded view, never the full Tasks page's own pagination.
    task_page = get_task_list(organisation, page_size=MODAL_TASK_LIST_SIZE)
    tasks_tab = {
        "tasks": task_page.items,
        "total_count": task_page.total_count,
        "tasks_url": reverse("security_tasks:list", args=[organisation.id]),
    }

    # Activity tab - bounded, read-only recent SecurityTaskEvent/
    # AssistantAction summary for this organisation (M010C PID §1).
    task_events = list(
        SecurityTaskEvent.objects.filter(organisation=organisation).select_related("task", "actor_user")[
            :MODAL_ACTIVITY_LIST_SIZE
        ]
    )
    assistant_actions = list(
        AssistantAction.objects.filter(organisation=organisation).select_related("actor")[:MODAL_ACTIVITY_LIST_SIZE]
    )
    activity_tab = {"task_events": task_events, "assistant_actions": assistant_actions}

    # Ask tab - private to this user (irene.services' own owner-scoping).
    conversation = conversation_services.get_or_create_active_conversation(organisation, user)
    message_page = conversation_services.list_messages(organisation, user, conversation.id)
    pending_actions = AssistantAction.objects.filter(
        organisation=organisation,
        actor=user,
        conversation=conversation,
        decision_state=ActionDecisionState.PROPOSED,
    ).order_by("-created_at")[:3]
    ask_tab = {
        "conversation_id": conversation.id,
        "messages": message_page.messages,
        "pending_actions": pending_actions,
        "form": AskForm(),
        "adviser_mode_enabled": getattr(settings, "IRENE_ADVISER_MODE_ENABLED", False),
    }

    # Auto-open preference (M010-UX-CUSTOMER-JOURNEYS.md §1: "one
    # auto-open per new browser/login session, persists dismiss
    # preference") - reuses foundations_journey's own M010B
    # UserJourneyPreference model, per this package's PID §1 ("reuse
    # UserJourneyPreference ... rather than inventing a second preference
    # model"), plus a per-SESSION (not per-preference) flag so a session
    # that has already auto-opened once does not reopen on every
    # subsequent Home navigation even while the stored preference stays
    # on.
    auto_open = _resolve_auto_open(request, user)

    # Stage 3 tab (WO-IRENE-001 Increment 2 browser-wiring, Central
    # Architecture requirement 1: "presented and answered inside the
    # existing IRENE modal") - additive 5th tab, `None` (tab omitted
    # entirely, same convention `build_modal_context` itself already uses
    # for the whole modal above) for any session that fails Stage 3's own
    # composed `check_stage3_access` gate (Amendment D1) or when the
    # section is not currently registered. Every one of the four tabs
    # above is built identically regardless of this outcome.
    stage3_tab = None
    try:
        stage3_organisation = check_stage3_access(request, organisation.id)
    except (Stage3AccessDenied, Http404):
        stage3_tab = None
    else:
        try:
            stage3_tab = _build_stage3_tab_context(request, stage3_organisation)
        except UnregisteredSectionError:
            stage3_tab = None

    return ModalContext(
        irene_enabled=True,
        auto_open=auto_open,
        continue_tab=continue_tab,
        tasks_tab=tasks_tab,
        activity_tab=activity_tab,
        ask_tab=ask_tab,
        stage3_tab=stage3_tab,
    )


_SESSION_AUTO_OPENED_KEY = "irene_auto_opened_this_session"


def _resolve_auto_open(request, user) -> bool:
    from foundations_journey.models import UserJourneyPreference

    if request.session.get(_SESSION_AUTO_OPENED_KEY):
        return False
    preference = UserJourneyPreference.objects.filter(user=user).first()
    enabled = preference.auto_open_enabled if preference is not None else True
    if enabled:
        request.session[_SESSION_AUTO_OPENED_KEY] = True
    return enabled


def _stage3_field_names_for_definition(question) -> tuple:
    """The real `OrganisationProfile` field name(s) one registered Stage 3
    question's own answer is stored under, for a RAW
    `irene.question_engine.contract.QuestionDefinition` (as found in
    `section.questions` - e.g. what `_stage3_question_by_code` returns) -
    `(question.question_code,)` for `single_choice` (the Stage 3 adapter's
    own documented convention: every single-choice `question_code` IS the
    real field name) or every sub-field's own `field_code`, read off this
    question's own `fields` tuple, for `grouped_independent_answer`. Empty
    for `delegated_workflow` (3.7/Key Assets - nothing is saved here;
    `irene.question_engine.adapters.stage3_technology_data.
    KEY_ASSETS_QUESTION_CODE` only ever renders a link out).

    Deliberately a SEPARATE function from
    `_stage3_field_names_for_rendered` below: a raw `QuestionDefinition`'s
    grouped sub-fields live under its own `.fields` attribute (`tuple[
    GroupedAnswerField, ...]`), never the presenter's own, differently-
    named `.grouped_fields` (`tuple[RenderedGroupedField, ...]`) a
    `RenderedQuestion` carries - conflating the two raised a real
    `AttributeError` here before this fix (caught by this package's own
    `test_grouped_question_saves_every_sibling_field_together`)."""
    if question.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE:
        return (question.question_code,)
    if question.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER:
        return tuple(field.field_code for field in question.fields)
    return ()


def _stage3_field_names_for_rendered(question) -> tuple:
    """The same field-name resolution as
    `_stage3_field_names_for_definition` above, but for a presenter-
    produced `irene.question_engine.presenter.RenderedQuestion` (as found
    in `rendered.questions` - what `_build_stage3_tab_context` iterates) -
    reads `.grouped_fields` (`tuple[RenderedGroupedField, ...]`), never
    the raw definition's own, differently-named `.fields`."""
    if question.capability_type == CAPABILITY_TYPE_SINGLE_CHOICE:
        return (question.question_code,)
    if question.capability_type == CAPABILITY_TYPE_GROUPED_INDEPENDENT_ANSWER:
        return tuple(field.field_code for field in question.grouped_fields)
    return ()


def _stage3_question_by_code(section, question_code):
    for question in section.questions:
        if question.question_code == question_code:
            return question
    return None


def _build_stage3_tab_context(request, organisation) -> dict:
    """Shared by `build_modal_context`'s additive Stage 3 tab AND the
    standalone `stage3_panel` view below - ONE place calls
    `irene.question_engine.presenter.render_section` for the real,
    registered Stage 3 section and attaches the per-question extras
    (the save-guard's own `expected_state_token`, the Key Assets
    delegated-workflow link, and any just-posted "Explain this" result)
    a template needs - never a second, divergent copy of this
    assembly. Callers are responsible for having already proven access
    via `check_stage3_access`/`_require_stage3_access` - this function
    performs no authorisation check of its own."""
    from django.urls import NoReverseMatch, reverse

    from irene.product_knowledge import get_concept
    from organisations.models import OrganisationProfile
    from organisations.services import compute_stage3_expected_state_token

    section = get_section(STAGE3_SECTION_CODE)
    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    rendered = render_section(section, answered_values_for_profile(profile))

    # Read-once flash (see STAGE3_EXPLANATION_SESSION_KEY's own comment) -
    # popped here so a later, unrelated render of this same tab never
    # re-shows a stale explanation.
    pending_explanation = request.session.pop(STAGE3_EXPLANATION_SESSION_KEY, None)

    questions = []
    for question in rendered.questions:
        field_names = _stage3_field_names_for_rendered(question)
        expected_state_token = (
            compute_stage3_expected_state_token(organisation, field_names) if field_names else ""
        )

        key_assets_url = ""
        if question.capability_type == CAPABILITY_TYPE_DELEGATED_WORKFLOW:
            concept = get_concept(question.delegated_route_concept_id)
            if concept is not None:
                try:
                    key_assets_url = reverse(concept.route_name, kwargs={"organisation_id": organisation.id})
                except NoReverseMatch:
                    key_assets_url = ""

        explanation = None
        if pending_explanation and pending_explanation.get("question_code") == question.question_code:
            explanation = pending_explanation

        questions.append(
            {
                "rendered": question,
                "expected_state_token": expected_state_token,
                "key_assets_url": key_assets_url,
                "explanation": explanation,
            }
        )

    return {"section": rendered, "questions": questions}


def _require_stage3_access(request, organisation_id):
    """Maps `Stage3AccessDenied` (a real member, missing capability) onto
    the ordinary `django.core.exceptions.PermissionDenied` every other
    insufficient-tier route in this codebase already raises (Django's own
    branded 403) - `check_stage3_access` itself already raises a plain
    `Http404` for a non-member via `get_member_organisation_or_404`, left
    to propagate unchanged. One shared helper so all three new Stage 3
    views below enforce the identical composed tenant+capability gate
    (Central Architecture requirement 2) - never three independently
    re-derived checks."""
    try:
        return check_stage3_access(request, organisation_id)
    except Stage3AccessDenied as exc:
        raise PermissionDenied(str(exc)) from exc


@login_required
@require_capability()
def workspace(request, organisation_id):
    """Direct-URL-enforcement destination for the `irene` ProductArea row
    (M010C PID §1: "wire the modal open action to it... give that row's
    destination_view_name a real meaning"). Independently gated on the
    `irene` capability (via `entitlements.capabilities.
    ROUTE_NAMESPACE_TO_CAPABILITY["irene"]`) - a session without it gets
    the ordinary 403 `require_capability()` already gives, proving this
    is real access control, not merely a redirect. Once past that gate,
    redirects to Home with `?irene=open` - the modal itself is always
    rendered as PART of Home (see `build_modal_context`'s own docstring
    for why there is no separate full "IRENE page" template to maintain
    in parallel with Home's)."""
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    return redirect(f"{reverse('organisations:detail', args=[organisation.id])}?irene=open")


@login_required
@require_capability()
def ask(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(request.user, organisation_id)

    form = AskForm(request.POST)
    if form.is_valid():
        conversation = conversation_services.get_or_create_active_conversation(organisation, request.user)
        context = irene_tools.build_authorized_context(request, organisation)
        response = orchestration.ask_irene(
            context,
            organisation,
            request.user,
            conversation_id=conversation.id,
            intent_code=form.cleaned_data["intent_code"],
            user_message=form.cleaned_data["message"],
        )
        orchestration.materialize_proposed_actions(context, response)
    else:
        messages.error(request, "Your message could not be sent - please check it and try again.")

    return redirect(f"{reverse('organisations:detail', args=[organisation.id])}?irene=open&irene_tab=ask")


@login_required
@require_capability()
def confirm_task(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(request.user, organisation_id)

    form = ConfirmTaskForm(request.POST)
    if form.is_valid():
        context = irene_tools.build_authorized_context(request, organisation)
        try:
            task_preview = irene_tools.confirm_task_creation(context, action_id=form.cleaned_data["action_id"])
        except ActionProposalExpiredError:
            messages.error(request, "This proposal is no longer available to confirm.")
        else:
            messages.success(request, f'Task "{task_preview["title"]}" created.')
    else:
        messages.error(request, "That confirmation could not be processed.")

    return redirect(f"{reverse('organisations:detail', args=[organisation.id])}?irene=open&irene_tab=ask")


@login_required
@require_capability("customer_assurance")
def assurance_status(request, organisation_id):
    """M010E PID §3 - the Monthly/PRO-gated Customer Assurance status
    page. Deliberately gated on the EXPLICIT "customer_assurance"
    capability (never the "irene" default `require_capability()` would
    otherwise resolve for this `irene` namespace route) - a Foundational-
    tier member hitting this URL directly, not through any link IRENE
    would ever render for them, gets the ordinary, generic 403
    `require_capability` already gives every other insufficient-tier
    route in this codebase (PermissionDenied -> Django's own branded
    403.html, carrying no message) - proving this gate is real access
    control, not merely an absent link.

    Reuses `irene.tools.get_customer_assurance_status` - the SAME tool
    the Ask tab would call for this organisation - so this page and
    anything IRENE says in conversation can never disagree about whether
    the organisation is ready/entitled or what its real import rows are.
    That tool independently re-proves BOTH the tier-2 entitlement and the
    100% readiness gate on every call (see its own docstring) - this view
    adds no readiness/entitlement check of its own beyond the
    `require_capability("customer_assurance")` decorator above, exactly
    the same "pipeline-level hook, never a view-level-only reimplementation"
    discipline `questionnaire.upload_handler` already established for the
    real upload view."""
    from organisations.views import get_member_organisation_or_404

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    context = irene_tools.build_authorized_context(request, organisation)
    status = irene_tools.get_customer_assurance_status(context)
    return render(
        request,
        "irene/assurance_status.html",
        {"organisation": organisation, "status": status},
    )


@login_required
@require_capability()
def set_auto_open_preference(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from organisations.views import get_member_organisation_or_404

    from foundations_journey.models import UserJourneyPreference

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    enabled = request.POST.get("auto_open_enabled") == "on"
    UserJourneyPreference.objects.update_or_create(
        user=request.user, defaults={"auto_open_enabled": enabled}
    )
    messages.success(request, "Your IRENE preference has been updated.")
    return redirect(reverse("organisations:detail", args=[organisation.id]))


# ---------------------------------------------------------------------------
# WO-IRENE-001 Increment 2 (browser-wiring) - Stage 3 question-engine
# wiring. Three new, additive views; none of them touch `ask_irene`,
# `_modal.html`/`modal.js`'s existing Ask-tab markup/behaviour, or
# `organisations.views.organisation_stage3_technology_data`/its template
# in any way (Central Architecture requirement 5). Each independently
# calls `_require_stage3_access` (composed tenant+capability gate,
# requirement 2) as its own first action - never
# `@require_capability()`, which resolves a single capability from the
# route's own namespace and cannot express Stage 3's composed
# `irene`+`foundations` check (see `irene.question_engine.adapters.
# stage3_technology_data.check_stage3_access`'s own docstring for why).
# ---------------------------------------------------------------------------


@login_required
def stage3_panel(request, organisation_id):
    """Standalone, independently-gated destination for the real,
    registered Stage 3 section (Central Architecture requirement 1/2).
    Shares its entire rendering assembly with `build_modal_context`'s own
    additive Stage 3 tab via `_build_stage3_tab_context` - never a second,
    divergent render path. A direct GET here is also what the IRENE
    modal's new Stage 3 tab button itself needs no separate copy of: the
    tab's own content is pre-rendered as part of Home (no AJAX, ADR-0001,
    same as every other tab) by that same shared helper."""
    organisation = _require_stage3_access(request, organisation_id)
    stage3 = _build_stage3_tab_context(request, organisation)
    return render(
        request,
        "irene/stage3_panel.html",
        {"organisation": organisation, "stage3": stage3},
    )


def _stage3_redirect_to_modal(organisation_id):
    return redirect(f"{reverse('organisations:detail', args=[organisation_id])}?irene=open&irene_tab=stage3")


@login_required
def stage3_save(request, organisation_id):
    """Guarded Stage 3 answer save (Central Architecture requirement 3) -
    enforces `_require_stage3_access` first, then calls ONLY
    `organisations.services.save_stage3_fields` (the audited guarded
    adapter) - never a direct `OrganisationProfile.save()`.
    `StaleCanonicalStateError`/`CanonicalValidationError` are both real,
    expected outcomes a genuine user submission can hit and are handled
    here as ordinary, user-visible, non-crashing redirects with a flash
    message - never an unhandled 500."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    from organisations.services import (
        CanonicalValidationError,
        StaleCanonicalStateError,
        UnknownStage3FieldError,
        save_stage3_fields,
    )

    organisation = _require_stage3_access(request, organisation_id)

    try:
        section = get_section(STAGE3_SECTION_CODE)
    except UnregisteredSectionError:
        raise Http404("Stage 3 is not currently available.")

    question_code = request.POST.get("question_code", "")
    question = _stage3_question_by_code(section, question_code)
    if question is None:
        raise Http404("Unknown Stage 3 question.")

    field_names = _stage3_field_names_for_definition(question)
    if not field_names:
        # delegated_workflow (3.7/Key Assets) - nothing is ever saved
        # through this endpoint; Key Assets' own app owns that write path
        # entirely (Amendment D3's "link out, come back", never a
        # duplicate inline editor).
        messages.error(request, "That item cannot be saved here.")
        return _stage3_redirect_to_modal(organisation.id)

    field_values = {name: request.POST.get(name, "") for name in field_names}
    expected_state_token = request.POST.get("expected_state_token", "")

    try:
        save_stage3_fields(
            organisation=organisation,
            field_values=field_values,
            expected_state_token=expected_state_token,
            catalogue_version=section.catalogue_version,
            interaction_contract_version=section.interaction_contract_version,
            actor=request.user,
        )
    except StaleCanonicalStateError:
        messages.error(
            request,
            "Someone else updated this answer while you were viewing it. Please review and save again.",
        )
    except CanonicalValidationError:
        messages.error(request, "That answer could not be saved. Please check it and try again.")
    except UnknownStage3FieldError:
        raise Http404("Unknown Stage 3 field.")
    else:
        messages.success(request, "Saved.")

    return _stage3_redirect_to_modal(organisation.id)


@login_required
def stage3_explain(request, organisation_id):
    """"Explain this" for a Stage 3 question (Central Architecture
    requirement 4) - enforces `_require_stage3_access` first, then
    `resolve_stage3_explanation` (Increment 2 core's typed
    context+skill-only dispatch - no gateway call inside that adapter
    module), then THIS increment's new, additive
    `irene.question_engine.stage3_orchestration.ask_irene_stage3_explain`
    (the real `ask_adviser` call site, or the safe fallback when Adviser
    Mode is off/unavailable/fails - requirement 6). The result is handed
    back to the modal via a read-once session flash + redirect (the same
    post/redirect/get, no-AJAX convention `ask`/`confirm_task` above
    already use) - never a 500 for a question this feature cannot
    explain (3.7/Key Assets)."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    from organisations.models import OrganisationProfile

    organisation = _require_stage3_access(request, organisation_id)

    try:
        section = get_section(STAGE3_SECTION_CODE)
    except UnregisteredSectionError:
        raise Http404("Stage 3 is not currently available.")

    question_code = request.POST.get("question_code", "")
    question = _stage3_question_by_code(section, question_code)
    if question is None:
        raise Http404("Unknown Stage 3 question.")

    profile = OrganisationProfile.objects.filter(organisation=organisation).first()
    answered_values = answered_values_for_profile(profile)

    try:
        dispatch = resolve_stage3_explanation(
            organisation=organisation,
            question=question,
            answered_values=answered_values,
            field_code=None,
        )
    except ValueError:
        # delegated_workflow (3.7/Key Assets) has no typed explanation
        # context at all (Stage3QuestionExplanationContext only covers
        # 3.1-3.6) - nothing to explain, never a 500.
        messages.error(request, "This item cannot be explained here.")
        return _stage3_redirect_to_modal(organisation.id)

    response = ask_irene_stage3_explain(organisation=organisation, user=request.user, dispatch=dispatch)
    request.session[STAGE3_EXPLANATION_SESSION_KEY] = {
        "question_code": question_code,
        "message": response.message,
    }
    return _stage3_redirect_to_modal(organisation.id)
