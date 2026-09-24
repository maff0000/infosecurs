"""
M006 PID §11b - CSRF / methods.

`django.middleware.csrf.CsrfViewMiddleware` is already global (`config/
settings.py`'s `MIDDLEWARE`), so this is primarily a VERIFICATION pass
(PID §11b's own wording), not new protection being built - mirrors
`core/tests/test_error_pages.py::test_403_csrf_failure_renders_safe_
customer_facing_page`'s existing CSRF-failure discipline (same branded
`403_csrf.html`, same "no leakage" check), extended here across one
representative mutation from every organisation-scoped app named in PID
§11b: baseline answer save, evidence upload, remediation status change,
policy approve, questionnaire accept, governance role assignment,
workplace create.

Two properties are proven per representative mutation:

1. A POST with no CSRF token is rejected with a safe 403 - never a 500,
   never the mutation silently succeeding. `django.middleware.csrf.
   CsrfViewMiddleware.process_view` runs before ANY view code (including
   `@login_required` itself, which is a decorator inside the view
   function, not a middleware) - so this check does not depend on the
   requesting user actually being a member of the target organisation, or
   on any URL-supplied secondary id (an action id, a response id, a
   version id...) actually existing. Every case below therefore uses a
   syntactically-valid but arbitrary/non-existent secondary id where one
   is required, exactly like `core/tests/test_route_matrix.py`'s own
   documented reasoning - the property under test (CSRF is enforced) does
   not depend on it.

2. The same action is not reachable via a bare GET at all - either
   `HttpResponseNotAllowed` (405) for the codebase's explicitly POST-only
   "action-trigger" views (`remediation:start`, `questionnaire:
   response_accept`), or, for the GET+POST hybrid "form" views
   (`security_baseline:baseline`, `evidence:upload`, `policy:
   version_approve_direct`, `governance:roles`, `workplace:create`) where
   GET legitimately renders a confirmation/entry form, a direct proof that
   a GET performs no write at all (the relevant model's row count for this
   organisation is unchanged before/after) - GET reaching that form is not
   itself "the mutation", only the POST branch inside each of those views
   is, and that branch is never entered for `request.method == "GET"`
   (confirmed by reading every view in question - see PID §11a's route-
   matrix module docstring point 3 for the same "read before asserting"
   discipline applied there).

No real domain objects are created anywhere in this file - deliberately,
matching point 3's reasoning above: the CSRF property does not need them,
and the "GET performs no write" property is proven by an unchanged row
COUNT, not by inspecting one specific row.
"""
import uuid

import pytest
from django.test import Client
from django.urls import reverse

from evidence.models import EvidenceItem
from governance.models import GovernanceRoleAssignment
from security_baseline.models import BaselineAssessment
from workplace.models import Workplace

pytestmark = pytest.mark.django_db


def _csrf_client(user):
    """A real, logged-in client with CSRF checks genuinely enforced (no
    token/cookie supplied) - mirrors `core/tests/test_error_pages.py::
    test_403_csrf_failure_renders_safe_customer_facing_page`'s own
    `Client(enforce_csrf_checks=True)` pattern."""
    c = Client(enforce_csrf_checks=True)
    c.force_login(user)
    return c


def _assert_safe_csrf_rejection(response):
    assert response.status_code == 403, (
        f"expected a safe 403 CSRF rejection, got {response.status_code} - "
        f"a mutation must never silently succeed, and never 500, without a "
        f"valid CSRF token"
    )
    assert b"session expired" in response.content, (
        "expected the branded 403_csrf.html page (M006 PID §10), not a bare/"
        "default Django CSRF failure page"
    )


class TestSecurityBaselineCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("security_baseline:baseline", args=[org_a.id])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_does_not_save_a_baseline_answer(self, client_a, org_a):
        before = BaselineAssessment.objects.filter(organisation=org_a).count()
        response = client_a.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 200
        after = BaselineAssessment.objects.filter(organisation=org_a).count()
        assert after == before == 0, "a bare GET must never create a BaselineAssessment"


class TestEvidenceCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("evidence:upload", args=[org_a.id])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_does_not_create_evidence(self, client_a, org_a):
        before = EvidenceItem.objects.filter(organisation=org_a).count()
        response = client_a.get(reverse("evidence:upload", args=[org_a.id]))
        assert response.status_code == 200
        after = EvidenceItem.objects.filter(organisation=org_a).count()
        assert after == before == 0, "a bare GET must never create an EvidenceItem"


class TestRemediationStatusChangeCSRFAndMethods:
    """`remediation:start` - one of `action_start`/`action_complete`/
    `action_accept`, all built identically (method-checked-first,
    `HttpResponseNotAllowed` for anything but POST - see
    `remediation/views.py`)."""

    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("remediation:start", args=[org_a.id, uuid.uuid4()])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_is_not_allowed(self, client_a, org_a):
        url = reverse("remediation:start", args=[org_a.id, uuid.uuid4()])
        response = client_a.get(url)
        assert response.status_code == 405, (
            "a status-transition action must never be reachable via a bare GET"
        )


class TestPolicyApproveCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("policy:version_approve_direct", args=[org_a.id, uuid.uuid4()])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_performs_no_approval(self, client_a, org_a):
        # A fabricated version id 404s before the GET/POST branch is ever
        # reached (`_get_member_policy_version_or_404` runs first in
        # `policy.views._approve`) - which itself already proves a GET can
        # perform no approval (there is nothing to approve and nothing was
        # written). See `policy/tests/test_approval.py` for the full
        # positive-path proof using a real draft version.
        url = reverse("policy:version_approve_direct", args=[org_a.id, uuid.uuid4()])
        response = client_a.get(url)
        assert response.status_code == 404


class TestQuestionnaireResponseAcceptCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("questionnaire:response_accept", args=[org_a.id, uuid.uuid4()])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_is_not_allowed(self, client_a, org_a):
        url = reverse("questionnaire:response_accept", args=[org_a.id, uuid.uuid4()])
        response = client_a.get(url)
        assert response.status_code == 405, (
            "accepting a response must never be reachable via a bare GET"
        )


class TestGovernanceRoleAssignmentCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("governance:roles", args=[org_a.id])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_does_not_reassign_a_role(self, client_a, org_a):
        before = GovernanceRoleAssignment.objects.filter(organisation=org_a).count()
        response = client_a.get(reverse("governance:roles", args=[org_a.id]))
        assert response.status_code == 200
        after = GovernanceRoleAssignment.objects.filter(organisation=org_a).count()
        assert after == before, "a bare GET must never reassign/create a governance role"


class TestWorkplaceCreateCSRFAndMethods:
    def test_post_without_csrf_token_is_rejected(self, org_a, user_a):
        url = reverse("workplace:create", args=[org_a.id])
        response = _csrf_client(user_a).post(url, data={})
        _assert_safe_csrf_rejection(response)

    def test_get_does_not_create_a_workplace(self, client_a, org_a):
        before = Workplace.objects.filter(organisation=org_a).count()
        response = client_a.get(reverse("workplace:create", args=[org_a.id]))
        assert response.status_code == 200
        after = Workplace.objects.filter(organisation=org_a).count()
        assert after == before == 0, "a bare GET must never create a Workplace"
