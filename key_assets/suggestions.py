"""
Deterministic, non-AI starter key-asset suggestions (PID.md M002 §7.1).

This module reads the existing organisations.OrganisationProfile and applies
plain Python conditionals - there is no AI/LLM call anywhere here, and there
must never be one added: M002 §7.1 is explicit that the starter asset list
is deterministic, not an AI call.

Suggestions are always created as KeyAsset.STATUS_SUGGESTED. Nothing in this
module ever sets a KeyAsset to CONFIRMED - only an explicit customer action
(key_assets.views.key_asset_confirm) does that.
"""
from organisations.models import UNKNOWN, YES, OrganisationProfile

from key_assets.models import (
    CATEGORY_BUSINESS_APPLICATION,
    CATEGORY_CLOUD_SERVICE,
    CATEGORY_ENDPOINT,
    CATEGORY_IDENTITY_OR_PRODUCTIVITY,
    CATEGORY_INFORMATION,
    CRITICALITY_HIGH,
    CRITICALITY_MEDIUM,
    KeyAsset,
)

# primary_cloud_provider is a plain CharField, not a foreign key - "none" is
# a real, valid choice value (organisations.models.CLOUD_PROVIDER_CHOICES),
# distinct from the "not confirmed" UNKNOWN state, and does not itself imply
# a cloud environment asset exists.
CLOUD_PROVIDER_NONE = "none"

CLOUD_PROVIDER_LABELS = {
    "aws": "Amazon Web Services (AWS)",
    "azure": "Microsoft Azure",
    "gcp": "Google Cloud Platform (GCP)",
    "other": "Cloud environment",
}


def starter_suggestion_specs(profile):
    """
    Return the deterministic suggestion specs implied by `profile`.

    A pure function of a single OrganisationProfile - no DB writes, no AI
    call - so the suggestion rules (PID.md M002 §7.1) are directly
    unit-testable against a profile without touching the database.

    Each spec is a dict with: suggestion_key, name, category, description,
    criticality.
    """
    specs = []

    if profile.productivity_platform == "microsoft_365":
        specs.append(
            {
                "suggestion_key": "productivity_microsoft_365",
                "name": "Microsoft 365 / business identity and email",
                "category": CATEGORY_IDENTITY_OR_PRODUCTIVITY,
                "description": (
                    "The organisation's Microsoft 365 tenant - business "
                    "email, identity and core productivity data."
                ),
                "criticality": CRITICALITY_HIGH,
            }
        )
    elif profile.productivity_platform == "google_workspace":
        specs.append(
            {
                "suggestion_key": "productivity_google_workspace",
                "name": "Google Workspace / business identity and email",
                "category": CATEGORY_IDENTITY_OR_PRODUCTIVITY,
                "description": (
                    "The organisation's Google Workspace tenant - business "
                    "email, identity and core productivity data."
                ),
                "criticality": CRITICALITY_HIGH,
            }
        )

    if profile.staff_count is not None and profile.staff_count > 0:
        specs.append(
            {
                "suggestion_key": "employee_endpoints",
                "name": "Employee endpoints",
                "category": CATEGORY_ENDPOINT,
                "description": (
                    "Laptops, desktops and mobile devices staff use to do "
                    "their work."
                ),
                "criticality": CRITICALITY_MEDIUM,
            }
        )

    if profile.primary_cloud_provider not in (UNKNOWN, CLOUD_PROVIDER_NONE):
        label = CLOUD_PROVIDER_LABELS.get(
            profile.primary_cloud_provider, "Cloud environment"
        )
        specs.append(
            {
                "suggestion_key": "primary_cloud_environment",
                "name": f"{label} environment",
                "category": CATEGORY_CLOUD_SERVICE,
                "description": "The organisation's primary cloud environment.",
                "criticality": CRITICALITY_HIGH,
            }
        )

    if profile.develops_hosts_own_software == YES:
        specs.append(
            {
                "suggestion_key": "hosted_application",
                "name": "Hosted application / service",
                "category": CATEGORY_BUSINESS_APPLICATION,
                "description": (
                    "The software/service the organisation develops or "
                    "hosts itself."
                ),
                "criticality": CRITICALITY_HIGH,
            }
        )

    if YES in (
        profile.handles_personal_data,
        profile.handles_confidential_business_data,
        profile.handles_special_category_data,
    ):
        specs.append(
            {
                "suggestion_key": "sensitive_information",
                "name": "Customer / business information",
                "category": CATEGORY_INFORMATION,
                "description": (
                    "Personal, confidential or special-category information "
                    "the organisation handles, per its organisation profile."
                ),
                "criticality": CRITICALITY_HIGH,
            }
        )

    return specs


def ensure_starter_suggestions(organisation):
    """
    Create any deterministic starter KeyAsset suggestions implied by
    `organisation`'s current OrganisationProfile that do not already exist.

    Idempotent, keyed on (organisation, suggestion_key): an asset that was
    already suggested - and may since have been confirmed, edited or
    dismissed - is never recreated. Safe to call on every Key Assets page
    view; a no-op if the organisation has no profile yet.

    Returns the list of newly-created KeyAsset rows (possibly empty).
    """
    try:
        profile = organisation.profile
    except OrganisationProfile.DoesNotExist:
        return []

    existing_keys = set(
        KeyAsset.objects.filter(organisation=organisation)
        .exclude(suggestion_key="")
        .values_list("suggestion_key", flat=True)
    )

    created = []
    for spec in starter_suggestion_specs(profile):
        if spec["suggestion_key"] in existing_keys:
            continue
        asset = KeyAsset.objects.create(
            organisation=organisation,
            status=KeyAsset.STATUS_SUGGESTED,
            **spec,
        )
        created.append(asset)
    return created
