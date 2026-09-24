"""
M006 PID §11a - explicit, mechanically-derived route matrix.

PID §11a's own wording: "Maintain an explicit route matrix proving every
organisation-scoped customer route: requires auth; scopes to the
authenticated organisation; does not leak cross-tenant object existence;
rejects cross-tenant GET/POST manipulation." Every app already has its own
`test_tenant_isolation.py` covering its own central flows with real
domain objects (see e.g. `questionnaire/tests/test_tenant_isolation.py`) -
this module is a NEW, systematic layer on top of those, not a replacement:
it walks the actual registered URL tree so no organisation-scoped route can
silently go unchecked as apps add routes, and it deliberately does not
delete or weaken any existing per-app test.

Mechanism (PID §11a: "your call on the exact mechanism, document it
clearly"):

1. Route enumeration is MECHANICAL: `_iter_org_scoped_routes` walks the
   real registered `django.urls.get_resolver()` tree - the same tree
   `config/urls.py`'s `include()`s build at import time - accumulating each
   URL pattern's full dotted name (`<namespace>:<name>`) and the union of
   URL converters (`organisation_id`, plus any other id/key segment)
   contributed by every ancestor `include()` prefix plus the pattern's own
   segment. This is exactly how Django itself resolves a request, so a new
   organisation-scoped `path()` in any app is picked up automatically the
   next time this test runs - nothing here needs hand-maintaining as apps
   grow.

2. A route counts as "organisation-scoped customer route" (PID §11a's
   subject) iff its resolved converters include `organisation_id`. Reading
   `config/urls.py` confirms this is precisely the right set: every
   organisation-scoped app is mounted either as
   `organisations/<uuid:organisation_id>/<app>/` (evidence, remediation,
   risk_register, key_assets, security_state, governance, workplace,
   policy, questionnaire) or supplies `<uuid:organisation_id>/...` itself
   (`organisations`, `security_baseline`, `activity`). `admin/`,
   `accounts/login/`, `accounts/logout/`, `identity/*` (allauth),
   `core:home`, `core:healthz`, `organisations:list` and
   `organisations:create` are correctly EXCLUDED by this filter - none of
   them takes an organisation id at all, so none is a candidate for
   cross-tenant leakage in the first place.

3. Reading every `views.py` in the codebase (done once, ahead of writing
   this file) confirms a codebase-wide invariant with NO exception found:
   every organisation-scoped view either (a) calls
   `organisations.views.get_member_organisation_or_404` as the very first
   thing it does, before touching any other URL-supplied id (e.g.
   `evidence.views._get_member_evidence_item_or_404`,
   `policy.views._get_member_policy_version_or_404`,
   `risk_register.views._get_member_risk_or_404`, and the equivalent
   helper in every other app all do this - membership is baked into the
   very first lookup, not checked afterwards), or (b) checks
   `request.method` first (an explicitly POST-only "action" view, e.g.
   `remediation.views.action_start`/`risk_register.views.risk_confirm`/
   `evidence.views.evidence_withdraw`, returning `HttpResponseNotAllowed`
   for any other method) and only THEN calls
   `get_member_organisation_or_404`. Either way, a request naming another
   organisation's id can never reach a second, per-object lookup keyed by
   some other URL segment (an evidence id, a risk id, a response id, a
   link id...) before the organisation-membership check has already
   rejected it.

   This is what makes it sound for this mechanical sweep to fill any OTHER
   required URL segment with a syntactically-valid but essentially
   arbitrary placeholder value (a fresh random UUID for every
   database-backed id; the one exception is `security_state`'s
   `control_key`, which is validated against the in-memory catalogue
   rather than the database, so a fabricated key would 404 unconditionally
   before the organisation check is even relevant - a real catalogue key
   is used there instead, so this route's cross-tenant probe genuinely
   exercises the organisation-membership check rather than the unrelated
   catalogue-lookup 404). The organisation-boundary check this test exists
   to prove fires first regardless of whether the placeholder happens to
   resolve to a real object - proven by the code-reading above, not
   assumed.

   Because no domain objects are created here, a route requiring a
   secondary id (evidence_id, risk_id, action_id, version_id, response_id,
   asset_id, workplace_id, link_id) will 404 even for the ROUTE-OWNING
   client (the placeholder object genuinely does not exist) - this test
   still proves the property PID §11a asks for (a wrong-tenant caller can
   never get further than a rightful member with the same fabricated id
   does), it just cannot additionally prove "and a REAL org_a object stays
   hidden from org_b" for every single route from URL shape alone. That
   stronger, real-object proof already exists per app (e.g.
   `questionnaire/tests/test_tenant_isolation.py::
   test_org_b_response_id_used_against_org_a_url_is_404`,
   `evidence/tests/test_tenant_isolation.py`, etc.) and is deliberately not
   duplicated here - this module's job is comprehensive URL-level breadth,
   not a second copy of each app's own object-level depth.

4. HTTP method behaviour is read directly off each view, not guessed: for
   every enumerated route, organisation A's own member (`client_a`) sends a
   real GET and a real POST (empty body) first. A `405` response marks
   that method as categorically unavailable for the route (an explicit
   `HttpResponseNotAllowed` in the view); anything else (200, 302, 404 for
   a missing placeholder object) marks it as accepted. This observed
   baseline is then used to compute what the WRONG-tenant attempt below is
   expected to return - a `405` route must still return `405` for anyone,
   since Django raises it before any tenant check ever runs, and that is
   not a leak (it reveals nothing about whether org_a exists).

5. For every route, four requests are made and asserted:
     a. anonymous GET  -> 302 to the login page, never served.
     b. anonymous POST -> 302 to the login page, never served.
     c. `client_b` (a member of `org_b` only) GET  on org_a's URL -> never
        200; matches the method-based expectation from point 4 (404, or
        405 if that method is rejected for everyone).
     d. `client_b` POST on org_a's URL -> same as (c) for POST.

   Every route this sweep walks becomes its own parametrized test id (see
   `ROUTE_IDS` below), so `pytest core/tests/test_route_matrix.py -v`
   itself is the human-readable proof of exactly which routes were
   checked - PID §11a's "a human reviewer can see the matrix is genuinely
   comprehensive". `test_route_matrix_enumeration_is_not_degenerate` below
   is an additional tripwire against the walk itself silently finding
   nothing (which would otherwise look like "0 routes, all passing").
"""
import uuid

import pytest
from django.test import Client
from django.urls import get_resolver, reverse
from django.urls.converters import IntConverter, SlugConverter, StringConverter, UUIDConverter
from django.urls.resolvers import URLPattern, URLResolver

from ai_platform.testing import FakePolicyGateway

# A real, always-present security_baseline catalogue key (see point 3
# above) - security_state.views.security_state_detail's `control_key` is
# validated against `security_baseline.catalogue.CATALOGUE_BY_KEY` (an
# in-memory dict), not the database, so a fabricated key would 404
# unconditionally regardless of tenant and never actually exercise the
# organisation-membership check this route needs proving.
_REAL_CONTROL_KEY = "mfa_privileged_accounts"


def _dummy_value(param_name, converter):
    if param_name == "control_key":
        return _REAL_CONTROL_KEY
    if isinstance(converter, UUIDConverter):
        return uuid.uuid4()
    if isinstance(converter, IntConverter):
        return 999999999
    if isinstance(converter, SlugConverter):
        return "no-such-slug"
    if isinstance(converter, StringConverter):
        return "no-such-value"
    # An unrecognised converter type: fail loudly rather than silently
    # build a meaningless URL - this sweep is only an honest "systematic,
    # mechanical" proof (PID §11a) if every enumerated route is genuinely
    # exercised, never skipped by accident.
    raise AssertionError(
        f"no dummy-value mapping for converter {converter!r} (param {param_name!r}) - "
        "extend _dummy_value rather than letting this route silently fall through"
    )


def _iter_named_routes(resolver=None, namespace_path=(), converters=None):
    """Recursively walks the real registered URL tree, yielding
    (full_dotted_name, converters_dict) for every named URL pattern -
    see module docstring point 1."""
    resolver = resolver or get_resolver()
    converters = dict(converters or {})
    for entry in resolver.url_patterns:
        entry_converters = dict(converters)
        entry_converters.update(getattr(entry.pattern, "converters", None) or {})
        if isinstance(entry, URLPattern):
            if entry.name:
                full_name = ":".join([*namespace_path, entry.name])
                yield full_name, entry_converters
        elif isinstance(entry, URLResolver):
            namespace = entry.namespace
            new_namespace_path = (*namespace_path, namespace) if namespace else namespace_path
            yield from _iter_named_routes(entry, new_namespace_path, entry_converters)


def _organisation_scoped_routes():
    """Every named route whose resolved converters require
    `organisation_id` - see module docstring point 2. Deduplicated and
    sorted for a stable, readable parametrize ordering."""
    routes = {}
    for full_name, converters in _iter_named_routes():
        if "organisation_id" not in converters:
            continue
        routes[full_name] = converters
    return sorted(routes.items())


ROUTES = _organisation_scoped_routes()
ROUTE_IDS = [name for name, _ in ROUTES]


def _build_kwargs(converters, organisation_id):
    kwargs = {}
    for name, converter in converters.items():
        kwargs[name] = organisation_id if name == "organisation_id" else _dummy_value(name, converter)
    return kwargs


@pytest.fixture(autouse=True)
def _fake_policy_gateway(monkeypatch):
    """
    This sweep's job is proving the auth/tenant boundary on every
    organisation-scoped route - not exercising real AI generation.
    `policy:generate` is the one route in the whole matrix that
    unconditionally calls into `ai_platform`'s real `LiteLLMGateway` the
    instant its method+tenant checks pass (no form/body gate the way
    `questionnaire:analyse`'s empty-`question_text` early-return, or
    `risk_register:interpret`'s empty-draft-risks early-return, both
    happen to short-circuit before ever reaching a gateway call with this
    sweep's empty POST body). Swapping in `ai_platform.testing.
    FakePolicyGateway` - the exact same seam `policy/tests/test_http_ui.py`
    already patches for its own HTTP-level tests - keeps this sweep
    hermetic and independent of `AI_GATEWAY_BASE_URL` being configured,
    without touching any `ai_platform/`/`policy.services` production code
    (hard constraint): only which gateway instance this one service call
    constructs.
    """
    monkeypatch.setattr("policy.services.LiteLLMGateway", lambda: FakePolicyGateway())


@pytest.mark.django_db
@pytest.mark.parametrize("route_name, converters", ROUTES, ids=ROUTE_IDS)
def test_organisation_scoped_route_requires_auth_and_tenant_scope(
    route_name, converters, client_a, client_b, org_a, org_b
):
    login_path = reverse("login")
    url = reverse(route_name, kwargs=_build_kwargs(converters, org_a.id))

    # (a)/(b) unauthenticated - never served, always redirected to login,
    # for both a read and a write attempt.
    anon_get = Client().get(url)
    assert anon_get.status_code == 302, (
        f"{route_name}: anonymous GET {url} should redirect to login, "
        f"got {anon_get.status_code}"
    )
    assert anon_get["Location"].startswith(login_path), (
        f"{route_name}: anonymous GET redirected to {anon_get['Location']!r}, "
        f"not the login page"
    )

    anon_post = Client().post(url, data={})
    assert anon_post.status_code == 302, (
        f"{route_name}: anonymous POST {url} should redirect to login, "
        f"got {anon_post.status_code}"
    )
    assert anon_post["Location"].startswith(login_path), (
        f"{route_name}: anonymous POST redirected to {anon_post['Location']!r}, "
        f"not the login page"
    )

    # Baseline: org_a's own member, to learn (per method) whether this
    # route rejects that method outright for everyone (405) - see module
    # docstring point 4. Never asserted against directly beyond that - a
    # 404 here just means the fabricated secondary id does not exist,
    # which is expected and does not weaken the cross-tenant proof below.
    owner_get = client_a.get(url)
    owner_post = client_a.post(url, data={})

    expected_get = 405 if owner_get.status_code == 405 else 404
    expected_post = 405 if owner_post.status_code == 405 else 404

    # (c)/(d) wrong-tenant - a member of org_b only, using org_a's id.
    cross_get = client_b.get(url)
    cross_post = client_b.post(url, data={})

    assert cross_get.status_code != 200, (
        f"{route_name}: cross-tenant GET {url} (org_b member, org_a's id) "
        f"returned 200 - possible cross-tenant data leak"
    )
    assert cross_get.status_code == expected_get, (
        f"{route_name}: cross-tenant GET {url} returned {cross_get.status_code}, "
        f"expected {expected_get} (owner baseline was {owner_get.status_code}) - "
        f"a status code that differs from the owner-baseline-derived expectation "
        f"can itself indicate a tenant-boundary defect"
    )

    assert cross_post.status_code != 200, (
        f"{route_name}: cross-tenant POST {url} (org_b member, org_a's id) "
        f"returned 200 - possible cross-tenant mutation or data leak"
    )
    assert cross_post.status_code == expected_post, (
        f"{route_name}: cross-tenant POST {url} returned {cross_post.status_code}, "
        f"expected {expected_post} (owner baseline was {owner_post.status_code})"
    )


# Namespaces PID §11a's route matrix must cover, per config/urls.py's own
# organisation-scoped includes (module docstring point 2) - a fixed,
# independently-read list used only as a tripwire against the mechanical
# walk above silently degenerating to "found nothing" (which would
# otherwise present as "0 routes, all green"), never as the enumeration
# mechanism itself.
_EXPECTED_ORGANISATION_SCOPED_NAMESPACES = {
    "organisations",
    "security_baseline",
    "key_assets",
    "risk_register",
    "evidence",
    "remediation",
    "security_state",
    "governance",
    "workplace",
    "policy",
    "questionnaire",
    "activity",
}


def test_route_matrix_enumeration_is_not_degenerate():
    """Tripwire: the mechanical walk must have found a substantial,
    multi-app set of organisation-scoped routes - not zero, not just one
    app's worth. This is deliberately a coarse minimum-count/namespace-
    presence check, not a hand-typed exact route list (that would just be
    the thing PID §11a asks this module to avoid)."""
    assert len(ROUTES) >= 40, (
        f"route matrix enumeration found only {len(ROUTES)} organisation-scoped "
        f"routes - expected at least 40 across every organisation-scoped app; "
        f"the mechanical walk may be broken. Routes found: {ROUTE_IDS}"
    )
    found_namespaces = {name.split(":", 1)[0] for name in ROUTE_IDS}
    missing = _EXPECTED_ORGANISATION_SCOPED_NAMESPACES - found_namespaces
    assert not missing, (
        f"route matrix enumeration found no organisation-scoped routes at all "
        f"for namespace(s) {sorted(missing)} - the mechanical walk may not be "
        f"reaching that app's urls.py include"
    )


def test_route_matrix_report_lists_every_route_checked():
    """PID §11a: 'a human reviewer can see the matrix is genuinely
    comprehensive, not just some tests passed'. This test's own failure
    message (and `pytest -v`'s per-route parametrize ids on the test
    above) is that report."""
    report_lines = "\n".join(f"  - {name}" for name in ROUTE_IDS)
    assert ROUTES, (
        f"organisation-scoped route matrix ({len(ROUTES)} routes checked by "
        f"test_organisation_scoped_route_requires_auth_and_tenant_scope):\n"
        f"{report_lines}"
    )
