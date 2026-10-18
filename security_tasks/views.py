"""
Tasks sidebar page + detail view (M010A PID §1/§2). Thin views: every
mutation goes through `security_tasks.services`, never touches
`SecurityTask.objects` directly for a write. Every view follows this
codebase's exact established convention
(`@login_required` + `@require_capability()` + `get_member_organisation_or_404`
as the view's own first action - see `risk_register/views.py`,
`security_baseline/views.py`): a non-member gets the same ordinary 404
every other organisation-scoped route in this codebase already gives.
"""
from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect, render

from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404

from security_tasks import services
from security_tasks.exceptions import (
    ConcurrentModificationError,
    DependencyBlockedError,
    DependencyCrossOrganisationError,
    DependencyCycleError,
    DependencySelfReferenceError,
    DuplicateDependencyError,
    ForeignAssigneeError,
    InvalidTransitionError,
)
from security_tasks.forms import (
    TaskAssignForm,
    TaskCreateForm,
    TaskDependencyForm,
    TaskFilterForm,
    TaskTransitionForm,
)
from security_tasks.models import SecurityTask, SourceOrigin, TaskKind
from security_tasks.source_registry import SOURCE_KIND_NONE


@login_required
@require_capability()
def task_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    filter_form = TaskFilterForm(request.GET or None, organisation=organisation)
    filters = {}
    if filter_form.is_valid():
        filters = {
            "group": filter_form.cleaned_data.get("group") or None,
            "status": filter_form.cleaned_data.get("status") or None,
            "assignee_id": filter_form.cleaned_data.get("assignee") or None,
            "due_filter": filter_form.cleaned_data.get("due") or None,
            "search": filter_form.cleaned_data.get("q") or None,
        }

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    task_page = services.get_task_list(organisation, page=page_number, **filters)
    # M010D PID §4 / M010-MASTER-ARCHITECTURE.md §6 "no independent LLM
    # scheduler judgement" - read-only, zero-AI counts derived through
    # get_task_list's own existing filters (see that function's docstring).
    review_briefing = services.get_review_briefing_counts(organisation)

    return render(
        request,
        "security_tasks/list.html",
        {
            "organisation": organisation,
            "filter_form": filter_form,
            "task_page": task_page,
            "review_briefing": review_briefing,
        },
    )


def _get_member_task_detail_or_404(user, organisation_id, task_id):
    organisation = get_member_organisation_or_404(user, organisation_id)
    detail = services.get_task_detail(organisation, task_id)
    if detail is None:
        raise Http404("Task not found.")
    return organisation, detail


@login_required
@require_capability()
def task_detail(request, organisation_id, task_id):
    organisation, detail = _get_member_task_detail_or_404(request.user, organisation_id, task_id)
    transition_form = TaskTransitionForm(initial={"expected_version": detail.task.version})
    assign_form = TaskAssignForm(organisation=organisation, initial={"expected_version": detail.task.version})
    dependency_form = TaskDependencyForm(organisation=organisation, current_task=detail.task)
    return render(
        request,
        "security_tasks/detail.html",
        {
            "organisation": organisation,
            "detail": detail,
            "task": detail.task,
            "transition_form": transition_form,
            "assign_form": assign_form,
            "dependency_form": dependency_form,
        },
    )


@login_required
@require_capability()
def task_create(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = TaskCreateForm(request.POST, organisation=organisation)
        if form.is_valid():
            try:
                task = services.create_task(
                    organisation,
                    actor=request.user,
                    kind=TaskKind.MANUAL_OTHER,
                    title=form.cleaned_data["title"],
                    summary=form.cleaned_data.get("summary", ""),
                    idempotency_key=form.cleaned_data["idempotency_key"],
                    source_origin=SourceOrigin.HUMAN,
                    source_kind=SOURCE_KIND_NONE,
                    due_at=form.cleaned_data.get("due_at"),
                    assignee_id=form.cleaned_data.get("assignee") or None,
                    priority=form.cleaned_data.get("priority") or None,
                )
            except ForeignAssigneeError:
                messages.error(request, "That assignee is not a current member of this organisation.")
            else:
                messages.success(request, f'Task "{task.title}" created.')
                return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task.id)
        else:
            messages.error(request, "The task could not be created. Please check the errors below.")
    else:
        form = TaskCreateForm(organisation=organisation, initial={"idempotency_key": str(uuid.uuid4())})

    return render(request, "security_tasks/form.html", {"organisation": organisation, "form": form})


@login_required
@require_capability()
def task_transition(request, organisation_id, task_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, detail = _get_member_task_detail_or_404(request.user, organisation_id, task_id)

    form = TaskTransitionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "That transition could not be applied. Please check the errors below.")
        return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)

    try:
        services.transition_task(
            organisation,
            actor=request.user,
            task_id=task_id,
            expected_version=form.cleaned_data["expected_version"],
            next_status=form.cleaned_data["next_status"],
            reason=form.cleaned_data["reason"],
            override_blocked=form.cleaned_data.get("override_blocked", False),
        )
    except ConcurrentModificationError:
        messages.error(request, "This task changed since you loaded the page. Please review and try again.")
    except InvalidTransitionError:
        messages.error(request, "That status change is not allowed from the task's current status.")
    except DependencyBlockedError:
        messages.error(request, "This task is blocked by another task that is not yet done or cancelled.")
    else:
        messages.success(request, "Task status updated.")
    return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)


@login_required
@require_capability()
def task_assign(request, organisation_id, task_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation = get_member_organisation_or_404(request.user, organisation_id)

    form = TaskAssignForm(request.POST, organisation=organisation)
    if not form.is_valid():
        messages.error(request, "That assignment could not be applied.")
        return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)

    try:
        services.assign_task(
            organisation,
            actor=request.user,
            task_id=task_id,
            expected_version=form.cleaned_data["expected_version"],
            assignee_id=form.cleaned_data.get("assignee") or None,
        )
    except SecurityTask.DoesNotExist:
        raise Http404("Task not found.")
    except ConcurrentModificationError:
        messages.error(request, "This task changed since you loaded the page. Please review and try again.")
    except ForeignAssigneeError:
        messages.error(request, "That assignee is not a current member of this organisation.")
    else:
        messages.success(request, "Task assignment updated.")
    return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)


@login_required
@require_capability()
def task_link_dependency(request, organisation_id, task_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, detail = _get_member_task_detail_or_404(request.user, organisation_id, task_id)

    form = TaskDependencyForm(request.POST, organisation=organisation, current_task=detail.task)
    if not form.is_valid():
        messages.error(request, "Please choose a valid task to depend on.")
        return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)

    try:
        services.link_task_dependency(
            organisation,
            actor=request.user,
            predecessor_id=form.cleaned_data["predecessor"],
            successor_id=str(task_id),
        )
    except DependencySelfReferenceError:
        messages.error(request, "A task cannot depend on itself.")
    except DependencyCrossOrganisationError:
        messages.error(request, "That task could not be found.")
    except DuplicateDependencyError:
        messages.error(request, "That dependency already exists.")
    except DependencyCycleError:
        messages.error(request, "That dependency would create a cycle and cannot be added.")
    else:
        messages.success(request, "Dependency added.")
    return redirect("security_tasks:detail", organisation_id=organisation.id, task_id=task_id)
