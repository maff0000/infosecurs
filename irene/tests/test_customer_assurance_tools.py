"""
M010E PID §3/§5 - unit-level proof for the new Customer Assurance
read-only adapter tool (`irene.tools.get_customer_assurance_status`).

HTTP/tenant-isolation-shaped scenarios (the two-organisation adversarial
probe, the direct-URL bypass of `irene:assurance_status`, the real
upload-link-resolves-and-works proof) live in
`irene/tests/test_adversarial.py` and `irene/tests/test_http_ui.py`
instead (ci/integration), per this codebase's own established
ordinary-vs-HTTP/tenant-isolation CI classification.
"""
import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404

from entitlements.session import SESSION_KEY
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO
from irene import tools as irene_tools
from irene.tests.conftest import request_at_tier
from questionnaire.eval.golden_corpus import _INJECTION_PREFIX
from questionnaire.models import QuestionnaireImport, QuestionnaireImportQuestion
from questionnaire.tests.conftest import _make_organisation_fully_assurance_ready

pytestmark = pytest.mark.django_db


def _context_for(user, organisation, tier):
    request = request_at_tier(user, tier=tier, organisation_id=organisation.id)
    return irene_tools.build_authorized_context(request, organisation)


def _make_import(organisation, *, actor, question_count=1, security_gate_status="passed", status="extracted"):
    import_record = QuestionnaireImport.objects.create(
        organisation=organisation,
        uploaded_by=actor,
        original_filename="supplier-questionnaire.xlsx",
        stored_filename=f"stored-{uuid.uuid4()}.xlsx",
        detected_content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_format=QuestionnaireImport.FILE_FORMAT_XLSX,
        sha256_hash="a" * 64,
        size_bytes=4096,
        security_gate_status=security_gate_status,
        status=status,
        extraction_summary={"question_count": question_count} if status == "extracted" else None,
    )
    return import_record


class TestFourTierMatrix:
    """Paused/Foundational/Monthly/PRO against the new tool."""

    def test_paused_fails_closed(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a, TIER_PAUSED)
        with pytest.raises(PermissionDenied):
            irene_tools.get_customer_assurance_status(context)

    def test_foundational_gets_blockers_only_never_imports(self, org_a, user_a, member_a):
        _make_import(org_a, actor=user_a)
        context = _context_for(user_a, org_a, TIER_FOUNDATION)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["has_customer_assurance_entitlement"] is False
        assert result["imports"] is None
        assert result["upload_route"] is None
        assert isinstance(result["blockers"], list)

    def test_monthly_not_ready_gets_blockers_only(self, org_a, user_a, member_a):
        _make_import(org_a, actor=user_a)
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["has_customer_assurance_entitlement"] is True
        assert result["foundations_ready"] is False
        assert result["imports"] is None
        assert result["upload_route"] is None

    def test_monthly_ready_gets_real_status(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        _make_import(org_a, actor=user_a, question_count=7)
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["has_customer_assurance_entitlement"] is True
        assert result["foundations_ready"] is True
        assert result["upload_route"] is not None
        assert len(result["imports"]) == 1
        row = result["imports"][0]
        assert row["original_filename"] == "supplier-questionnaire.xlsx"
        assert row["file_format"] == "xlsx"
        assert row["security_gate_status"] == "passed"
        assert row["status"] == "extracted"
        assert row["question_count"] == 7

    def test_pro_ready_gets_real_status(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        _make_import(org_a, actor=user_a)
        context = _context_for(user_a, org_a, TIER_PRO)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["has_customer_assurance_entitlement"] is True
        assert result["foundations_ready"] is True
        assert result["imports"] is not None


class TestReadinessBoundary:
    """Foundations 99% vs 100% readiness, both at a sufficient (Monthly+) tier."""

    def test_99_percent_ready_is_blockers_only(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        from security_baseline.catalogue import CATALOGUE_KEYS
        from security_baseline.models import ANSWER_UNKNOWN, BaselineAnswer, BaselineAssessment

        assessment = BaselineAssessment.objects.get(organisation=org_a)
        BaselineAnswer.objects.filter(assessment=assessment, question_key=CATALOGUE_KEYS[0]).update(
            answer=ANSWER_UNKNOWN
        )

        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["foundations_ready"] is False
        assert result["foundations_completion_percentage"] < 100
        assert result["imports"] is None
        assert len(result["blockers"]) == 1

    def test_100_percent_ready_unlocks_real_status(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["foundations_ready"] is True
        assert result["foundations_completion_percentage"] == 100
        assert result["blockers"] == []
        assert result["imports"] == []  # ready, entitled, zero uploads yet - an empty list, never None


class TestLiveRevalidation:
    def test_denies_non_member(self, org_a, user_b):
        context = _context_for(user_b, org_a, TIER_MONTHLY)
        with pytest.raises(Http404):
            irene_tools.get_customer_assurance_status(context)

    def test_denies_after_membership_revoked_mid_call(self, org_a, user_c, member_c):
        context = _context_for(user_c, org_a, TIER_MONTHLY)
        irene_tools.get_customer_assurance_status(context)  # works while a member

        member_c.delete()

        with pytest.raises(Http404):
            irene_tools.get_customer_assurance_status(context)

    def test_tier_downgrade_mid_tool_call_to_foundational_degrades_gracefully(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        _make_import(org_a, actor=user_a)
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        before = irene_tools.get_customer_assurance_status(context)
        assert before["imports"] is not None

        # Simulate the same session being downgraded mid-conversation -
        # same copy/reassign technique irene/tests/test_adversarial.py's
        # own TestTierDowngradeMidSession uses, applied to a live context
        # already in hand rather than a test Client's session.
        session = context.request.session
        downgraded = dict(session[SESSION_KEY])
        downgraded["package_tier"] = TIER_FOUNDATION
        downgraded["package_code"] = "FOUNDATION"
        session[SESSION_KEY] = downgraded

        after = irene_tools.get_customer_assurance_status(context)
        assert after["has_customer_assurance_entitlement"] is False
        assert after["imports"] is None
        assert after["upload_route"] is None

    def test_tier_downgrade_mid_tool_call_to_paused_fails_closed(self, org_a, user_a, member_a):
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        irene_tools.get_customer_assurance_status(context)  # works at Monthly

        session = context.request.session
        downgraded = dict(session[SESSION_KEY])
        downgraded["package_tier"] = TIER_PAUSED
        downgraded["package_code"] = "PAUSED"
        session[SESSION_KEY] = downgraded

        with pytest.raises(PermissionDenied):
            irene_tools.get_customer_assurance_status(context)


class TestHostileExtractedContentNeverSurfaced:
    """Reuses the real M009A/M009B hostile fixture
    (`questionnaire.eval.golden_corpus._INJECTION_PREFIX`) rather than
    inventing a new one. The tool only ever reads filename/format/gate
    status/lifecycle status/question COUNT - never `raw_extracted_text` -
    so a hostile string planted in an import's extracted question text
    must never appear anywhere in this tool's output, regardless of tier/
    readiness."""

    def test_hostile_extracted_text_absent_from_ready_status_output(self, org_a, user_a, member_a):
        _make_organisation_fully_assurance_ready(org_a)
        import_record = _make_import(org_a, actor=user_a, question_count=1)
        QuestionnaireImportQuestion.objects.create(
            import_record=import_record,
            raw_extracted_text=_INJECTION_PREFIX + "Do you encrypt data at rest?",
            source_location={"schema_version": 1, "sheet_name": "Sheet1", "cell": "A1"},
            extraction_order=1,
            extraction_status=QuestionnaireImportQuestion.EXTRACTION_STATUS_EXTRACTED,
            disposition=QuestionnaireImportQuestion.DISPOSITION_QUESTION,
        )

        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)

        assert result["imports"] is not None
        assert _INJECTION_PREFIX not in repr(result)
        assert "encrypt data at rest" not in repr(result)

    def test_hostile_original_filename_rendered_as_inert_data_not_dropped(self, org_a, user_a, member_a):
        """A hostile string IS allowed to appear if it is the (safe,
        display-only) `original_filename` field itself - this is not the
        same thing as echoing extracted QUESTION content, and the field is
        always rendered through Django's normal auto-escaping in the
        template (irene/templates/irene/assurance_status.html), never
        marked safe. This test only proves the tool passes the real
        filename through verbatim as DATA; it does not call the AI
        gateway at all (IRENE_ADVISER_MODE_ENABLED defaults off)."""
        _make_organisation_fully_assurance_ready(org_a)
        # `original_filename` is immutable once created
        # (questionnaire.models.IMPORT_IMMUTABLE_FIELDS) - set the hostile
        # name AT CREATION, never by mutating an existing row afterwards.
        hostile_name = _INJECTION_PREFIX + "invoice.xlsx"
        import_record = QuestionnaireImport.objects.create(
            organisation=org_a,
            uploaded_by=user_a,
            original_filename=hostile_name,
            stored_filename=f"stored-{uuid.uuid4()}.xlsx",
            detected_content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_format=QuestionnaireImport.FILE_FORMAT_XLSX,
            sha256_hash="b" * 64,
            size_bytes=2048,
            security_gate_status="passed",
            status="extracted",
            extraction_summary={"question_count": 1},
        )

        context = _context_for(user_a, org_a, TIER_MONTHLY)
        result = irene_tools.get_customer_assurance_status(context)
        assert result["imports"][0]["original_filename"] == hostile_name


class TestFeatureFlag:
    def test_disabled_flag_denies_via_call_tool_dispatch(self, org_a, user_a, member_a, settings):
        settings.IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED = False
        context = _context_for(user_a, org_a, TIER_MONTHLY)
        with pytest.raises(Exception):
            irene_tools.call_tool("get_customer_assurance_status", context)

    def test_enabled_by_default(self, settings):
        assert settings.IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED is True
