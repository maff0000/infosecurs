"""
M010D management command tests (docs/pids/M010D-REVIEW-RULES-SCHEDULER.md
§3/§5) - `python manage.py run_security_reviews`.
"""
from __future__ import annotations

import datetime as dt
import io

import pytest
from django.core.management import call_command

from evidence.models import EvidenceItem
from remediation.models import RemediationAction
from security_tasks import review_scheduler
from security_tasks.models import SecurityTask


def _make_evidence_item(org, *, valid_until):
    return EvidenceItem.objects.create(
        organisation=org, kind=EvidenceItem.KIND_EXTERNAL_REFERENCE, title="Cyber Essentials certificate",
        status=EvidenceItem.STATUS_ACTIVE, valid_until=valid_until,
        reference_url="https://example.invalid/certificate",
    )


def _make_remediation_action(org, *, target_date):
    return RemediationAction.objects.create(
        organisation=org, title="Patch the VPN gateway", status=RemediationAction.STATUS_OPEN,
        target_date=target_date,
    )


@pytest.mark.django_db
class TestRunSecurityReviewsCommand:
    def test_processes_every_organisation_and_creates_tasks(self, org_a, org_b):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        _make_remediation_action(org_b, target_date=dt.date(2026, 11, 21))

        out = io.StringIO()
        call_command("run_security_reviews", stdout=out)

        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        assert SecurityTask.objects.filter(organisation=org_b).count() == 1
        output = out.getvalue()
        assert "organisations_processed=2" in output
        assert "organisations_failed=0" in output

    def test_organisation_filter_processes_only_that_organisation(self, org_a, org_b):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        _make_remediation_action(org_b, target_date=dt.date(2026, 11, 21))

        out = io.StringIO()
        call_command("run_security_reviews", organisation=str(org_a.id), stdout=out)

        assert SecurityTask.objects.filter(organisation=org_a).count() == 1
        assert SecurityTask.objects.filter(organisation=org_b).count() == 0

    def test_repeated_sequential_runs_produce_a_stable_db_snapshot(self, org_a):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))

        for _ in range(3):
            call_command("run_security_reviews", stdout=io.StringIO())

        assert SecurityTask.objects.filter(organisation=org_a).count() == 1

    def test_one_organisations_rule_failure_does_not_block_the_next_organisation(self, org_a, org_b, monkeypatch):
        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        _make_remediation_action(org_b, target_date=dt.date(2026, 11, 21))

        real_run_for_organisation = review_scheduler.run_for_organisation

        def _flaky(organisation, *, now=None):
            if organisation.id == org_a.id:
                raise RuntimeError("simulated rule-evaluation failure for org_a")
            return real_run_for_organisation(organisation, now=now)

        monkeypatch.setattr(
            "security_tasks.management.commands.run_security_reviews.run_for_organisation", _flaky
        )

        out = io.StringIO()
        err = io.StringIO()
        call_command("run_security_reviews", stdout=out, stderr=err)

        # org_a's failure is caught and logged - org_b is still processed.
        assert SecurityTask.objects.filter(organisation=org_b).count() == 1
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0
        output = out.getvalue()
        assert "organisations_processed=1" in output
        assert "organisations_failed=1" in output
        # No cross-tenant leakage: the failure line names org_a's id only,
        # never org_b's data, and vice versa for the success line.
        assert str(org_b.id) not in err.getvalue()

    def test_command_makes_no_ai_gateway_call(self, org_a):
        from unittest.mock import patch

        from ai_platform.gateway import LiteLLMGateway

        _make_evidence_item(org_a, valid_until=dt.date(2026, 11, 20))
        with patch.object(LiteLLMGateway, "_send") as mock_send:
            call_command("run_security_reviews", stdout=io.StringIO())
        mock_send.assert_not_called()
