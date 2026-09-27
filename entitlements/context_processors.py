"""
Wires `entitlements.navigation.build_navigation_tree` into every template's
context as `nav_tree` (M007-WI2, PID §4.4/§18).

Deliberately a context processor, not a template tag: `application_shell.
html` is the ONE place the tree is rendered (PID §16.3 - no duplicated menu
DOM/logic across pages), and every one of the 37 organisation-scoped
templates that now extend it reaches this shell via a different app's view
- a context processor guarantees the tree is always present under the
shell's own control, without every view function remembering to compute
and pass it itself.

`organisation_id` comes from `request.resolver_match.kwargs`, never from a
freshly-queried `Organisation` row: every organisation-scoped route is
mounted with a `<uuid:organisation_id>` URL converter (confirmed against
every `include()` in `config/urls.py` - see `entitlements/navigation.py`'s
own docstring), so the id is already sitting on the resolved URL by the
time any context processor runs, with no extra query and no risk of ever
disagreeing with the id the page's own view already tenant-checked via
`organisations.views.get_member_organisation_or_404`. This processor never
performs its own membership check - it only decides "build a nav tree for
this id", using exactly the id the URL itself already carries and the view
has already authorised.
"""
from __future__ import annotations

from entitlements.navigation import build_navigation_tree


def navigation(request):
    """
    Returns `{"nav_tree": [...]}` for an authenticated request whose
    resolved URL carries an `organisation_id` (i.e. every organisation-
    scoped route - PID §3's whole first-level IA only ever makes sense
    once an organisation is selected, matching this dispatch's own finding
    that all 16 seeded `ProductArea.destination_view_name` values resolve
    to such a route). Returns `{}` - not a key with an empty list - for
    everything else (pre-organisation-selection pages, admin, healthz,
    unauthenticated requests), so `{% if nav_tree %}`-style guards in
    non-shell templates simply see nothing, exactly like `core.
    context_processors.active_nav`'s own "unmapped view falls back
    sensibly" precedent.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}

    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return {}

    organisation_id = resolver_match.kwargs.get("organisation_id")
    if organisation_id is None:
        return {}

    return {"nav_tree": build_navigation_tree(request, organisation_id)}
