from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from activity.models import ActivityEvent
from activity.services import record_event
from entitlements.decorators import require_capability
from organisations.views import get_member_organisation_or_404

from risk_register.forms import RiskEditForm
from risk_register.methodology import CATALOGUE_BY_ID, VARIANT_NO
from risk_register.models import Risk
from risk_register.risk_choices import RATIONALE_CODE_LABELS, TREATMENT_CATEGORY_LABELS
from risk_register.scenario_engine import current_trigger_variant, current_unconfirmed_control_keys
from risk_register.services import generate_draft_risks
from security_baseline import stage4

# The RiskEditForm fields whose before/after values are worth preserving as
# structured delta (Learning Signal Capture Addendum §3/§7): every field the
# form actually lets a customer change. Kept as an explicit list, mirrored
# from RiskEditForm.Meta.fields, rather than introspected from the form, so
# it is obvious at a glance which fields this event type covers.
#
# `threat`/`vulnerability` were removed from this list (and from
# `RiskEditForm` itself) by the M008C-WI3 dispatch - see
# `risk_register.forms.RiskEditForm`'s own docstring: both are now
# read-only display of the matched scenario's wording, never customer-
# editable, so they can no longer appear in an edit delta.
_RISK_EDIT_DELTA_FIELDS = [
    "title",
    "impact",
    "likelihood",
    "rationale",
    "proposed_treatment",
]


def _get_member_risk_or_404(user, organisation_id, risk_id):
    """
    Tenant-scoped risk fetch, mirroring
    organisations.views.get_member_organisation_or_404 and
    key_assets.views._get_member_key_asset_or_404: membership is verified
    first (an ordinary 404 for a non-member or a manipulated/foreign
    organisation id), then the risk is looked up scoped to that
    organisation - there is no code path where a risk from a different
    organisation could be read or acted on via a mismatched/foreign risk id
    in the URL (PID.md M002 §16).
    """
    organisation = get_member_organisation_or_404(user, organisation_id)
    risk = get_object_or_404(Risk, id=risk_id, organisation=organisation)
    return organisation, risk


@login_required
@require_capability()
def risk_list(request, organisation_id):
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    risks = list(Risk.objects.filter(organisation=organisation))
    context = {
        "organisation": organisation,
        "draft_risks": [r for r in risks if r.status == Risk.STATUS_DRAFT_AI_SUGGESTED],
        "confirmed_risks": [r for r in risks if r.status == Risk.STATUS_CONFIRMED],
        "dismissed_risks": [r for r in risks if r.status == Risk.STATUS_DISMISSED],
    }
    return render(request, "risk_register/list.html", context)


@login_required
@require_capability()
def risk_generate(request, organisation_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    # PID §0.6/§0.7 (M002-3b dispatch): generation is now a deterministic
    # scenario-instantiation pass - no AI call, no gateway, and therefore
    # nothing here that can fail with a gateway/network error. It can only
    # ever add new draft Risk rows or find nothing new to propose; existing
    # confirmed/dismissed risks are structurally untouched either way (see
    # risk_register.scenario_engine's dedup rule).
    created = generate_draft_risks(organisation)
    if created:
        messages.success(
            request,
            f"Generated {len(created)} new AI-suggested risk(s) for review.",
        )
    else:
        messages.success(
            request,
            "Risk generation completed but did not propose any new risks. "
            "This can happen if there are no confirmed key assets yet, or "
            "every applicable scenario for your confirmed assets and "
            "baseline answers was already generated previously.",
        )

    return redirect("risk_register:list", organisation_id=organisation.id)


@login_required
@require_capability()
def foundations_risks_actions(request, organisation_id):
    """
    Stage 5 "Your Risks & Actions" (M008C-WI3, docs/design/
    M008-FREE-TEXT-REPLACEMENT-REGISTER.md's parent dispatch) - a
    deterministic, zero-AI guided summary of the organisation's current
    risks, split into risks CONFIRMED by the organisation's current
    baseline answers vs. risks whose underlying control answer still needs
    confirming.

    GET auto-generation judgement call (documented in this dispatch's
    report, not merely in code): calling `generate_draft_risks` on a bare
    GET is deliberate here, same as this module's own `risk_generate`
    dispatches today - it is dedup-safe and deterministic
    (`risk_register.scenario_engine`'s own "never mutate an existing Risk"
    guarantee), so a GET can never create a *duplicate* row or silently
    overwrite anything a customer already reviewed. It DOES mean a GET can
    create new rows the customer has not explicitly asked for via a
    button-press, which is a real (if narrow) deviation from "GET must
    never change persisted state" - accepted here because every row it can
    possibly create is already fully entailed by facts the customer has
    already confirmed elsewhere (their own confirmed key assets and
    baseline answers), so nothing is asserted here that was not already
    true; nothing is "new truth", only a new persisted VIEW of existing
    truth. An alternative (an explicit "Refresh risks" button, mirroring
    `risk_generate`'s own POST-only convention) is equally defensible and
    was not chosen only to keep Stage 5 a single guided page with no extra
    click required to see current risks, matching Stage 1-4's "answer and
    move on" pacing (docs/design/M008C-UX-FLOW-DESIGN.md).

    Every risk is re-classified LIVE against the organisation's CURRENT
    canonical baseline answers (`risk_register.scenario_engine.
    current_trigger_variant`) - never trusting anything cached on the
    `Risk` row itself, which could be stale if a baseline answer changed
    after this risk was generated. A risk whose trigger has resolved away
    entirely (every relevant control now answers something other than a
    trigger state) is excluded from both groups and from the headline
    count - see `current_trigger_variant`'s own docstring for why that is
    the safe behaviour, not a silent misclassification as confirmed.
    """
    organisation = get_member_organisation_or_404(request.user, organisation_id)
    request.session["current_organisation_id"] = str(organisation.id)

    generate_draft_risks(organisation)

    draft_risks = (
        Risk.objects.filter(organisation=organisation, status=Risk.STATUS_DRAFT_AI_SUGGESTED)
        .select_related("key_asset")
    )

    confirmed_risks = []
    needing_confirmation = []
    for risk in draft_risks:
        variant = current_trigger_variant(risk)
        if variant is None:
            # No longer a live risk against current facts - exclude from
            # both groups and the headline count (see this view's own
            # docstring).
            continue
        if variant == VARIANT_NO:
            confirmed_risks.append(risk)
        else:
            unconfirmed_keys = current_unconfirmed_control_keys(risk)
            needing_confirmation.append(
                {
                    "risk": risk,
                    "question_links": [
                        {
                            "control_key": key,
                            "title": stage4.QUESTION_COPY.get(key, {}).get("title", key),
                            "url": reverse(
                                "security_baseline:foundations_question",
                                kwargs={"organisation_id": organisation.id, "question_key": key},
                            ),
                        }
                        for key in unconfirmed_keys
                    ],
                }
            )

    confirmed_count = len(confirmed_risks)
    needing_confirmation_count = len(needing_confirmation)
    total_count = confirmed_count + needing_confirmation_count

    # Central Architecture's own exact wording, adopted verbatim (this
    # dispatch's instructions): "3 security risks identified · 2 things
    # still need confirming", with the real counts substituted - same
    # "verbatim, no pluralisation branching" discipline as
    # `security_baseline.stage4.progress_copy`.
    headline = (
        f"{total_count} security risks identified · "
        f"{needing_confirmation_count} things still need confirming"
    )

    return render(
        request,
        "risk_register/foundations_risks_actions.html",
        {
            "organisation": organisation,
            "headline": headline,
            "confirmed_risks": confirmed_risks,
            "needing_confirmation": needing_confirmation,
            "confirmed_count": confirmed_count,
            "needing_confirmation_count": needing_confirmation_count,
            "total_count": total_count,
        },
    )


@login_required
@require_capability()
def risk_detail(request, organisation_id, risk_id):
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)
    return render(
        request,
        "risk_register/detail.html",
        {
            "organisation": organisation,
            "risk": risk,
            # M008C-WI3: a human-readable label for whatever is currently
            # stored in `rationale`/`proposed_treatment` - a real catalogue
            # code (post-WI3 edit), or a legacy/provenance sentence
            # (pre-WI3 edit, or scenario-engine-written text never
            # touched by a customer edit) which these two `.get(...,
            # risk.<field>)` calls correctly fall back to displaying
            # verbatim, exactly as `RiskEditForm`'s own legacy-value
            # handling does.
            "rationale_label": RATIONALE_CODE_LABELS.get(risk.rationale, risk.rationale),
            "proposed_treatment_label": TREATMENT_CATEGORY_LABELS.get(
                risk.proposed_treatment, risk.proposed_treatment
            ),
        },
    )


@login_required
@require_capability()
def risk_edit(request, organisation_id, risk_id):
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(
            request,
            "Only AI-suggested draft risks can be edited here. This risk has "
            "already been confirmed or dismissed.",
        )
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    if request.method == "POST":
        form = RiskEditForm(request.POST, instance=risk)

        # Snapshot the pre-change value of every editable field now, before
        # `form.is_valid()` is even called below - not merely before
        # `form.save()`. Django's `ModelForm._post_clean()` (invoked from
        # inside `full_clean()`, which `is_valid()` triggers) already calls
        # `construct_instance()` and sets the new field values directly
        # onto `self.instance` - i.e. onto `risk` - as a side effect of
        # validation itself, well before `.save()` persists anything. A
        # snapshot taken after `is_valid()` would already see the *new*
        # values on `risk`, not the "before" this event needs (Learning
        # Signal Capture Addendum §3/§7 - the same discipline
        # security_baseline.services.save_baseline_answers already uses for
        # control_answer_changed, where the previous answer is read from
        # the database before the write, not from a form-mutated instance).
        previous_values = {
            field: getattr(risk, field) for field in _RISK_EDIT_DELTA_FIELDS
        }

        if form.is_valid():
            with transaction.atomic():
                form.save()

                delta = {}
                for field in _RISK_EDIT_DELTA_FIELDS:
                    new_value = getattr(risk, field)
                    if new_value != previous_values[field]:
                        delta[field] = {
                            "previous": previous_values[field],
                            "new": new_value,
                        }

                if delta:
                    record_event(
                        organisation,
                        ActivityEvent.EVENT_RISK_SUGGESTION_EDITED,
                        actor=request.user,
                        related_object_type="risk",
                        related_object_id=str(risk.id),
                        metadata=delta,
                    )

            messages.success(request, f'Risk "{risk.title}" updated.')
            return redirect(
                "risk_register:detail", organisation_id=organisation.id, risk_id=risk.id
            )
        messages.error(request, "The risk could not be saved. Please check the errors below.")
    else:
        form = RiskEditForm(instance=risk)

    return render(
        request,
        "risk_register/form.html",
        {
            "organisation": organisation,
            "risk": risk,
            "form": form,
            # M008C-WI3: lets form.html show the scenario's own
            # `suggested_treatment` text read-only alongside the new
            # `proposed_treatment` treatment-category choice - `None` for a
            # risk whose `scenario_id` doesn't resolve (retired/manually
            # created), which the template already guards with `{% if %}`.
            "risk_scenario": CATALOGUE_BY_ID.get(risk.scenario_id),
        },
    )


@login_required
@require_capability()
def risk_confirm(request, organisation_id, risk_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(request, "Only a draft AI suggestion can be confirmed.")
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    risk.status = Risk.STATUS_CONFIRMED
    risk.confirmed_by = request.user
    risk.confirmed_at = timezone.now()
    risk.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
    messages.success(request, f'Risk "{risk.title}" confirmed into the risk register.')
    return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)


@login_required
@require_capability()
def risk_dismiss(request, organisation_id, risk_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    organisation, risk = _get_member_risk_or_404(request.user, organisation_id, risk_id)

    if risk.status != Risk.STATUS_DRAFT_AI_SUGGESTED:
        messages.error(request, "Only a draft AI suggestion can be dismissed.")
        return redirect("risk_register:detail", organisation_id=organisation.id, risk_id=risk.id)

    with transaction.atomic():
        risk.status = Risk.STATUS_DISMISSED
        risk.dismissed_by = request.user
        risk.dismissed_at = timezone.now()
        risk.save(update_fields=["status", "dismissed_by", "dismissed_at", "updated_at"])

        record_event(
            organisation,
            ActivityEvent.EVENT_RISK_SUGGESTION_DISMISSED,
            actor=request.user,
            related_object_type="risk",
            related_object_id=str(risk.id),
            metadata={
                "title": risk.title,
                "impact": risk.impact,
                "likelihood": risk.likelihood,
                "risk_band": risk.risk_band,
            },
        )

    messages.success(request, f'Risk "{risk.title}" dismissed.')
    return redirect("risk_register:list", organisation_id=organisation.id)
