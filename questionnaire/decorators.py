"""
M009B Increment 1 - `@requires_assurance_readiness`
(WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2.2).

Marks a view function with an attribute
`questionnaire.upload_handler.QuestionnaireUploadSizeGuardMiddleware`'s own
`process_view` hook checks - mirrors `entitlements.decorators.
require_capability`'s own "only acts on marked, organisation-scoped
routes" discipline: the hook raises `ImproperlyConfigured` the first time
a marked route without an `organisation_id` URL kwarg is actually
exercised (a programming-time mistake, caught the first time the route is
hit by a test or manually - not a request-time 500 for an ordinary user).

This decorator does NOT itself check anything at request time, and is NOT
a wrapper (it never changes identity/calling convention of the view
function it marks) - it is a pure, additive marker. ALL the actual
membership/readiness enforcement lives in the middleware hook (binding
STOP condition, WO §2.9/§8: "Any readiness check implemented only at view
level without the pipeline-level hook").

Because this is a plain attribute set directly on the function object
(never a `functools.wraps`-wrapped closure), it survives being wrapped by
further decorators applied OUTSIDE it (e.g. `@require_capability()`,
`@login_required`) - both of those use `functools.wraps`, whose
`WRAPPER_UPDATES = ("__dict__",)` copies the wrapped function's `__dict__`
(including this marker attribute) onto the outer wrapper's own `__dict__`.
So regardless of stacking order, the final view function Django's URL
resolver registers - and therefore the `view_func` this middleware's
`process_view` hook receives - still carries this attribute. The
convention this codebase already uses elsewhere
(`entitlements.decorators.require_capability`'s own docstring) is still
followed here for readability: place this decorator innermost, closest to
`def`:

    @login_required
    @require_capability()
    @requires_assurance_readiness
    def some_view(request, organisation_id, ...):
        ...
"""
from __future__ import annotations

REQUIRES_ASSURANCE_READINESS_ATTR = "requires_assurance_readiness"


def requires_assurance_readiness(view_func):
    """Marks `view_func` so the pipeline-level middleware hook enforces
    tenant-membership-then-Assurance-Readiness before this view - or
    anything downstream of it, including `CsrfViewMiddleware`'s own
    `process_view` (and the lazy multipart-body parse that reading
    `request.POST` there triggers) - ever runs for an organisation that is
    not yet ready. A pure marker: adds zero behaviour and zero performance
    cost of its own beyond setting one attribute at decoration time."""
    setattr(view_func, REQUIRES_ASSURANCE_READINESS_ATTR, True)
    return view_func


__all__ = ["REQUIRES_ASSURANCE_READINESS_ATTR", "requires_assurance_readiness"]
