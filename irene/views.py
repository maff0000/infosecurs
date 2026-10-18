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
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from entitlements.decorators import require_capability
from irene import orchestration
from irene import services as conversation_services
from irene import tools as irene_tools
from irene.exceptions import ActionProposalExpiredError
from irene.forms import AskForm, ConfirmTaskForm
from irene.models import ActionDecisionState, AssistantAction

# M010C PID §2 ("Task List available without modal via sidebar") - bounded
# fragment sizes, never the full paginated page a dedicated sidebar visit
# would show.
MODAL_TASK_LIST_SIZE = 5
MODAL_ACTIVITY_LIST_SIZE = 8


@dataclasses.dataclass(frozen=True)
class ModalContext:
    irene_enabled: bool
    auto_open: bool
    continue_tab: dict
    tasks_tab: dict
    activity_tab: dict
    ask_tab: dict


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

    return ModalContext(
        irene_enabled=True,
        auto_open=auto_open,
        continue_tab=continue_tab,
        tasks_tab=tasks_tab,
        activity_tab=activity_tab,
        ask_tab=ask_tab,
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
