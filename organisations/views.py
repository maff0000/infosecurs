from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

import governance.services
from entitlements.decorators import require_capability
from entitlements.metrics import (
    STATE_COMPLETE,
    STATE_INCOMPLETE,
    get_foundational_security_posture,
    get_needs_attention,
    get_security_foundations_completion,
)
from entitlements.models import ProductArea, RequirementKind
from entitlements.session import Invalid, get_validated_context
from entitlements.tiers import TIER_PAUSED

from organisations.forms import OrganisationCreateForm, OrganisationProfileForm
from organisations.models import (
    AuditEvent,
    CustomerZeroFixture,
    Organisation,
    OrganisationMembership,
    OrganisationProfile,
)
from organisations.reset_service import (
    ResetFilesystemError,
    reset_customer_zero_organisation,
)
from security_baseline.models import ANSWER_CHOICES

# ---------------------------------------------------------------------------
# M007-WI5 (PID §13-15) small shared helpers. Both `organisation_detail`
# (Home's Needs Attention links) and `organisation_foundations` (each
# requirement row's own action link) resolve a `ProductArea.code` to a real
# URL the exact same way `entitlements.navigation.build_navigation_tree`
# already does - `reverse(area.destination_view_name, kwargs={...})` - so
# there is exactly one route-resolution approach in this app, not one
# hand-rolled per template (PID dispatch: "reuse the same small resolution
# approach in both places... do not duplicate route-resolution logic").
# Deliberately NOT added to `entitlements.navigation`/`entitlements.
# capabilities` itself - those modules are WI2/WI1 scope this dispatch does
# not redesign; this is a small view-level helper, not a new shared service.
# ---------------------------------------------------------------------------


def _product_area_url(product_area_code: str, organisation_id) -> str:
    area = ProductArea.objects.get(code=product_area_code)
    return reverse(area.destination_view_name, kwargs={"organisation_id": organisation_id})


# PID §14.1's "recommended wording shape" example lines, expressed as
# (singular, plural) phrases that follow the leading count - e.g. count=3 +
# this dict's "important security controls are not fully implemented"
# plural renders "3 important security controls are not fully implemented",
# matching the PID's own example verbatim. The singular form only fires for
# `policy_review_overdue` in practice today (its count is always 0 or 1 -
# entitlements.metrics.get_needs_attention's own docstring), but every
# signal gets one anyway so a future signal whose count can be exactly 1
# never reads ungrammatically ("1 important security controls are...").
_NEEDS_ATTENTION_PHRASES: dict[str, tuple[str, str]] = {
    "important_controls_not_fully_implemented": (
        "important security control is not fully implemented",
        "important security controls are not fully implemented",
    ),
    "foundations_items_incomplete": (
        "Security Foundations item still needs completion",
        "Security Foundations items still need completion",
    ),
    "controls_marked_not_sure": (
        "security control is marked Not sure",
        "security controls are marked Not sure",
    ),
    "policy_review_overdue": (
        "policy review is overdue",
        "policy reviews are overdue",
    ),
}


def _needs_attention_lines(needs_attention, organisation_id) -> list[dict]:
    """
    PID §14/§27: only a non-zero-count signal produces a rendered line (a
    `count == 0` signal is entirely omitted here - `entitlements.metrics`
    itself always returns all four, count=0 where nothing applies, so this
    is the one place that filters, matching that module's own docstring).
    Iterated in `entitlements.metrics.NeedsAttention`'s own field order,
    which is PID §14's own listed order. No HTML is built here - `text` is
    plain wording, `url` a plain string; the template alone decides how
    `click here` is marked up (PID §14.1's binding link-behaviour rule).
    """
    lines = []
    for signal in (
        needs_attention.important_controls,
        needs_attention.foundations_incomplete,
        needs_attention.not_sure_controls,
        needs_attention.policy_review_overdue,
    ):
        if signal.count == 0:
            continue
        singular, plural = _NEEDS_ATTENTION_PHRASES[signal.key]
        phrase = singular if signal.count == 1 else plural
        lines.append(
            {
                "text": f"{signal.count} {phrase}",
                "url": _product_area_url(signal.destination_product_area_code, organisation_id),
            }
        )
    return lines


# PID §15's "show the real answer, not a flattened Complete/Incomplete" for
# a BASELINE_CONTROL row - reuses `security_baseline.models.ANSWER_CHOICES`
# verbatim (the exact same Yes/Partially/No/Not sure/Not applicable wording
# the Baseline questionnaire itself already shows the customer), never a
# second, independently-worded label table.
_BASELINE_ANSWER_DISPLAY: dict[str, str] = dict(ANSWER_CHOICES)

# A DERIVED_MILESTONE row's `answer_state` is one of these two
# (entitlements.metrics.STATE_COMPLETE/STATE_INCOMPLETE) - simpler wording
# is fine here per the dispatch ("there is no separate security-strength
# fact for a milestone to preserve").
_MILESTONE_ANSWER_DISPLAY: dict[str, str] = {
    STATE_COMPLETE: "Complete",
    STATE_INCOMPLETE: "Needs completion",
}


def _requirement_answer_display(state) -> str:
    if state.requirement_kind == RequirementKind.BASELINE_CONTROL:
        return _BASELINE_ANSWER_DISPLAY.get(state.answer_state, state.answer_state)
    return _MILESTONE_ANSWER_DISPLAY.get(state.answer_state, state.answer_state)


def _product_area_labels() -> dict[str, str]:
    """One bounded query for every active ProductArea's label, shared
    across every row `organisation_foundations` renders - never one query
    per requirement row."""
    return dict(ProductArea.objects.active().values_list("code", "label"))


def get_member_organisation_or_404(user, organisation_id):
    """
    Fetch an organisation, scoped to the requesting user's membership, in a
    single query.

    This is deliberate: the tenant scope is baked into the query itself
    (memberships__user=user) rather than fetched-then-checked, so there is
    no code path where the object exists but the caller forgets to verify
    membership before using it. A non-member (or a manipulated/foreign
    UUID in the URL) gets an ordinary 404, not a 403 - callers never learn
    whether an organisation they cannot access exists at all.
    """
    return get_object_or_404(
        Organisation, id=organisation_id, memberships__user=user
    )


@login_required
def organisation_list(request):
    organisations = Organisation.objects.filter(memberships__user=request.user).order_by("name")
    return render(
        request,
        "organisations/list.html",
        {"organisations": organisations},
    )


@login_required
def organisation_create(request):
    if request.method == "POST":
        form = OrganisationCreateForm(request.POST)
        if form.is_valid():
            # Atomic (PID §6-7): an organisation must never be left without
            # its Account Holder's governance person/role rows - this is
            # one transaction, not a best-effort follow-up call.
            with transaction.atomic():
                organisation = form.save()
                OrganisationMembership.objects.create(
                    organisation=organisation,
                    user=request.user,
                    role=OrganisationMembership.ROLE_OWNER,
                )
                governance.services.ensure_account_holder_person(organisation, request.user)
            messages.success(request, f'Organisation "{organisation.name}" created.')
            return redirect("organisations:detail", organisation_id=organisation.id)
    else:
        form = OrganisationCreateForm()
    return render(request, "organisations/create.html", {"form": form})


@login_required
@require_capability()
def organisation_detail(request, organisation_id):
    """
    The Home dashboard (M007-WI5, PID §13-14) - supersedes the old M006
    flat Overview card list this view used to render via `organisations.
    overview.build_overview` (that module and every one of its area
    functions remain fully intact and independently tested -
    `organisations/tests/test_overview.py` - this view simply no longer
    renders their output as Home's primary content, per Central
    Architecture's own "do not clutter the initial Home beyond the
    authorised M007 structure" instruction).

    Tier-branched, not route-guard-branched: `home`'s own `ProductArea.
    min_package_tier` is 0 (PID Appendix A), so `require_capability()`
    above never denies this route for ANY tier including Paused - PID
    §13.1 is explicit that the Paused/non-Paused distinction here is a
    VIEW-LEVEL content decision, not an access-control one. A Paused
    session renders only the minimal paused state, with ZERO calls into
    `entitlements.metrics` (computed-then-hidden is exactly what PID §13.1
    asks this view NOT to do); every other tier gets the two metric cards
    plus Needs Attention.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    context = get_validated_context(request)
    if isinstance(context, Invalid):
        # Defence in depth only - unreachable in normal operation:
        # `require_capability()` above already calls `has_capability`,
        # which itself calls `get_validated_context` and denies (redirects
        # to login) an Invalid session before this view body ever runs
        # (entitlements/decorators.py's own fail-closed handling). This
        # mirrors that exact same redirect rather than assuming it can
        # never happen.
        return redirect_to_login(request.get_full_path())

    if context.package_tier == TIER_PAUSED:
        return render(
            request,
            "organisations/detail.html",
            {"organisation": organisation, "is_paused": True},
        )

    posture = get_foundational_security_posture(organisation)
    completion = get_security_foundations_completion(organisation)
    needs_attention = get_needs_attention(organisation)

    return render(
        request,
        "organisations/detail.html",
        {
            "organisation": organisation,
            "is_paused": False,
            "posture": posture,
            "completion": completion,
            "security_state_url": _product_area_url("security_state", organisation.id),
            "foundations_url": reverse(
                "organisations:foundations", kwargs={"organisation_id": organisation.id}
            ),
            "needs_attention_lines": _needs_attention_lines(needs_attention, organisation.id),
        },
    )


@login_required
@require_capability()
def organisation_foundations(request, organisation_id):
    """
    The Foundations workspace (M007-WI5, PID §15) - a plain, read-only
    listing of every active v1 `FoundationRequirement`'s resolved state.
    Reuses `get_security_foundations_completion`'s own `requirement_states`
    (already filtered to every `counts_toward_completion=True` row - today
    all 18) rather than calling `get_foundations_requirement_states` a
    second time: the exact same per-item facts the Home completion card
    itself is built from (PID §15's own "each displayed state is derived
    from the same resolver used by the Home completion metric"), one query
    pass, not two.

    No metric/completion math happens here - `completion.percentage`/
    `completion.completed_count`/`completion.total_count` are rendered
    exactly as `entitlements.metrics` returns them. No form, no POST, no
    editable checkbox anywhere on this page - every state is derived and
    read-only, exactly like Home.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    completion = get_security_foundations_completion(organisation)
    area_labels = _product_area_labels()

    rows = [
        {
            "state": state,
            "area_label": area_labels.get(state.product_area_code, state.product_area_code),
            "answer_display": _requirement_answer_display(state),
            "action_url": _product_area_url(state.product_area_code, organisation.id),
        }
        for state in completion.requirement_states
    ]

    return render(
        request,
        "organisations/foundations.html",
        {"organisation": organisation, "completion": completion, "rows": rows},
    )


@login_required
@require_capability()
def organisation_hub(request, organisation_id):
    """
    The "Organisation" primary-nav landing page (M006 PID §5): Profile,
    Governance roles and Workplace used to live as three of the flat card
    list `organisations:detail` used to render (M006's Overview page;
    M007-WI5, above, rewrote that URL into the new Home dashboard - PID
    §13 - which does not render this hub's own links either); they need a
    single home now that they are no longer on either page. Deliberately
    minimal - three links, mirroring the existing `summary-card` style
    already used across this codebase - not a new CRUD surface of its own.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)
    return render(
        request,
        "organisations/organisation_hub.html",
        {
            "organisation": organisation,
            # M008A: the DEV tools section is visible only when BOTH the
            # settings-level gate is on AND this particular organisation is
            # the trusted fixture - computed here, not just relied on via
            # "the URL happens to be unreachable" (the dispatch's own
            # explicit requirement: a template conditional showing/hiding a
            # link must check the same setting the view itself checks).
            "customer_zero_reset_enabled": (
                settings.CUSTOMER_ZERO_RESET_ENABLED
                and CustomerZeroFixture.objects.filter(organisation=organisation).exists()
            ),
        },
    )


@login_required
@require_capability()
def organisation_profile(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    instance = OrganisationProfile.objects.filter(organisation=organisation).first()
    is_new = instance is None

    if request.method == "POST":
        form = OrganisationProfileForm(request.POST, instance=instance)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.organisation = organisation
            profile.save()
            AuditEvent.objects.create(
                organisation=organisation,
                action=(
                    AuditEvent.ACTION_PROFILE_CREATED
                    if is_new
                    else AuditEvent.ACTION_PROFILE_UPDATED
                ),
                actor=request.user,
            )
            messages.success(request, "Organisation profile saved.")
            return redirect("organisations:profile", organisation_id=organisation.id)
        messages.error(request, "The profile could not be saved. Please check the errors below.")
    else:
        form = OrganisationProfileForm(instance=instance)

    return render(
        request,
        "organisations/profile_form.html",
        {"organisation": organisation, "form": form, "is_new": is_new},
    )


# ---------------------------------------------------------------------------
# M008A (docs/evidence/M008A-RESET-DELETION-MANIFEST.md) - dev-only Customer
# Zero reset. Deliberately NOT decorated with `@require_capability()`: that
# decorator resolves a `ProductArea`/capability code for the route, and
# this is a dev-tools surface, not a commercial product area - the PID
# dispatch is explicit that no new `ProductArea`/capability should be
# invented just to force a fourth authority layer that doesn't naturally
# exist here. The three real authority layers checked below are exactly
# the dispatch's own framing:
#   1. The environment gate (settings.CUSTOMER_ZERO_RESET_ENABLED) -
#      checked FIRST, before any other authorization logic, and fails
#      closed with a genuine 404 (never 403, never a redirect) for BOTH
#      GET and POST.
#   2. The CustomerZeroFixture identity check - the one thing that makes
#      an organisation eligible for this feature at all, re-checked again,
#      independently, inside `reset_customer_zero_organisation` itself
#      (defence in depth - this view's own check is never the only guard).
#   3. Ordinary tenant-owner membership, via the same
#      `get_member_organisation_or_404` every other organisation-scoped
#      view in this codebase already uses - no reset-specific membership
#      logic.
# A fail-closed/tampered `infosecurs_context` (PID §6.4, M007) is still
# handled explicitly below, via the exact same `entitlements.session.
# get_validated_context` call `entitlements.decorators.require_capability`
# itself uses for this one piece - reused directly rather than
# re-implemented, without pulling in that decorator's unrelated
# capability/tier/active-organisation-alignment machinery, which has no
# natural meaning for a route with no capability code.
# ---------------------------------------------------------------------------
@login_required
def customer_zero_reset(request, organisation_id):
    """
    GET renders a confirmation screen; it never deletes anything - there is
    no code path here where a GET request reaches
    `reset_customer_zero_organisation`. POST validates a literal, typed
    `RESET` confirmation (case-sensitive) plus Django's own CSRF protection
    (this view is never exempted from it) before calling the service
    function.

    On a successful reset, calls Django's own `logout(request)` (PID §8's
    Central Architecture instruction: "reset succeeds -> session destroyed
    -> customer returned to login") - a full session destroy, not merely
    `entitlements.session.issue_context`'s key-rotation - then redirects to
    the login page. `logout()` only ever touches the current request's own
    session (Django's own implementation - `request.session.flush()`), so
    every other user's session is completely unaffected by construction.
    """
    # 1. Environment gate - checked first, before anything else, and
    # fails closed as an ordinary 404 regardless of method.
    if not settings.CUSTOMER_ZERO_RESET_ENABLED:
        raise Http404

    # M007 fail-closed session-validation path (PID §6.4), reused as-is -
    # see this section's module-level comment above for why this is not a
    # reset-specific check.
    context = get_validated_context(request)
    if isinstance(context, Invalid):
        return redirect_to_login(request.get_full_path())

    # Ordinary tenant-owner membership - the same helper, same Http404
    # convention, every other organisation-scoped view in this codebase
    # already uses.
    organisation = get_member_organisation_or_404(request.user, organisation_id)

    # The real safety-critical check: this organisation must be the
    # trusted, synthetic Customer Zero fixture. An absent fixture relation
    # renders EXACTLY like "not a member"/"doesn't exist" - a plain 404,
    # never a 403 (a 403 would leak "this organisation exists but isn't
    # the fixture" to an authenticated member of some other, real
    # organisation).
    if not CustomerZeroFixture.objects.filter(organisation=organisation).exists():
        raise Http404

    if request.method == "POST":
        confirmation = request.POST.get("confirmation", "")
        if confirmation != "RESET":
            messages.error(
                request,
                "Type RESET exactly (case-sensitive) to confirm. Nothing was deleted.",
            )
            return render(
                request,
                "organisations/customer_zero_reset_confirm.html",
                {"organisation": organisation},
            )

        try:
            reset_customer_zero_organisation(organisation, performed_by=request.user)
        except ResetFilesystemError:
            # PID §A4: the DB transaction already committed successfully
            # at this point - the organisation's data IS reset - but the
            # separate evidence-directory filesystem cleanup step did not
            # fully succeed. Never report this as a clean success: no
            # logout, no redirect to login, a clear on-screen error
            # instead, and the reset is safely retryable (idempotent).
            messages.error(
                request,
                "The organisation's data was reset, but cleaning up its stored "
                "evidence files did not fully succeed. Re-run the reset to retry "
                "the file cleanup - the database state is already consistent.",
            )
            return render(
                request,
                "organisations/customer_zero_reset_confirm.html",
                {"organisation": organisation},
            )

        logout(request)
        return redirect("login")

    return render(
        request,
        "organisations/customer_zero_reset_confirm.html",
        {"organisation": organisation},
    )
