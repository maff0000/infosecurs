"""
Policy lifecycle views (M004 PID §3.9-19 - m004-2a-policy-foundation +
m004-2b-policy-lifecycle dispatches): draft generation/read-only view
(2a), plus the section-based editor, the direct/external approval flow,
new-draft-from-approved, and the approved-artefact PDF download (2b).
"""
from __future__ import annotations

from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.views import get_member_organisation_or_404

from activity.models import ActivityEvent
from activity.services import record_event
from ai_platform.policy_orchestration import PolicyGenerationFailed

from policy.forms import PolicyApprovalConfirmForm, PolicyVersionEditForm, section_field_name
from policy.models import PolicyVersion
from policy.pdf import render_policy_pdf
from policy.presentation import approval_summary
from policy.services import (
    PolicyLifecycleError,
    approve_policy_directly,
    compute_current_review_warnings,
    create_new_draft_from_approved,
    default_next_review_date,
    generate_policy_draft,
    get_policy_authoriser,
    record_external_policy_approval,
)


def _get_member_policy_version_or_404(user, organisation_id, version_id):
    """
    Tenant-scoped policy-version fetch, mirroring
    `organisations.views.get_member_organisation_or_404` /
    `risk_register.views._get_member_risk_or_404`: membership is verified
    first, then the version is looked up scoped to that organisation - a
    foreign/manipulated version id in the URL is an ordinary 404, never a
    path to another organisation's policy (PID §23, §26 tenant isolation).
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    version = get_object_or_404(PolicyVersion, id=version_id, organisation=organisation)
    return organisation, version


def _approval_eligibility(organisation, user):
    """
    Returns `(authoriser_person_or_None, can_approve_directly, can_record_external)`
    for `user` acting on `organisation` right now (PID §17, ADR-0002 §4.1).
    Used by both the version-detail template (to decide which approval
    button, if any, to show) and as the same eligibility question the
    approve views themselves re-check before accepting a POST - never
    trusted from the template/URL alone.
    """
    authoriser = get_policy_authoriser(organisation)
    if authoriser is None:
        return None, False, False
    is_direct = authoriser.user_id is not None and authoriser.user_id == user.id
    return authoriser, is_direct, not is_direct


@login_required
def policy_detail(request, organisation_id):
    """Organisation-level policy overview: the most recent `PolicyVersion`
    (if any) shown in full, plus a list of every version for history/
    navigation (PID §15 "later create a new draft/version" implies more
    than one version can exist; old approved versions must stay reachable,
    PID §19)."""
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    versions = list(
        PolicyVersion.objects.filter(organisation=organisation).order_by("-version_number")
    )
    latest_version = versions[0] if versions else None
    return render(
        request,
        "policy/detail.html",
        {
            "organisation": organisation,
            "version": latest_version,
            "versions": versions,
            "approval_summary": approval_summary(latest_version) if latest_version else None,
        },
    )


@login_required
def policy_generate(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    try:
        generate_policy_draft(organisation, actor=request.user)
    except PolicyGenerationFailed:
        # PID §14 / policy.services module docstring point 5: a failed call
        # creates nothing - never surface the raw exception (a
        # GatewayError message, safe but internal/technical) directly to
        # the end user.
        messages.error(
            request,
            "AI policy generation could not be completed right now, so "
            "nothing was created. You can try again later.",
        )
        return redirect("policy:detail", organisation_id=organisation.id)

    messages.success(request, "A new draft Information Security Policy has been generated.")
    return redirect("policy:detail", organisation_id=organisation.id)


@login_required
def policy_version_detail(request, organisation_id, version_id):
    """One specific `PolicyVersion`'s full content, plus the actions
    available to this user for this version's current status (edit/
    approve-direct/approve-external/new-draft/download)."""
    organisation, version = _get_member_policy_version_or_404(
        request.user, organisation_id, version_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    authoriser, can_approve_directly, can_record_external = _approval_eligibility(
        organisation, request.user
    )
    return render(
        request,
        "policy/version_detail.html",
        {
            "organisation": organisation,
            "version": version,
            "policy_authoriser": authoriser,
            "can_approve_directly": can_approve_directly,
            "can_record_external": can_record_external,
            "approval_summary": approval_summary(version)
            if version.status in (PolicyVersion.STATUS_APPROVED, PolicyVersion.STATUS_SUPERSEDED)
            else None,
        },
    )


@login_required
def policy_edit(request, organisation_id, version_id):
    """
    Section-based draft editor (PID §16). Only a `status=draft` version may
    be edited - gated here at the view layer for a clear user-facing
    redirect/message (the model's `ImmutablePolicyVersionError` remains the
    defence-in-depth backstop if this check is ever bypassed - see
    `policy/tests/test_edit.py` for an HTTP-level proof of both layers).
    """
    organisation, version = _get_member_policy_version_or_404(
        request.user, organisation_id, version_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    if version.status != PolicyVersion.STATUS_DRAFT:
        messages.error(request, "Only a draft policy version can be edited.")
        return redirect(
            "policy:version_detail", organisation_id=organisation.id, version_id=version.id
        )

    # Only the sections this version actually contains are editable here
    # (PolicyVersionEditForm's own docstring: a content editor, not a
    # section add/remove tool), already reduced to ALLOWED_SECTION_KEYS
    # order by the form itself.
    editable_section_keys = [entry["section_key"] for entry in version.sections]

    if request.method == "POST":
        form = PolicyVersionEditForm(request.POST, section_keys=editable_section_keys)

        # Snapshot every "previous" value needed for the Learning Signal
        # Capture delta from `version` RIGHT NOW, before this form's
        # cleaned_data is ever read or applied - see PolicyVersionEditForm's
        # own docstring for why this form structurally cannot mutate
        # `version` as a side effect of is_valid() (it is not a ModelForm
        # bound to an instance), and why this snapshot-first discipline is
        # still applied anyway, matching risk_register.views.risk_edit's
        # comment on the same lesson.
        previous_title = version.title
        previous_next_review_date = version.next_review_date
        previous_section_content = {
            entry["section_key"]: entry["content"] for entry in version.sections
        }

        if form.is_valid():
            new_title = form.cleaned_data["title"]
            new_next_review_date = form.cleaned_data.get("next_review_date")

            new_sections = []
            changed_sections = []
            for entry in version.sections:
                key = entry["section_key"]
                if key in form.section_keys:
                    new_content = form.cleaned_data[section_field_name(key)]
                else:
                    new_content = entry["content"]
                if new_content != previous_section_content.get(key):
                    changed_sections.append(key)
                new_sections.append({"section_key": key, "content": new_content})

            title_changed = new_title != previous_title
            next_review_date_changed = new_next_review_date != previous_next_review_date

            if changed_sections or title_changed or next_review_date_changed:
                with transaction.atomic():
                    version.title = new_title
                    version.next_review_date = new_next_review_date
                    version.sections = new_sections
                    version.save(
                        update_fields=["title", "next_review_date", "sections", "updated_at"]
                    )
                    # Metadata is the changed-fields delta ONLY (PID §16:
                    # "activity events need not duplicate large policy
                    # text") - never the section content itself.
                    record_event(
                        organisation,
                        ActivityEvent.EVENT_POLICY_DRAFT_EDITED,
                        actor=request.user,
                        related_object_type="policy_version",
                        related_object_id=str(version.id),
                        metadata={
                            "changed_sections": changed_sections,
                            "title_changed": title_changed,
                            "next_review_date_changed": next_review_date_changed,
                        },
                    )
                messages.success(request, "Draft policy updated.")
            else:
                messages.success(request, "No changes were made.")
            return redirect(
                "policy:version_detail", organisation_id=organisation.id, version_id=version.id
            )
        messages.error(request, "The draft could not be saved. Please check the errors below.")
    else:
        initial = {"title": version.title, "next_review_date": version.next_review_date}
        for entry in version.sections:
            if entry["section_key"] in editable_section_keys:
                initial[section_field_name(entry["section_key"])] = entry["content"]
        form = PolicyVersionEditForm(initial=initial, section_keys=editable_section_keys)

    # H3 correction (M006-AUDIT-0003): editing policy prose must never
    # itself be a source of review warnings (canonical security state
    # remains the sole authority - see `policy.services` module docstring),
    # and this POST path above deliberately never touches
    # `version.review_warnings` at all. This GET-time preview mirrors the
    # approval-confirmation page's own preview (`compute_current_review_warnings`)
    # purely so the customer editing a draft sees live-current warnings
    # here too, not a stale edit-time/generation-time snapshot - the
    # eventual approved version's own warnings are still guaranteed correct
    # independently by `_finalise_approval`'s own recompute regardless of
    # what is shown here.
    current_review_warnings = compute_current_review_warnings(version)

    return render(
        request,
        "policy/edit.html",
        {
            "organisation": organisation,
            "version": version,
            "form": form,
            "current_review_warnings": current_review_warnings,
        },
    )


def _approve(request, organisation_id, version_id, *, mode):
    """
    Shared GET/POST handling for the two approval actions - `mode` is
    `"direct"` or `"external"`. Deliberately still two distinct URL
    names/view functions below (`policy_approve_direct`/
    `policy_approve_external`) so nothing in the URL layer or a template's
    `{% url %}` call can accidentally point at "the approval view" without
    saying which kind - this helper only removes the duplicated
    GET/POST/redirect plumbing, never the mode distinction itself (ADR-0002
    §4.1: "never silently fall back... never let a UI label imply...").
    """
    organisation, version = _get_member_policy_version_or_404(
        request.user, organisation_id, version_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    if version.status != PolicyVersion.STATUS_DRAFT:
        messages.error(request, "Only a draft policy version can be approved.")
        return redirect(
            "policy:version_detail", organisation_id=organisation.id, version_id=version.id
        )

    authoriser, can_approve_directly, can_record_external = _approval_eligibility(
        organisation, request.user
    )
    eligible = can_approve_directly if mode == "direct" else can_record_external
    if not eligible:
        if authoriser is None:
            messages.error(
                request,
                "No Policy Authoriser is currently assigned for this organisation. "
                "Assign one in Governance before approving.",
            )
        elif mode == "direct":
            messages.error(
                request,
                "You are not the assigned Policy Authoriser, so you cannot approve this "
                "policy directly.",
            )
        else:
            messages.error(
                request,
                "The assigned Policy Authoriser is you - use direct approval instead of "
                "recording an external approval.",
            )
        return redirect(
            "policy:version_detail", organisation_id=organisation.id, version_id=version.id
        )

    if request.method == "POST":
        form = PolicyApprovalConfirmForm(request.POST)
        if form.is_valid():
            next_review_date = form.cleaned_data["next_review_date"]
            try:
                if mode == "direct":
                    approve_policy_directly(
                        version, actor=request.user, next_review_date=next_review_date
                    )
                    messages.success(
                        request, f'"{version.title}" approved directly by {authoriser.full_name}.'
                    )
                else:
                    record_external_policy_approval(
                        version, actor=request.user, next_review_date=next_review_date
                    )
                    messages.success(
                        request,
                        f'External approval by {authoriser.full_name} recorded for '
                        f'"{version.title}".',
                    )
            except PolicyLifecycleError as exc:
                messages.error(request, str(exc))
            return redirect(
                "policy:version_detail", organisation_id=organisation.id, version_id=version.id
            )
        messages.error(request, "Approval could not be recorded. Please check the errors below.")
    else:
        form = PolicyApprovalConfirmForm(
            initial={"next_review_date": version.next_review_date or default_next_review_date()}
        )

    # H3 correction (M006-AUDIT-0003): a freshly-derived, NOT-YET-PERSISTED
    # preview of what `review_warnings` would be recomputed to right now -
    # the exact same `compute_current_review_warnings` call
    # `policy.services._finalise_approval` itself uses at the actual
    # approval-write freeze point, so what the customer sees here on this
    # confirmation page is exactly what gets persisted if they confirm.
    # Deliberately a pure read (no DB mutation on this GET) - Central
    # Architecture's own stated preference for a derived-display approach
    # over a GET-time write.
    current_review_warnings = compute_current_review_warnings(version)

    return render(
        request,
        "policy/approve.html",
        {
            "organisation": organisation,
            "version": version,
            "form": form,
            "mode": mode,
            "policy_authoriser": authoriser,
            "current_review_warnings": current_review_warnings,
        },
    )


@login_required
def policy_approve_direct(request, organisation_id, version_id):
    """PID §17.1 - Account Holder is also the assigned Policy Authoriser."""
    return _approve(request, organisation_id, version_id, mode="direct")


@login_required
def policy_approve_external(request, organisation_id, version_id):
    """PID §17.2 - a different named Policy Authoriser; the Account Holder
    records that approval was obtained externally."""
    return _approve(request, organisation_id, version_id, mode="external")


@login_required
def policy_new_draft(request, organisation_id, version_id):
    """PID §15 - the only way to "edit" an approved policy's content: copy
    it into a brand new draft version, leaving the approved version
    untouched."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation, version = _get_member_policy_version_or_404(
        request.user, organisation_id, version_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    if version.status != PolicyVersion.STATUS_APPROVED:
        messages.error(
            request,
            "A new draft can only be created from the currently approved policy version.",
        )
        return redirect(
            "policy:version_detail", organisation_id=organisation.id, version_id=version.id
        )

    new_version = create_new_draft_from_approved(version, actor=request.user)
    messages.success(
        request, f"A new draft (version {new_version.version_number}) was created for editing."
    )
    return redirect(
        "policy:version_edit", organisation_id=organisation.id, version_id=new_version.id
    )


@login_required
def policy_download(request, organisation_id, version_id):
    """
    Private, authenticated, tenant-scoped approved-artefact download (PID
    §19), mirroring `evidence.views.evidence_download`'s response-header
    discipline exactly (safe ASCII-fallback + UTF-8 `filename*`,
    `X-Content-Type-Options: nosniff`).

    Only `approved` or `superseded` versions may be downloaded - PID §15/
    §19: supersession must not remove historical downloadability, so a
    superseded (not just the current approved) version stays reachable
    here. A `draft` version has never been approved and is not yet a
    stable artefact - `Http404`, matching this codebase's "an
    inaccessible/inapplicable object is an ordinary 404, not a 403"
    convention used throughout (see `evidence_download`'s own `kind`
    check).

    `render_policy_pdf` is handed this exact, already-tenant-scoped
    `version` object plus `organisation` - see that module's own docstring
    for why there is no live-state lookup possible here at all (PID §19).
    """
    organisation, version = _get_member_policy_version_or_404(
        request.user, organisation_id, version_id
    )
    if version.status not in (PolicyVersion.STATUS_APPROVED, PolicyVersion.STATUS_SUPERSEDED):
        raise Http404

    pdf_bytes, _page_count = render_policy_pdf(version, organisation)

    filename = f"{organisation.name} - Information Security Policy v{version.version_number}.pdf"
    safe_ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "policy.pdf"
    encoded_name = quote(filename)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{encoded_name}'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


__all__ = [
    "policy_detail",
    "policy_generate",
    "policy_version_detail",
    "policy_edit",
    "policy_approve_direct",
    "policy_approve_external",
    "policy_new_draft",
    "policy_download",
]
