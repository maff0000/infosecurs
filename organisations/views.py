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

from organisations.forms import (
    OrganisationCreateForm,
    OrganisationProfileForm,
    OrganisationProfileStage1Form,
    OrganisationProfileStage2SupplementaryForm,
    OrganisationProfileStage3Form,
)
from organisations.models import (
    UNKNOWN,
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
from governance.models import GovernanceRoleAssignment
from key_assets.models import KeyAsset
from security_baseline.models import ANSWER_CHOICES
from workplace.models import Workplace

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

    # M008C/M008B-WI2a: a small, purely additive hook into this existing,
    # unredesigned page - three links to the new Stage 1-3 guided-journey
    # pages, rendered ABOVE the existing read-only requirement rows below.
    # This does not touch `completion`/`rows`/the per-requirement
    # `action_url` resolution above in any way (those still resolve
    # exactly as M007-WI5 left them, untouched by this WI - no
    # ProductArea/FoundationRequirement data migration was made or
    # needed) - it is new, separate context the template renders as its
    # own separate section. See this WI's dispatch report for why this
    # was chosen over repointing any existing `action_url`.
    stage_links = [
        {
            "number": 1,
            "name": "Your Business",
            "url": reverse(
                "organisations:stage1_business", kwargs={"organisation_id": organisation.id}
            ),
        },
        {
            "number": 2,
            "name": "Your People & Workplaces",
            "url": reverse(
                "organisations:stage2_people_workplaces",
                kwargs={"organisation_id": organisation.id},
            ),
        },
        {
            "number": 3,
            "name": "Your Technology & Data",
            "url": reverse(
                "organisations:stage3_technology_data",
                kwargs={"organisation_id": organisation.id},
            ),
        },
        # M008C-WI3: Stage 5 "Your Risks & Actions" - same purely additive
        # pattern as the Stage 1-3 tiles above (this WI's own instruction:
        # "add a 4th tile there for Stage 5, same pattern"). Stage 4 (the
        # guided security-baseline walk, `security_baseline:foundations_start`)
        # deliberately has no tile of its own here - it was already reachable
        # before this WI via the 12 BASELINE_CONTROL rows' own `action_url`
        # below, and adding one was not asked for by this WI's scope.
        {
            "number": 5,
            "name": "Your Risks & Actions",
            "url": reverse(
                "risk_register:foundations_risks_actions",
                kwargs={"organisation_id": organisation.id},
            ),
        },
    ]

    return render(
        request,
        "organisations/foundations.html",
        {
            "organisation": organisation,
            "completion": completion,
            "rows": rows,
            "stage_links": stage_links,
        },
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
# M008C/M008B-WI2a - Stage 1-3 of the guided Foundations journey
# (docs/design/M008B-STAGES-1-3-CATALOGUE.md, docs/design/
# M008C-UX-FLOW-DESIGN.md). Three single-screen stage pages, all still
# writing into the exact same `OrganisationProfile` row `organisation_
# profile` above writes into (M008C §8: "this design introduces no new
# truth store") - never a second, parallel profile model.
#
# Each view follows `organisation_profile`'s own exact shape (fetch-or-
# None instance, is_new flag, save(commit=False) + set organisation +
# save(), the same AuditEvent actions) so a stage save and a legacy-
# profile-page save are indistinguishable in the audit trail - both are
# just "the profile was created/updated", whichever screen did it.
#
# `_count_confirmed` backs each stage's own simple, local progress line
# ("N of M confirmed so far"). This is DELIBERATELY NOT the REVIEWED/
# confirmed pair M008C-UX-FLOW-DESIGN.md §6 specifies for Stage 4's 12
# baseline controls: that pair needs its own per-answer provenance
# (security_baseline.AnswerSelectionDetail) to distinguish "never visited"
# from "visited and explicitly chose Not sure" - OrganisationProfile has
# no equivalent provenance table for any of its fields, and adding one is
# explicitly out of this WI's scope (no new migration). Each Stage 1-3
# field already always holds SOME value (either a genuine confirmed
# answer, or the model's own UNKNOWN/blank default) - there is no third
# "unvisited" state to distinguish at this layer - so this helper answers
# the honest, simpler question "how many of this stage's fields currently
# hold a real, confirmed answer", not "how many have been reviewed".
# ---------------------------------------------------------------------------


def _count_confirmed(instance, field_names):
    """How many of `field_names` on `instance` (an `OrganisationProfile`,
    or `None` if the organisation has no profile row yet) currently hold a
    genuinely confirmed value - i.e. not the model's own UNKNOWN/blank
    default. See this section's module comment above for why this is a
    deliberately simpler count than Stage 4's own REVIEWED/confirmed
    pair."""
    if instance is None or instance.pk is None:
        return 0
    confirmed = 0
    for name in field_names:
        value = getattr(instance, name)
        if value in (None, "", UNKNOWN):
            continue
        confirmed += 1
    return confirmed


STAGE1_BUSINESS_FIELDS = [
    "legal_trading_name",
    "sector",
    "staff_count",
    "commercial_security_driver",
    "receives_security_questionnaires",
]


@login_required
@require_capability()
def organisation_stage1_business(request, organisation_id):
    """Stage 1 of 6 - Your Business (M008B §Stage 1). Reachable/editable
    at any time (save-and-return-later, M008C-UX-FLOW-DESIGN.md §3) -
    GET always re-renders whatever is currently on the profile row, there
    is no one-shot-only completion state."""
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    instance = OrganisationProfile.objects.filter(organisation=organisation).first()
    is_new = instance is None

    if request.method == "POST":
        form = OrganisationProfileStage1Form(request.POST, instance=instance)
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
            messages.success(request, "Your Business details saved.")
            return redirect(
                "organisations:stage2_people_workplaces", organisation_id=organisation.id
            )
        messages.error(
            request, "Those details could not be saved. Please check the errors below."
        )
    else:
        form = OrganisationProfileStage1Form(instance=instance)

    return render(
        request,
        "organisations/stage1_business.html",
        {
            "organisation": organisation,
            "form": form,
            "confirmed_count": _count_confirmed(instance, STAGE1_BUSINESS_FIELDS),
            "total_count": len(STAGE1_BUSINESS_FIELDS),
            "foundations_url": reverse(
                "organisations:foundations", kwargs={"organisation_id": organisation.id}
            ),
        },
    )


STAGE2_PEOPLE_WORKPLACES_FIELDS = [
    "people_with_system_access_count",
    "has_remote_or_offsite_access",
]


@login_required
@require_capability()
def organisation_stage2_people_workplaces(request, organisation_id):
    """
    Stage 2 of 6 - Your People & Workplaces (M008B §Stage 2). A landing
    page, not a single form: work pattern/workplaces (§2.1-2.2) and
    governance roles (§2.5) link out to the existing, already-structured
    `workplace`/`governance` flows (see this WI's dispatch report for why
    "link out, come back" was chosen over embedding those substantial UIs
    inline); the two brand-new dedicated facts this stage owns directly
    (§2.3/§2.4) are a small inline form, saved by this same view.

    The link-out destination for work pattern/workplaces resumes at the
    sensible point: straight to the pattern-selection onboarding start if
    this organisation has no active workplace yet, or to the existing
    workplace list otherwise - never re-asking the pattern question once
    at least one real workplace exists.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    instance = OrganisationProfile.objects.filter(organisation=organisation).first()
    is_new = instance is None

    if request.method == "POST":
        form = OrganisationProfileStage2SupplementaryForm(request.POST, instance=instance)
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
            messages.success(request, "Your People & Workplaces details saved.")
            return redirect(
                "organisations:stage3_technology_data", organisation_id=organisation.id
            )
        messages.error(
            request, "Those details could not be saved. Please check the errors below."
        )
    else:
        form = OrganisationProfileStage2SupplementaryForm(instance=instance)

    has_active_workplace = Workplace.objects.filter(
        organisation=organisation, is_active=True
    ).exists()
    workplace_url = reverse(
        "workplace:list" if has_active_workplace else "workplace:onboarding_start",
        kwargs={"organisation_id": organisation.id},
    )
    governance_assigned_count = GovernanceRoleAssignment.objects.filter(
        organisation=organisation
    ).count()

    return render(
        request,
        "organisations/stage2_people_workplaces.html",
        {
            "organisation": organisation,
            "form": form,
            "confirmed_count": _count_confirmed(instance, STAGE2_PEOPLE_WORKPLACES_FIELDS),
            "total_count": len(STAGE2_PEOPLE_WORKPLACES_FIELDS),
            "has_active_workplace": has_active_workplace,
            "workplace_url": workplace_url,
            "governance_url": reverse(
                "governance:roles", kwargs={"organisation_id": organisation.id}
            ),
            "governance_assigned_count": governance_assigned_count,
            "stage1_url": reverse(
                "organisations:stage1_business", kwargs={"organisation_id": organisation.id}
            ),
        },
    )


STAGE3_TECHNOLOGY_DATA_FIELDS = [
    "productivity_platform",
    "primary_cloud_provider",
    "endpoint_management",
    "develops_hosts_own_software",
    "handles_personal_data",
    "handles_confidential_business_data",
    "handles_payment_card_data",
    "handles_special_category_data",
    "cyber_essentials_status",
    "iso27001_status",
]


@login_required
@require_capability()
def organisation_stage3_technology_data(request, organisation_id):
    """
    Stage 3 of 6 - Your Technology & Data (M008B §Stage 3). The six
    OrganisationProfile-backed questions (3.1-3.6, ten underlying fields)
    are one form on this screen; Key assets (§3.7) links out to the
    existing `key_assets` app's own list/create flow unchanged, same
    "link out, come back" pattern as Stage 2. The last stage in this WI's
    scope - "Save and continue" returns to the Foundations landing, not a
    Stage 4 this WI does not own.

    Zero AI/LLM calls: this view (like every other view in this module)
    never imports or calls `ai_platform` - it only reads/writes
    `OrganisationProfile` and the read-only `KeyAsset` confirmed count
    below.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    instance = OrganisationProfile.objects.filter(organisation=organisation).first()
    is_new = instance is None

    if request.method == "POST":
        form = OrganisationProfileStage3Form(request.POST, instance=instance)
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
            messages.success(request, "Your Technology & Data details saved.")
            return redirect("organisations:foundations", organisation_id=organisation.id)
        messages.error(
            request, "Those details could not be saved. Please check the errors below."
        )
    else:
        form = OrganisationProfileStage3Form(instance=instance)

    confirmed_assets_count = KeyAsset.objects.filter(
        organisation=organisation, status=KeyAsset.STATUS_CONFIRMED
    ).count()

    return render(
        request,
        "organisations/stage3_technology_data.html",
        {
            "organisation": organisation,
            "form": form,
            "confirmed_count": _count_confirmed(instance, STAGE3_TECHNOLOGY_DATA_FIELDS),
            "total_count": len(STAGE3_TECHNOLOGY_DATA_FIELDS),
            "key_assets_url": reverse(
                "key_assets:list", kwargs={"organisation_id": organisation.id}
            ),
            "confirmed_assets_count": confirmed_assets_count,
            "stage2_url": reverse(
                "organisations:stage2_people_workplaces",
                kwargs={"organisation_id": organisation.id},
            ),
        },
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
