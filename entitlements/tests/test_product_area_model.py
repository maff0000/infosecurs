"""
Mechanical proof of PID §4.2's constraints - not eyeballing that the model
looks right, but actually attempting the forbidden operation and observing
the database refuse it.
"""
import pytest
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from entitlements.models import ProductArea

pytestmark = pytest.mark.django_db


def make_area(**overrides):
    defaults = dict(
        code="test-area",
        label="Test Area",
        destination_view_name="organisations:detail",
        min_package_tier=1,
        display_order=0,
    )
    defaults.update(overrides)
    return ProductArea.objects.create(**defaults)


class TestUniqueCode:
    def test_duplicate_code_rejected(self):
        make_area(code="dup")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_area(code="dup")


class TestTierRangeConstraint:
    @pytest.mark.parametrize("tier", [0, 1, 2, 3])
    def test_in_range_tier_accepted(self, tier):
        area = make_area(code=f"tier-{tier}", min_package_tier=tier)
        assert area.min_package_tier == tier

    @pytest.mark.parametrize("tier", [-1, 4, 100])
    def test_out_of_range_tier_rejected_at_db_level(self, tier):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_area(code=f"bad-tier-{tier}", min_package_tier=tier)


class TestCannotParentItself:
    def test_self_parent_rejected_at_db_level(self):
        area = make_area(code="self-parent-test")
        area.parent = area
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                area.save()

    def test_self_parent_rejected_by_clean(self):
        area = make_area(code="self-parent-clean-test")
        area.parent = area
        with pytest.raises(ValidationError):
            area.clean()

    def test_ordinary_parent_child_is_fine(self):
        parent = make_area(code="parent-ok")
        child = make_area(code="child-ok", parent=parent)
        assert child.parent_id == parent.id
        # clean() must not raise for a legitimate, distinct parent.
        child.clean()

    def test_null_parent_passes_the_db_constraint(self):
        # A NULL parent_id must never be treated as "violates the
        # self-parent constraint" - SQL's `parent = id` is UNKNOWN, not
        # TRUE, when parent_id IS NULL, and Postgres CHECK constraints
        # treat UNKNOWN as satisfied.
        area = make_area(code="no-parent-ok", parent=None)
        assert area.parent_id is None


class TestDeterministicOrdering:
    def test_ordering_is_display_order_then_code(self):
        make_area(code="zzz-first-order", display_order=1)
        make_area(code="aaa-first-order", display_order=1)
        make_area(code="only-second-order", display_order=2)

        ordered_codes = list(
            ProductArea.objects.filter(code__endswith="-order").values_list("code", flat=True)
        )
        assert ordered_codes == ["aaa-first-order", "zzz-first-order", "only-second-order"]


class TestActiveQuerysetHelper:
    def test_active_excludes_inactive_rows(self):
        make_area(code="active-row", is_active=True)
        make_area(code="inactive-row", is_active=False)

        active_codes = set(ProductArea.objects.active().values_list("code", flat=True))
        assert "active-row" in active_codes
        assert "inactive-row" not in active_codes

    def test_manager_default_returns_everything_including_inactive(self):
        make_area(code="inactive-visible-to-plain-manager", is_active=False)
        assert ProductArea.objects.filter(code="inactive-visible-to-plain-manager").exists()


class TestForTierHelper:
    def test_for_tier_filters_by_min_package_tier_and_active(self):
        make_area(code="tier0-active", min_package_tier=0)
        make_area(code="tier2-active", min_package_tier=2)
        make_area(code="tier1-inactive", min_package_tier=1, is_active=False)

        codes_at_tier_1 = set(
            ProductArea.objects.filter(code__startswith="tier").for_tier(1).values_list("code", flat=True)
        )
        assert codes_at_tier_1 == {"tier0-active"}

        codes_at_tier_2 = set(
            ProductArea.objects.filter(code__startswith="tier").for_tier(2).values_list("code", flat=True)
        )
        assert codes_at_tier_2 == {"tier0-active", "tier2-active"}
