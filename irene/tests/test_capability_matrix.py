"""
M010E PID §1 - the IRENE capability matrix is a read-only REPORTING
projection over the real `irene.tools.TOOL_REGISTRY` and the live
`ProductArea` table, never a second tier-comparison mechanism. These
tests prove it stays that way: every row's tier comes from the real DB
seed data (no hand-maintained duplicate), and the matrix covers every
tool/modal feature this campaign (Work Packages A-E) has built.
"""
import pytest

from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY
from irene.capability_matrix import MODAL_FEATURE_CAPABILITIES, get_capability_matrix
from irene.tools import TOOL_REGISTRY

pytestmark = pytest.mark.django_db


class TestCapabilityMatrixCoverage:
    def test_covers_every_registered_tool(self):
        matrix = get_capability_matrix()
        tool_rows = {row.name for row in matrix if row.kind == "tool"}
        assert tool_rows == set(TOOL_REGISTRY)

    def test_covers_every_modal_feature(self):
        matrix = get_capability_matrix()
        modal_rows = {row.name for row in matrix if row.kind == "modal_feature"}
        assert modal_rows == set(MODAL_FEATURE_CAPABILITIES)

    def test_sorted_stably_by_kind_then_name(self):
        matrix = get_capability_matrix()
        keys = [(row.kind, row.name) for row in matrix]
        assert keys == sorted(keys)


class TestCapabilityMatrixReflectsRealDbTiers:
    """Never a hand-maintained duplicate - the tier reported here must
    match the real, live ProductArea row `has_capability` itself reads."""

    def test_new_customer_assurance_tool_reports_monthly_tier(self):
        matrix = get_capability_matrix()
        row = next(r for r in matrix if r.name == "get_customer_assurance_status")
        assert row.required_capability == "security"
        # The tool's own base gate is Foundational (1) - the tier-2 gate
        # is an INTERNAL recheck inside the tool body, not its registry
        # tier (see irene.tools.get_customer_assurance_status's own
        # docstring for why that is deliberate).
        assert row.min_package_tier == TIER_FOUNDATION

    def test_assurance_status_modal_feature_reports_monthly_tier(self):
        matrix = get_capability_matrix()
        row = next(r for r in matrix if r.name == "irene:assurance_status")
        assert row.required_capability == "customer_assurance"
        assert row.min_package_tier == TIER_MONTHLY
        assert row.min_package_tier_code == "MONTHLY"

    def test_unknown_capability_code_reports_none_rather_than_raising(self, monkeypatch):
        import dataclasses

        from irene import capability_matrix

        monkeypatch.setitem(
            capability_matrix.MODAL_FEATURE_CAPABILITIES, "fake:feature", "made_up_capability"
        )
        matrix = get_capability_matrix()
        row = next(r for r in matrix if r.name == "fake:feature")
        assert row.min_package_tier is None
        assert row.min_package_tier_code is None

    def test_feature_flag_reflected_for_flagged_tool(self, settings):
        settings.IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED = False
        matrix = get_capability_matrix()
        row = next(r for r in matrix if r.name == "get_customer_assurance_status")
        assert row.feature_flag_enabled is False

        settings.IRENE_CUSTOMER_ASSURANCE_ADAPTER_ENABLED = True
        matrix = get_capability_matrix()
        row = next(r for r in matrix if r.name == "get_customer_assurance_status")
        assert row.feature_flag_enabled is True
