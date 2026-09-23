from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from organisations.views import get_member_organisation_or_404

from evidence import link_services, services
from evidence.exceptions import EvidenceValidationError
from evidence.forms import ControlEvidenceLinkForm, EvidenceExternalReferenceForm, EvidenceFileUploadForm
from evidence.models import ControlEvidenceLink, EvidenceItem
from evidence.storage import CONTENT_TYPES, evidence_file_path


def _get_member_evidence_item_or_404(user, organisation_id, evidence_id):
    """
    Tenant-scoped evidence fetch, mirroring
    organisations.views.get_member_organisation_or_404 /
    key_assets.views._get_member_key_asset_or_404: membership is verified
    first, then the evidence item is looked up scoped to that organisation
    - so a foreign/manipulated evidence id in the URL is an ordinary 404,
    never a path to another organisation's evidence.
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    item = get_object_or_404(EvidenceItem, id=evidence_id, organisation=organisation)
    return organisation, item


def _get_supersedes_target(organisation, request):
    """
    Resolve an optional `?supersedes=<evidence_id>` used by the "replace
    this evidence" flow from the detail page. Scoped to the same
    organisation and required to be active - a 404 (not a 400/403) for
    anything else, matching this codebase's tenant-scoping convention.
    """
    supersedes_id = request.GET.get("supersedes") or request.POST.get("supersedes")
    if not supersedes_id:
        return None
    return get_object_or_404(
        EvidenceItem,
        id=supersedes_id,
        organisation=organisation,
        status=EvidenceItem.STATUS_ACTIVE,
    )


@login_required
def evidence_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    items = list(EvidenceItem.objects.filter(organisation=organisation))
    context = {
        "organisation": organisation,
        "active_items": [i for i in items if i.status == EvidenceItem.STATUS_ACTIVE],
        "superseded_items": [i for i in items if i.status == EvidenceItem.STATUS_SUPERSEDED],
        "withdrawn_items": [i for i in items if i.status == EvidenceItem.STATUS_WITHDRAWN],
    }
    return render(request, "evidence/list.html", context)


@login_required
def evidence_upload(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    supersedes = _get_supersedes_target(organisation, request)

    if request.method == "POST":
        form = EvidenceFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                item = services.create_file_evidence(
                    organisation=organisation,
                    actor=request.user,
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    source_label=form.cleaned_data["source_label"],
                    observed_at=form.cleaned_data["observed_at"],
                    valid_until=form.cleaned_data["valid_until"],
                    uploaded_file=form.cleaned_data["file"],
                    supersedes=supersedes,
                )
            except EvidenceValidationError as exc:
                form.add_error("file", str(exc))
                messages.error(request, "The evidence file could not be saved. Please check the errors below.")
            else:
                messages.success(request, f'Evidence "{item.title}" uploaded.')
                return redirect(
                    "evidence:detail", organisation_id=organisation.id, evidence_id=item.id
                )
        else:
            messages.error(request, "The evidence file could not be saved. Please check the errors below.")
    else:
        form = EvidenceFileUploadForm()

    return render(
        request,
        "evidence/upload.html",
        {"organisation": organisation, "form": form, "supersedes": supersedes},
    )


@login_required
def evidence_add_reference(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    supersedes = _get_supersedes_target(organisation, request)

    if request.method == "POST":
        form = EvidenceExternalReferenceForm(request.POST)
        if form.is_valid():
            item = services.create_external_reference_evidence(
                organisation=organisation,
                actor=request.user,
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                source_label=form.cleaned_data["source_label"],
                observed_at=form.cleaned_data["observed_at"],
                valid_until=form.cleaned_data["valid_until"],
                reference_url=form.cleaned_data["reference_url"],
                supersedes=supersedes,
            )
            messages.success(request, f'Evidence reference "{item.title}" added.')
            return redirect(
                "evidence:detail", organisation_id=organisation.id, evidence_id=item.id
            )
        messages.error(
            request, "The evidence reference could not be saved. Please check the errors below."
        )
    else:
        form = EvidenceExternalReferenceForm()

    return render(
        request,
        "evidence/add_reference.html",
        {"organisation": organisation, "form": form, "supersedes": supersedes},
    )


@login_required
def evidence_detail(request, organisation_id, evidence_id):
    organisation, item = _get_member_evidence_item_or_404(
        request.user, organisation_id, evidence_id
    )
    request.session["current_organisation_id"] = str(organisation.id)
    return render(
        request, "evidence/detail.html", {"organisation": organisation, "item": item}
    )


@login_required
def evidence_download(request, organisation_id, evidence_id):
    """
    Private, authenticated, tenant-scoped file download (PID §9/§22).

    No user-supplied filesystem path is ever consulted: the URL carries
    only the organisation id (already tenant-checked above) and the
    EvidenceItem's primary key, and the file path is resolved strictly
    from that item's own opaque `stored_filename` column.
    """
    organisation, item = _get_member_evidence_item_or_404(
        request.user, organisation_id, evidence_id
    )
    if item.kind != EvidenceItem.KIND_FILE:
        raise Http404

    try:
        path = evidence_file_path(organisation.id, item.stored_filename)
        file_handle = open(path, "rb")
    except (EvidenceValidationError, FileNotFoundError, OSError):
        raise Http404

    response = FileResponse(
        file_handle,
        content_type=CONTENT_TYPES.get(item.file_type, "application/octet-stream"),
    )
    safe_ascii_name = item.original_filename.encode("ascii", "ignore").decode("ascii") or "evidence-file"
    encoded_name = quote(item.original_filename)
    response["Content-Disposition"] = (
        f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{encoded_name}'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def evidence_withdraw(request, organisation_id, evidence_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, item = _get_member_evidence_item_or_404(
        request.user, organisation_id, evidence_id
    )
    try:
        services.withdraw_evidence(item, request.user)
    except EvidenceValidationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Evidence "{item.title}" withdrawn.')
    return redirect("evidence:detail", organisation_id=organisation.id, evidence_id=item.id)


@login_required
def evidence_link_control(request, organisation_id, evidence_id):
    """
    Link this evidence item to a catalogue control (PID §6.4, §18).

    Tenant scoping is identical to every other evidence view: the
    organisation membership check and the evidence-item lookup both live
    in `_get_member_evidence_item_or_404`, so a foreign/manipulated
    evidence id in the URL is an ordinary 404. `link_services.
    link_evidence_to_control` additionally re-verifies the tenant match
    itself (defence in depth - see that function's docstring), so this
    view never needs to trust its own lookup alone for the write.
    """
    organisation, item = _get_member_evidence_item_or_404(
        request.user, organisation_id, evidence_id
    )
    request.session["current_organisation_id"] = str(organisation.id)

    if request.method == "POST":
        form = ControlEvidenceLinkForm(request.POST)
        if form.is_valid():
            try:
                link_services.link_evidence_to_control(
                    organisation,
                    item,
                    form.cleaned_data["control_key"],
                    form.cleaned_data["relationship"],
                    form.cleaned_data["rationale"],
                    request.user,
                )
            except EvidenceValidationError as exc:
                form.add_error(None, str(exc))
                messages.error(
                    request, "This evidence could not be linked. Please check the errors below."
                )
            else:
                messages.success(request, "Evidence linked to control.")
                return redirect(
                    "evidence:detail", organisation_id=organisation.id, evidence_id=item.id
                )
        else:
            messages.error(
                request, "This evidence could not be linked. Please check the errors below."
            )
    else:
        form = ControlEvidenceLinkForm()

    return render(
        request,
        "evidence/link_control.html",
        {"organisation": organisation, "item": item, "form": form},
    )


@login_required
def evidence_unlink_control(request, organisation_id, evidence_id, link_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, item = _get_member_evidence_item_or_404(
        request.user, organisation_id, evidence_id
    )
    # Scoped to both this organisation AND this evidence item - a link id
    # belonging to another evidence item (even within the same
    # organisation) is an ordinary 404, not just organisation-scoped.
    link = get_object_or_404(
        ControlEvidenceLink, id=link_id, organisation=organisation, evidence=item
    )
    link_services.unlink_evidence_from_control(link, request.user)
    messages.success(request, "Evidence unlinked from control.")
    return redirect("evidence:detail", organisation_id=organisation.id, evidence_id=item.id)
