"""
M007-WI3 route/capability guard (PID §9, §25).

`require_capability` is the ONE view decorator every organisation-scoped
view in this codebase is wrapped in. It closes the gap WI1/WI2 deliberately
left open: `entitlements.capabilities.has_capability` and
`entitlements.session` were built and proven correct in isolation, and
WI2's navigation sidebar already consumes `has_capability` to decide what to
*show* - but until this WI, nothing called `has_capability` to decide what a
direct request may *reach*. Hiding a sidebar item was never access control
(PID §9's own words) - this decorator is that access control.

Composition this decorator proves, request by request, stacked on top of
what each app already does for itself:

    authenticated                              (@login_required, already
                                                 applied to every one of
                                                 these views - this
                                                 decorator assumes it ran
                                                 first; see the ordering note
                                                 below)
    AND valid session context                  (entitlements.session,
                                                 fail-closed - WI1)
    AND package entitlement                    (entitlements.capabilities.
                                                 has_capability - WI1, wired
                                                 by THIS module)
    AND active organisation alignment          (THIS module - new)
    AND current tenant membership              (organisations.views.
                                                 get_member_organisation_or_404
                                                 - existing, reused, ALSO
                                                 re-checked here - see
                                                 "why a second membership
                                                 query" below)
    AND object belongs to tenant               (each view's own per-object
                                                 scoped query, e.g.
                                                 key_assets._get_member_key_asset_or_404
                                                 - existing, untouched,
                                                 still runs after this
                                                 decorator returns control
                                                 to the view)

Decorator ordering (every decorated view in this codebase follows this
exact stacking - outermost first):

    @login_required
    @require_capability()
    def some_view(request, organisation_id, ...):
        ...

`login_required`'s wrapper executes first and denies an unauthenticated
request before this decorator ever runs, so `request.user` is always a real
authenticated user by the time `require_capability`'s wrapper executes.
Reversing the order would let an unauthenticated request reach this
decorator first - `get_validated_context`/`has_capability` would still
correctly deny it (both already fail closed for `AnonymousUser`), but the
membership lookup below would run against `AnonymousUser` needlessly, and
the failure mode would be a confusing 404 (no memberships for an anonymous
user) rather than `login_required`'s own clean redirect-to-login. Keeping
`@login_required` outermost everywhere is simply the correct, conventional
Django layering, not a security-load-bearing requirement of this module.

Why a second, redundant membership-scoped query at this layer
---------------------------------------------------------------
Every decorated view already calls `organisations.views.
get_member_organisation_or_404` (or a per-object wrapper that calls it
internally, e.g. `key_assets._get_member_key_asset_or_404`) as its own first
action. This decorator calls the SAME helper again, before the view body
ever runs. That is a second query, not a second code path - deliberately
NOT eliminated by threading the already-fetched `Organisation` through to
the view (refactoring 72 view signatures to share it is a distinct, larger
change, explicitly out of this dispatch's scope). Two reasons this
redundancy is kept rather than "optimised" away:

  1. Correctness ordering: see "why membership is checked before capability"
     below - this decorator's OWN gates must be provably correct in
     isolation, without relying on a view body it does not control running
     its own check in some particular order or at all.
  2. The active-organisation-alignment step (below) must never rotate the
     session into binding `organisation_id` for an organisation the user is
     not currently a member of - it needs its own proof of membership
     immediately before doing so, not a promise that "the view will check
     this afterwards".

Why membership is checked before the capability check
-------------------------------------------------------
If capability were checked first, a non-member with an insufficient tier
would get `PermissionDenied` (403) while a non-member with a sufficient
tier would fall through to the view's own membership check and get
`Http404` - i.e. the *response itself* would leak, to an attacker who is
not even a member of the target organisation, whether their (possibly
forged) tier happens to be high enough for that route. Checking membership
FIRST means every non-member gets the exact same ordinary `Http404` this
codebase already uses everywhere else for "not a member" (PID's own
"never leaking existence" doctrine - see `get_member_organisation_or_404`'s
docstring), with the capability/tier dimension never even evaluated, let
alone reflected in the response. Only once membership is proven does this
decorator go on to ask the *separate* "does this tier satisfy this
capability" question, whose own denial is `PermissionDenied` (403) -
generic and reason-free (Django's own `templates/403.html`, carrying no
message), matching PID's "never distinguishing wrong tier from not a
member" requirement: the two independent gates never produce a response an
attacker probing either dimension can use to tell which one denied them.

Why an Invalid session context redirects to login rather than 403/404
-------------------------------------------------------------------------
An authenticated Django user with a missing/malformed/tampered
`infosecurs_context` (PID §6.4's `Invalid` - wrong schema version, subject
mismatch, out-of-range tier, etc) is a DIFFERENT failure mode from "valid
session, wrong tier" or "valid session, not a member": there is no
`package_tier`/`package_code`/`auth_source` this decorator could trust
enough to re-issue a realigned context from, and `has_capability` would
correctly return `False` for it anyway (it also calls
`get_validated_context` and treats `Invalid` as deny) - so falling through
to the ordinary 403 path would still be *safe*, but would leave the user
stuck: every subsequent request would fail the exact same way forever,
with no path back to a working session. Central Architecture's own
suggested resolution (PID dispatch) is followed here: redirect to the login
page. This does not silently grant anything - `django.contrib.auth.views.
redirect_to_login` is the exact helper `login_required` itself uses, so the
response an unauthenticated visitor gets and the response an authenticated-
but-invalid-context visitor gets are the same shape. It genuinely recovers
the user (logging in again fires `entitlements.signals.
issue_context_on_login`, issuing a fresh, valid context) rather than
trapping them behind a permanent, unrecoverable 403. See
`entitlements/tests/test_decorators.py`'s fail-closed-invalid-context tests
for the mechanical proof that this path never falls through to granting
access.

`enforce_capability_gate` (below) - the reusable core, extracted M009B
Increment 1 (WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2.6)
---------------------------------------------------------------------------
This module's own three gates below "tenant membership" - invalid-context
redirect, active-organisation alignment, the capability/tier decision
itself - are not unique to `require_capability`'s own `wrapped_view`: WO
§2.6 requires `questionnaire.upload_handler.
QuestionnaireUploadSizeGuardMiddleware.process_view` to make the EXACT same
decision, for the same request, inside a pipeline-level `process_view`
hook rather than a view decorator (a hook that must run its own membership
check before the Assurance Readiness check, and - this increment's fix -
its own entitlement check between the two, since `require_capability`
itself never runs until Django calls the view function, which is always
AFTER every middleware's `process_view` hook has already returned).
`enforce_capability_gate` is that reusable core - called by `wrapped_view`
below AND by that middleware hook - so this decision exists in exactly one
place, never two copies that could silently drift apart. It deliberately
does NOT perform the membership check itself: both call sites already have
their own, earlier, independent proof of membership (this decorator's own
`get_member_organisation_or_404` call below; the hook's own identical call)
before this function ever runs - see "why a second, redundant
membership-scoped query at this layer" above for why that is correct, not
an oversight.
"""
from __future__ import annotations

import functools

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from entitlements.capabilities import capability_for_route, has_capability
from entitlements.session import Invalid, get_validated_context, issue_context

# `organisations.views` is deliberately NOT imported at module level here:
# `organisations/views.py` itself imports `entitlements.decorators` (to
# decorate its own `organisation_detail`/`organisation_hub`/
# `organisation_profile`) BEFORE it defines
# `get_member_organisation_or_404` in that same module - a top-level
# `from organisations.views import get_member_organisation_or_404` here
# would therefore be a circular import, failing with "partially
# initialized module" the moment either module is imported first. Deferring
# the import to inside `wrapped_view` (below) resolves it at CALL time,
# once both modules have fully finished executing - this codebase's own
# established way of avoiding the same class of cycle (e.g.
# `key_assets.views`/`policy.views`/etc. import `organisations.views` at
# their own module level without issue, because none of THEM are imported
# back by `organisations.views` itself; `entitlements.decorators` is the
# one module `organisations.views` also needs).


def enforce_capability_gate(request, organisation_id, capability_code=None):
    """
    The reusable core of `require_capability`'s own entitlement decision -
    see this module's docstring ("`enforce_capability_gate` - the reusable
    core") for why this exists as its own function and who calls it.

    PRECONDITION the caller must already have proven, independently, before
    calling this: `request.user` is authenticated AND is a current member
    of `organisation_id` (this function performs no membership check of its
    own - see the module docstring). Calling this for a non-member or an
    anonymous user is a caller bug, not something this function guards
    against.

    Returns `None` if the capability check passes - the caller proceeds.
    Returns an `HttpResponse` (a redirect to the login page) if the
    session context is missing/malformed/tampered (`Invalid`) - the caller
    MUST return this response immediately, exactly as `wrapped_view` does
    below, never fall through to anything readiness/capability-derived.
    Raises `django.core.exceptions.PermissionDenied` - generic, reason-free
    (see module docstring: this genericness is load-bearing) - if the
    session is valid but the resolved capability's tier requirement is not
    met. Raises `ImproperlyConfigured` if `capability_code` is `None` and
    `request.resolver_match`'s namespace/url_name has no capability
    mapping (a programming-time error, not a request-time deny).
    """
    # Fail-closed handling of a missing/malformed/tampered session context
    # (PID §6.4) - see this module's docstring for why this is a
    # redirect-to-login, never a silent fall-through to the ordinary
    # capability-denied path, and never any access.
    context = get_validated_context(request)
    if isinstance(context, Invalid):
        return redirect_to_login(request.get_full_path())

    # Active organisation alignment (PID §6.5/§9's new gate this WI adds).
    # `organisation_id` may be a `uuid.UUID` off the URL converter;
    # `context.organisation_id` is either `None` (no active organisation
    # yet - e.g. straight after a real login) or the string `issue_context`
    # itself always stores. Re-issuing preserves the EXACT tier/code/
    # auth_source the already-validated context carries - this step only
    # ever changes which organisation the session is bound to, never what
    # package tier it grants - and reuses `issue_context`'s own built-in
    # session-key rotation (PID §6.5/§19.1) rather than rotating
    # separately. Evaluating the capability check against THIS caller's
    # own `organisation_id` (never whatever organisation happened to
    # already be active in session) is exactly why this alignment step
    # must run before `has_capability` is ever called, for every caller.
    if context.organisation_id != str(organisation_id):
        issue_context(
            request,
            request.user,
            package_tier=context.package_tier,
            package_code=context.package_code,
            auth_source=context.auth_source,
            organisation_id=organisation_id,
        )

    resolved_code = capability_code
    if resolved_code is None:
        resolver_match = request.resolver_match
        resolved_code = capability_for_route(
            resolver_match.namespace, resolver_match.url_name
        )
    if resolved_code is None:
        resolver_match = request.resolver_match
        raise ImproperlyConfigured(
            "enforce_capability_gate could not resolve a capability code for "
            f"namespace={getattr(resolver_match, 'namespace', None)!r}, "
            f"url_name={getattr(resolver_match, 'url_name', None)!r} - "
            "pass capability_code explicitly, or add a route mapping in "
            "entitlements.capabilities."
        )

    # The one central entitlement decision (PID §9) - re-reads whatever
    # context is now stored (the just-realigned one, if alignment ran
    # above), never a re-derived/hard-coded tier comparison of its own.
    # Generic, reason-free denial (`PermissionDenied` -> Django's existing
    # branded 403.html, carrying no message) - see this module's docstring
    # for why that genericness matters.
    if not has_capability(request, resolved_code):
        raise PermissionDenied

    return None


def require_capability(capability_code=None):
    """
    Decorator factory (PID §9's "one server-side entitlement decision").

    `capability_code`, if given, is used as-is - the explicit-argument shape
    the PID dispatch offers as an alternative to route-derived lookup. Every
    view this WI actually decorates leaves it `None` and relies on
    `entitlements.capabilities.capability_for_route(request.resolver_match.
    namespace, request.resolver_match.url_name)` instead: every organisation-
    scoped route namespace/url_name this codebase has is already present in
    `ROUTE_NAMESPACE_TO_CAPABILITY`/`ORGANISATIONS_URL_NAME_TO_CAPABILITY`
    (WI1), so there is no view left needing the explicit form today - it
    exists so a future route that genuinely cannot be inferred from
    namespace/url_name alone has a documented escape hatch that still goes
    through this exact same decorator and `has_capability` call, never a
    re-derived tier check of its own.

    Must only decorate a view whose URL carries an `organisation_id` kwarg
    (every `<uuid:organisation_id>`-scoped route in this codebase) - raises
    `ImproperlyConfigured` immediately (a programming-time error, not a
    request-time deny) if applied anywhere else, so a future mistake is
    caught the first time the route is exercised (by a test or manually),
    not silently misbehaving in production.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            from organisations.views import get_member_organisation_or_404

            organisation_id = kwargs.get("organisation_id")
            if organisation_id is None:
                raise ImproperlyConfigured(
                    f"require_capability was applied to {view_func.__module__}."
                    f"{view_func.__qualname__}, whose URL does not carry an "
                    "organisation_id - this decorator only guards "
                    "organisation-scoped routes (PID §9)."
                )

            # Tenant membership FIRST (PID §9.3) - before the session
            # context is even read and before capability is evaluated. See
            # this module's docstring for exactly why this ordering, not
            # just "membership matters", is the point: a non-member's
            # response must never vary with their (possibly forged) tier.
            # Raises Http404 (this codebase's existing non-member
            # convention) exactly like the view's own subsequent, separate
            # call to the same helper.
            get_member_organisation_or_404(request.user, organisation_id)

            # Invalid-context redirect, active-organisation alignment, and
            # the capability/tier decision itself - the reusable core also
            # used by `questionnaire.upload_handler.
            # QuestionnaireUploadSizeGuardMiddleware.process_view` (M009B
            # Increment 1). See `enforce_capability_gate`'s own docstring.
            gate_response = enforce_capability_gate(request, organisation_id, capability_code)
            if gate_response is not None:
                return gate_response

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
