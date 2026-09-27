import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from entitlements.models import FOUNDATION_METRIC_VERSION, FoundationRequirement, ProductArea, RequirementKind

pytestmark = pytest.mark.django_db


@pytest.fixture
def area():
    return ProductArea.objects.create(
        code="fr-test-area",
        label="FR Test Area",
        destination_view_name="organisations:detail",
        min_package_tier=1,
    )


def make_requirement(area, **overrides):
    defaults = dict(
        code="fr-test-req",
        title="Test requirement",
        product_area=area,
        requirement_kind=RequirementKind.BASELINE_CONTROL,
        source_key="test_key",
        min_package_tier=1,
        security_weight=3,
    )
    defaults.update(overrides)
    return FoundationRequirement.objects.create(**defaults)


class TestTierRangeConstraint:
    @pytest.mark.parametrize("tier", [-1, 4])
    def test_out_of_range_tier_rejected(self, area, tier):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_requirement(area, code=f"fr-bad-tier-{tier}", min_package_tier=tier)


class TestRequirementKindIsAControlledEnum:
    def test_valid_kinds_accepted(self, area):
        r1 = make_requirement(area, code="fr-baseline", requirement_kind=RequirementKind.BASELINE_CONTROL)
        r2 = make_requirement(area, code="fr-milestone", requirement_kind=RequirementKind.DERIVED_MILESTONE)
        assert r1.requirement_kind == "BASELINE_CONTROL"
        assert r2.requirement_kind == "DERIVED_MILESTONE"

    def test_arbitrary_kind_rejected_by_full_clean(self, area):
        instance = FoundationRequirement(
            code="fr-invalid-kind",
            title="x",
            product_area=area,
            requirement_kind="SOMETHING_ELSE",
            source_key="x",
            min_package_tier=1,
        )
        with pytest.raises(ValidationError):
            instance.full_clean()


class TestMethodologyVersion:
    def test_default_methodology_version_is_the_current_constant(self, area):
        requirement = make_requirement(area, code="fr-methodology")
        assert requirement.methodology_version == FOUNDATION_METRIC_VERSION == "2026-09-v1"


class TestNoEditableCustomerScore:
    def test_model_has_no_score_or_completed_field(self):
        """
        PID §10.4: this table stores product methodology, never a
        customer's computed posture/completion percentage or an
        independently-editable manual "done" flag.
        """
        field_names = {f.name for f in FoundationRequirement._meta.get_fields()}
        forbidden_substrings = ("score", "percentage", "completed", "is_done")
        offending = {
            name
            for name in field_names
            if any(bad in name.lower() for bad in forbidden_substrings)
        }
        assert offending == set()


class TestProductAreaProtectedFromDeletion:
    def test_deleting_a_referenced_product_area_is_protected(self, area):
        make_requirement(area, code="fr-protects-area")
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            area.delete()
