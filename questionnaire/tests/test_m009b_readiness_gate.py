"""
M009B Increment 1 - Assurance Readiness Gate tests
(WO-M009B-FOUNDATIONS-READINESS-CSV-BULK-ORCHESTRATION.md §2.7).

Unit tests against `security_baseline.readiness.evaluate_assurance_
readiness` directly, plus pipeline-level HTTP tests against the real,
un-stubbed middleware hook (every test below that needs the REAL gate
re-patches `questionnaire.upload_handler.evaluate_assurance_readiness`
itself, overriding this package's own `m009b_default_assurance_readiness`
autouse default - see that fixture's docstring in conftest.py for why the
default exists and how overriding it works).
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED
from questionnaire import import_services
from questionnaire.eval import m009b_csv_ingestion_corpus as corpus
from questionnaire.models import QuestionnaireImport
from questionnaire.scanner import STATE_CLEAN, ScanResult
from questionnaire.upload_handler import QuestionnaireUploadSizeGuardHandler
from security_baseline.readiness import evaluate_assurance_readiness

pytestmark = pytest.mark.django_db


def _upload(data: bytes, name="q.csv"):
    return SimpleUploadedFile(name, data, content_type="text/csv")


def _patch_clean_scanner(monkeypatch):
    class _Scanner:
        def scan_file(self, file_path):
            return ScanResult(state=STATE_CLEAN, provenance={"backend": "fake"})

    monkeypatch.setattr(import_services, "get_scanner", lambda: _Scanner())


# ---------------------------------------------------------------------------
# Unit tests - security_baseline.readiness.evaluate_assurance_readiness.
# ---------------------------------------------------------------------------
class TestEvaluateAssuranceReadiness:
    def test_zero_percent_completion_is_not_ready(self, org_a):
        result = evaluate_assurance_readiness(org_a)
        assert result.is_ready is False
        assert result.completion.percentage == 0
        assert len(result.blockers) == 18

    def test_partial_completion_is_not_ready(self, org_a, make_organisation_fully_assurance_ready):
        make_organisation_fully_assurance_ready(org_a)
        # Deliberately regress exactly one requirement back to incomplete
        # (amendment's own "deliberately regressed to unknown on one
        # FoundationRequirement row" scenario - §2.11).
        from security_baseline.catalogue import CATALOGUE_KEYS
        from security_baseline.models import ANSWER_UNKNOWN, BaselineAnswer, BaselineAssessment

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        BaselineAnswer.objects.filter(
            assessment=assessment, question_key=CATALOGUE_KEYS[0]
        ).update(answer=ANSWER_UNKNOWN)

        result = evaluate_assurance_readiness(org_a)
        assert result.is_ready is False
        assert result.completion.percentage < 100
        assert len(result.blockers) == 1

    def test_hundred_percent_completion_is_ready(self, org_a, make_organisation_fully_assurance_ready):
        make_organisation_fully_assurance_ready(org_a)
        result = evaluate_assurance_readiness(org_a)
        assert result.is_ready is True
        assert result.completion.percentage == 100
        assert result.blockers == ()

    def test_derived_milestone_resolver_false_blocks_readiness(
        self, org_a, make_organisation_fully_assurance_ready
    ):
        """A DERIVED_MILESTONE resolver returning False (governance roles
        never assigned) must, on its own, prevent readiness even when
        every BASELINE_CONTROL item is answered."""
        from security_baseline.catalogue import CATALOGUE_KEYS
        from security_baseline.models import ANSWER_YES, BaselineAnswer, BaselineAssessment

        assessment, _ = BaselineAssessment.objects.get_or_create(organisation=org_a)
        for key in CATALOGUE_KEYS:
            BaselineAnswer.objects.update_or_create(
                assessment=assessment, question_key=key, defaults={"answer": ANSWER_YES}
            )
        # Deliberately do NOT run make_organisation_fully_assurance_ready
        # - governance/workplace/profile/assets/risk/policy are all still
        # unset, so every DERIVED_MILESTONE resolver returns False.
        result = evaluate_assurance_readiness(org_a)
        assert result.is_ready is False
        assert len(result.blockers) == 6  # the 6 DERIVED_MILESTONE rows

    def test_readiness_built_on_canonical_completion_not_a_second_calculation(
        self, org_a, make_organisation_fully_assurance_ready
    ):
        from entitlements.metrics import get_security_foundations_completion

        make_organisation_fully_assurance_ready(org_a)
        canonical = get_security_foundations_completion(org_a)
        result = evaluate_assurance_readiness(org_a)
        assert result.completion.percentage == canonical.percentage
        assert result.completion.completed_count == canonical.completed_count
        assert result.completion.total_count == canonical.total_count


# ---------------------------------------------------------------------------
# Pipeline-level HTTP tests - the real, un-stubbed middleware hook.
# ---------------------------------------------------------------------------
class TestPipelineLevelReadinessGate:
    def test_get_to_unready_org_renders_blockers_not_upload_form(self, client_a, org_a, monkeypatch):
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200
        assert "form" not in response.context
        assert b"not available yet" in response.content

    def test_ready_org_renders_upload_form(
        self, client_a, org_a, make_organisation_fully_assurance_ready, monkeypatch
    ):
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        make_organisation_fully_assurance_ready(org_a)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200
        assert "form" in response.context

    def test_post_to_unready_org_never_populates_request_post_or_files(
        self, client_a, org_a, monkeypatch
    ):
        """The hook's genuine, provable guarantee (WO §2.6): no upload
        handler is ever INVOKED (its receive_data_chunk never fires), and
        no QuestionnaireImport row is ever created, for an unready
        organisation's POST."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        calls = []
        original = QuestionnaireUploadSizeGuardHandler.receive_data_chunk

        def _spy(self, raw_data, start):
            calls.append(len(raw_data))
            return original(self, raw_data, start)

        monkeypatch.setattr(QuestionnaireUploadSizeGuardHandler, "receive_data_chunk", _spy)

        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"declared_format": "csv", "file": _upload(corpus.valid_csv_with_answer_and_reference())},
        )
        assert response.status_code == 200
        assert b"not available yet" in response.content
        assert calls == []  # the upload handler's own chunk callback never fired
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == 0

    def test_direct_post_bypass_attempt_against_unready_org_still_rejected(
        self, client_a, org_a, monkeypatch
    ):
        """A hostile caller skipping the GET/form entirely and POSTing
        straight to the upload endpoint is rejected identically - the
        gate is pipeline-level, not merely "the rendered form is hidden"."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"file": _upload(corpus.valid_csv_with_answer_and_reference())},
        )
        assert response.status_code == 200
        assert b"not available yet" in response.content
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == 0

    def test_hook_fires_before_csrf_process_view(self, org_a, user_a, member_a, monkeypatch):
        """Request-level proof (not only unit-test mocking): a real,
        CSRF-enforcing client POSTing WITHOUT a CSRF token to an UNREADY
        organisation's upload URL gets the blocker response (200), never
        CSRF's own 403 - proving this hook's process_view genuinely runs,
        and genuinely short-circuits, before CsrfViewMiddleware.
        process_view ever gets a chance to reject the missing token. The
        same request shape against a READY organisation DOES get CSRF's
        ordinary 403, confirming the only reason the first request didn't
        is this hook's own, earlier-firing short-circuit."""
        from django.test import Client

        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        enforcing_client = Client(enforce_csrf_checks=True)
        enforcing_client.force_login(user_a)

        response = enforcing_client.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"file": _upload(corpus.valid_csv_with_answer_and_reference())},
        )
        assert response.status_code == 200
        assert b"not available yet" in response.content

    def test_membership_before_readiness_non_member_gets_404_never_readiness_response(
        self, client_b, org_a, org_b, user_b, member_b, monkeypatch, make_organisation_fully_assurance_ready
    ):
        """Binding ordering requirement (WO §2.6/§2.9): a non-member of a
        REAL, 100%-ready organisation still gets a genuine 404 - readiness
        is never even evaluated for them, let alone leaked by response
        shape."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        make_organisation_fully_assurance_ready(org_a)
        response = client_b.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 404
        assert b"not available yet" not in response.content

    def test_membership_before_readiness_non_member_of_unready_org_also_404s(
        self, client_b, org_a, org_b, user_b, member_b, monkeypatch
    ):
        """The symmetric case - org_a is genuinely UNREADY (the default,
        unconfigured fixture) AND the caller is a non-member: still a
        plain 404, never the readiness-blocker response - a non-member
        must never be able to tell "not ready" apart from "not a member"
        by response shape."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        response = client_b.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 404
        assert b"not available yet" not in response.content

    def test_unauthenticated_request_redirects_to_login_not_404_or_blocker(self, org_a, monkeypatch):
        """Regression guard for this hook's own deliberate "pass through
        for anonymous callers" design (see the hook's own docstring) -
        an unauthenticated visitor must still get the existing login
        redirect, never a 404 (which would newly regress the existing
        @login_required behaviour) and never a readiness-blocker
        response (which would require evaluating membership for an
        AnonymousUser - itself never attempted)."""
        from django.test import Client

        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        anon_client = Client()
        response = anon_client.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url or "login" in response.url

    def test_tenant_isolation_blockers_never_leak_another_orgs_state(
        self, client_a, org_a, org_b, make_organisation_fully_assurance_ready, monkeypatch
    ):
        """org_b is fully ready; org_a is genuinely unready. client_a
        (a member of org_a only) must see ONLY org_a's own blockers -
        never anything derived from org_b's state."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        make_organisation_fully_assurance_ready(org_b)
        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 200
        assert response.context["organisation"].id == org_a.id
        assert len(response.context["blockers"]) == 18


# ---------------------------------------------------------------------------
# Entitlement-tier check inside the hook (WO §2.6 repair: membership ->
# entitlement -> readiness) - against the REAL, un-stubbed
# `evaluate_assurance_readiness` (genuinely unready org_a, the package's
# own default fixture shape - see `m009b_default_assurance_readiness`'s
# docstring for why org_a is 0% ready unless explicitly made ready), with
# the requesting member's session tier forced insufficient for
# `customer_assurance` (min_package_tier=2 - TIER_PAUSED=0/TIER_FOUNDATION=1
# both qualify). Proves the defect this increment fixes is closed: before
# this fix, `QuestionnaireUploadSizeGuardMiddleware.process_view` never
# checked entitlement at all, so an insufficiently-entitled member of an
# unready org got the full readiness-blocker page (200, this
# organisation's real Foundations completion percentage and specific
# missing-control titles) instead of `require_capability`'s own generic,
# reason-free `PermissionDenied` (403) - a genuine entitlement-tier
# bypass / information-disclosure. This gap was previously untested: every
# other test in this file relies on `m009b_default_assurance_readiness`'s
# autouse stub (always-ready) and/or `client_a`'s default TIER_MONTHLY
# session, so the real "not ready" branch was never exercised in
# combination with an insufficient tier anywhere in the suite.
# ---------------------------------------------------------------------------
class TestEntitlementCheckedBetweenMembershipAndReadiness:
    @pytest.mark.parametrize("insufficient_tier", [TIER_PAUSED, TIER_FOUNDATION])
    def test_insufficient_tier_member_of_unready_org_gets_403_never_blocker_page(
        self, client_a, user_a, org_a, insufficient_tier, monkeypatch
    ):
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        set_session_tier(client_a, user_a, insufficient_tier, organisation_id=org_a.id)

        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))

        assert response.status_code == 403
        assert b"not available yet" not in response.content

    def test_insufficient_tier_post_to_unready_org_gets_403_and_never_touches_storage(
        self, client_a, user_a, org_a, monkeypatch
    ):
        """The same genuine-mechanism proof
        `test_post_to_unready_org_never_populates_request_post_or_files`
        above makes for the membership/readiness ordering, extended to
        the entitlement dimension: an insufficiently-entitled member's
        POST must never reach the point where any upload handler is
        invoked or any `QuestionnaireImport` row is created, exactly like
        an unready organisation's POST - proving this is a genuine
        pipeline-level short-circuit, not merely a hidden form."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        set_session_tier(client_a, user_a, TIER_FOUNDATION, organisation_id=org_a.id)
        calls = []
        original = QuestionnaireUploadSizeGuardHandler.receive_data_chunk

        def _spy(self, raw_data, start):
            calls.append(len(raw_data))
            return original(self, raw_data, start)

        monkeypatch.setattr(QuestionnaireUploadSizeGuardHandler, "receive_data_chunk", _spy)

        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"declared_format": "csv", "file": _upload(corpus.valid_csv_with_answer_and_reference())},
        )

        assert response.status_code == 403
        assert b"not available yet" not in response.content
        assert calls == []
        assert QuestionnaireImport.objects.filter(organisation=org_a).count() == 0

    def test_non_member_with_insufficient_tier_still_gets_404_not_403(
        self, client_b, org_a, org_b, user_b, member_b, monkeypatch
    ):
        """Ordering regression guard (WO §2.6: 'Only once membership is
        confirmed does the hook proceed to the entitlement-tier check') -
        a non-member's response must still be the plain, existing 404
        convention, never varying by (possibly forged/irrelevant) tier -
        the entitlement check added by this fix must never run, let alone
        be reachable, before membership is proven."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        set_session_tier(client_b, user_b, TIER_PAUSED, organisation_id=org_b.id)
        response = client_b.get(reverse("questionnaire:import_upload", args=[org_a.id]))
        assert response.status_code == 404
        assert b"not available yet" not in response.content

    def test_sufficiently_entitled_member_of_unready_org_still_sees_blocker_page(
        self, client_a, user_a, org_a, monkeypatch
    ):
        """Regression protection for what already worked (WO §2.6's
        'entitlement-tier check ... unaffected'): a Monthly+ (sufficiently
        entitled) member of a genuinely unready organisation must still
        reach - and see - the real readiness-blocker page, exactly as
        before this fix. Tier is forced explicitly here (rather than
        relying on client_a's login default) so this test documents the
        boundary it proves, not merely inherits it."""
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        set_session_tier(client_a, user_a, TIER_MONTHLY, organisation_id=org_a.id)

        response = client_a.get(reverse("questionnaire:import_upload", args=[org_a.id]))

        assert response.status_code == 200
        assert "form" not in response.context
        assert b"not available yet" in response.content
        assert response.context["organisation"].id == org_a.id


# ---------------------------------------------------------------------------
# End-to-end: a genuinely ready organisation uploads a real CSV through
# the real, un-stubbed HTTP pipeline.
# ---------------------------------------------------------------------------
class TestReadyOrganisationCsvUploadEndToEnd:
    def test_ready_organisation_uploads_csv_reaches_extracted(
        self, client_a, org_a, make_organisation_fully_assurance_ready, monkeypatch
    ):
        monkeypatch.setattr(
            "questionnaire.upload_handler.evaluate_assurance_readiness", evaluate_assurance_readiness
        )
        make_organisation_fully_assurance_ready(org_a)
        _patch_clean_scanner(monkeypatch)
        response = client_a.post(
            reverse("questionnaire:import_upload", args=[org_a.id]),
            {"declared_format": "csv", "file": _upload(corpus.valid_csv_with_answer_and_reference())},
        )
        assert response.status_code == 302
        import_record = QuestionnaireImport.objects.get(organisation=org_a)
        assert import_record.file_format == QuestionnaireImport.FILE_FORMAT_CSV
        assert import_record.status == QuestionnaireImport.STATUS_EXTRACTED
