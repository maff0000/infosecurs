"""
Mechanical tests for `core.context_processors.active_nav`'s URL-name-to-
section mapping (M006 PID §5, §22 "navigation/active organisation").

Pure unit tests of the mapping function itself - no database, no login, no
app-specific fixtures. `django.urls.resolve()` gives a real `ResolverMatch`
for a representative path in every organisation-scoped app; a bare UUID is
enough since URL resolution never touches the database.
"""
import uuid

from django.test import RequestFactory
from django.urls import resolve

from core.context_processors import (
    NAV_ACTIVITY,
    NAV_EVIDENCE,
    NAV_ORGANISATION,
    NAV_OVERVIEW,
    NAV_POLICY,
    NAV_QUESTIONNAIRES,
    NAV_SECURITY,
    active_nav,
)

ORG_ID = uuid.uuid4()


def _active_nav_for_path(path):
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    return active_nav(request)["active_nav"]


class TestActiveNavRepresentativeMappings:
    """One representative URL per app, covering every one of the seven
    sections at least once (PID §5's exact seven: Overview, Security,
    Evidence, Policy, Questionnaires, Activity, Organisation)."""

    def test_organisation_detail_is_overview(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/") == NAV_OVERVIEW

    def test_organisation_profile_is_organisation(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/profile/") == NAV_ORGANISATION

    def test_organisation_hub_is_organisation(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/hub/") == NAV_ORGANISATION

    def test_security_baseline_is_security(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/baseline/") == NAV_SECURITY

    def test_key_assets_is_security(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/assets/") == NAV_SECURITY

    def test_risk_register_is_security(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/risks/") == NAV_SECURITY

    def test_security_state_is_security(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/security-state/") == NAV_SECURITY

    def test_evidence_is_evidence(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/evidence/") == NAV_EVIDENCE

    def test_remediation_is_evidence(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/actions/") == NAV_EVIDENCE

    def test_policy_is_policy(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/policy/") == NAV_POLICY

    def test_questionnaire_is_questionnaires(self):
        assert (
            _active_nav_for_path(f"/organisations/{ORG_ID}/questionnaire/")
            == NAV_QUESTIONNAIRES
        )

    def test_activity_is_activity(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/activity/") == NAV_ACTIVITY

    def test_governance_is_organisation(self):
        assert (
            _active_nav_for_path(f"/organisations/{ORG_ID}/governance/roles/")
            == NAV_ORGANISATION
        )

    def test_workplace_is_organisation(self):
        assert _active_nav_for_path(f"/organisations/{ORG_ID}/workplace/") == NAV_ORGANISATION


class TestActiveNavDefaultsSensibly:
    """Everything not in the mapping is `None`, not an error - the
    pre-organisation-selection pages, health/auth infrastructure, and any
    future unmapped view alike."""

    def test_organisation_list_has_no_active_section(self):
        assert _active_nav_for_path("/organisations/") is None

    def test_organisation_create_has_no_active_section(self):
        assert _active_nav_for_path("/organisations/new/") is None

    def test_healthz_has_no_active_section(self):
        assert _active_nav_for_path("/healthz/") is None

    def test_home_has_no_active_section(self):
        assert _active_nav_for_path("/") is None

    def test_missing_resolver_match_has_no_active_section(self):
        request = RequestFactory().get("/anything/")
        request.resolver_match = None
        assert active_nav(request)["active_nav"] is None
