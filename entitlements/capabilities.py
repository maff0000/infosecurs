"""
Central server-side entitlement decision (PID §9).

`has_capability` is the ONE function every route guard (WI3's job to wire
onto every existing view) and the navigation service (WI2's job) must
consume - never a scattered `if request.session["package_tier"] == 2:` in
an individual view/template. This module also owns the code-governed route-
namespace -> `ProductArea.code` map (§9.2): a plain Python dict, not
executable/dynamic database configuration.

Deliberately NOT wired onto any existing view in this WI - see the PID
dispatch's own explicit boundary: WI1 builds and proves this function
correct in isolation; WI3 applies it.
"""
from __future__ import annotations

from entitlements.models import ProductArea
from entitlements.session import Invalid, get_validated_context

# Route namespace -> stable ProductArea.code (PID §9.2). Every entry here
# was read off each app's own config/urls.py mounting + urls.py app_name,
# the same way core.context_processors._NAV_SECTION_BY_NAMESPACE was built
# by hand rather than inferred from naming conventions.
ROUTE_NAMESPACE_TO_CAPABILITY: dict[str, str] = {
    "questionnaire": "customer_assurance",
    "security_state": "security",
    "security_baseline": "security",
    "key_assets": "security",
    "risk_register": "security",
    "evidence": "security",
    "remediation": "security",
    "policy": "policies",
    "governance": "company",
    "workplace": "company",
    "activity": "company",
}

# `organisations` splits by `url_name`, not just namespace - mirroring the
# existing precedent in `core.context_processors._ORGANISATIONS_URL_NAME_TO_SECTION`
# for the exact same reason: `list`/`create` are the pre-organisation-
# selection pages (no capability check applies - a user with zero
# organisations must still reach them) while `detail` (Overview/Home) and
# `profile`/`organisation_hub` (Company) mean different capabilities.
ORGANISATIONS_URL_NAME_TO_CAPABILITY: dict[str, str] = {
    "detail": "home",
    "profile": "company",
    "organisation_hub": "company",
    # M007-WI5 (PID §15): the new Foundations workspace route. `foundations`
    # (the ProductArea.code) and `foundations` (this url_name) are the same
    # string by coincidence, not a shortcut generalised elsewhere in this
    # map - every other entry here maps a DIFFERENT url_name to its
    # capability code.
    "foundations": "foundations",
}


def capability_for_route(namespace: str, url_name: str | None = None) -> str | None:
    """Returns the `ProductArea.code` a given route namespace/url_name maps
    to, or `None` if this map has no opinion (e.g. `login`, `healthz`,
    admin, or `organisations:list`/`organisations:create`) - `None` is not
    itself an allow/deny decision, it is "this route carries no M007
    capability check"; a future caller (WI3) that wants default-deny for
    *every* route must treat an unmapped route as its own separate policy
    decision, not something this function decides."""
    if namespace == "organisations":
        return ORGANISATIONS_URL_NAME_TO_CAPABILITY.get(url_name)
    return ROUTE_NAMESPACE_TO_CAPABILITY.get(namespace)


def has_capability(request, capability_code: str) -> bool:
    """
    Default-deny (PID §9.1): every failure mode - missing/malformed
    session, unknown/inactive `ProductArea`, insufficient tier - returns
    `False`. Never raises out to the caller for an expected denial path.

    Deliberately takes only `request` and a bare `capability_code` - never
    an organisation/tenant argument. Package entitlement and tenant
    authorisation are separate gates (PID §9.3): this function proves only
    "does this session's package tier satisfy this capability's minimum
    tier", nothing about which organisation is involved. A Tier-3 session
    for Organisation A must still go through
    `organisations.views.get_member_organisation_or_404` (or equivalent)
    before touching Organisation B's data - that check does not exist here
    and must never be reimplemented here.
    """
    context = get_validated_context(request)
    if isinstance(context, Invalid):
        return False

    try:
        area = ProductArea.objects.active().get(code=capability_code)
    except ProductArea.DoesNotExist:
        return False

    return context.package_tier >= area.min_package_tier
