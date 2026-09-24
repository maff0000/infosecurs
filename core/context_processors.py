PRODUCT_NAME = "Infosecurs"


def product(request):
    """Make the product name available to every template without repeating it."""
    return {"product_name": PRODUCT_NAME}


# ---------------------------------------------------------------------------
# Active primary-navigation section (M006 PID §5).
# ---------------------------------------------------------------------------
# A small, explicit dict from Django app namespace to one of the seven
# primary navigation sections `templates/base.html` renders. Deliberately
# NOT a configurable/database-driven navigation framework (PID §5's
# explicit non-goal) - every entry below was written out by hand after
# reading each app's own urls.py (config/urls.py's includes), not guessed
# or inferred from naming conventions.
NAV_OVERVIEW = "overview"
NAV_SECURITY = "security"
NAV_EVIDENCE = "evidence"
NAV_POLICY = "policy"
NAV_QUESTIONNAIRES = "questionnaires"
NAV_ACTIVITY = "activity"
NAV_ORGANISATION = "organisation"

# Every organisation-scoped app maps to exactly one of the seven sections.
# `organisations` itself is deliberately absent here - its URLs split
# across two different sections depending on url_name, not just namespace,
# so it is handled separately in `_ORGANISATIONS_URL_NAME_TO_SECTION`
# below. Apps with no organisation-scoped customer UI at all (`ai_platform`,
# `identity`) are absent too - there is no primary-nav page to mark active
# for them, so `active_nav` for anything in them correctly falls through to
# None ("everything else defaults sensibly", not a raised error).
_NAV_SECTION_BY_NAMESPACE = {
    "security_baseline": NAV_SECURITY,
    "key_assets": NAV_SECURITY,
    "risk_register": NAV_SECURITY,
    "security_state": NAV_SECURITY,
    "evidence": NAV_EVIDENCE,
    "remediation": NAV_EVIDENCE,
    "policy": NAV_POLICY,
    "questionnaire": NAV_QUESTIONNAIRES,
    "activity": NAV_ACTIVITY,
    "governance": NAV_ORGANISATION,
    "workplace": NAV_ORGANISATION,
}

# The `organisations` namespace splits across two sections depending on
# `url_name` specifically: `detail` is the repurposed Overview page (PID
# §6), while `profile` and the new `organisation_hub` landing page (this
# dispatch's part 4) live under the Organisation section alongside
# governance/workplace. `list` and `create` are deliberately absent - they
# are the pre-organisation-selection pages, which never have `organisation`
# in their own template context at all, so `base.html`'s existing
# `{% if organisation %}` gate already hides the whole primary nav for them
# regardless of what this mapping returns.
_ORGANISATIONS_URL_NAME_TO_SECTION = {
    "detail": NAV_OVERVIEW,
    "profile": NAV_ORGANISATION,
    "organisation_hub": NAV_ORGANISATION,
}


def active_nav(request):
    """
    Injects `active_nav` into every template's context: one of the seven
    section keys above for a page that belongs to the primary navigation,
    or `None` for anything else (login, admin, healthz, the organisation
    list/create pages, or any future view this mapping does not yet know
    about) - an unmapped view falls back to `None` rather than raising, so
    a page nobody has told this processor about simply renders with no nav
    item marked active instead of a 500.
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return {"active_nav": None}

    namespace = resolver_match.namespace
    url_name = resolver_match.url_name

    if namespace == "organisations":
        return {"active_nav": _ORGANISATIONS_URL_NAME_TO_SECTION.get(url_name)}

    return {"active_nav": _NAV_SECTION_BY_NAMESPACE.get(namespace)}
