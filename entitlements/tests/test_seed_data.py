"""
Proves PID §22's "fresh database produces exact intended rows" - exact
counts and exact `code` values, not "some rows exist" - plus §4's own
destination-reversibility test and §11.4's weight table landed verbatim.

These rows are created ONLY by entitlements/migrations/0002_* and 0003_*
(there is no fixture/factory anywhere in this test module that inserts
them) - the persistent pytest-django test database these tests run against
was itself built by running every migration from zero, so what is being
proved here is exactly "migrate alone reconstructs this data", per PID
§22/§32.
"""
import uuid

import pytest
from django.urls import NoReverseMatch, reverse

from entitlements.models import FoundationRequirement, ProductArea

pytestmark = pytest.mark.django_db

EXPECTED_PRODUCT_AREA_CODES = {
    "home",
    "foundations",
    "customer_assurance",
    "security",
    "security_state",
    "baseline",
    "assets",
    "risks",
    "evidence",
    "remediation",
    "policies",
    "company",
    "profile",
    "governance",
    "workplace",
    "activity",
    # M010A (entitlements/migrations/0005_seed_tasks_and_irene_product_
    # areas.py, docs/pids/M010A-TASK-SPINE.md §2) - strictly additive to
    # the 16 rows above, none of which this migration alters.
    "tasks",
    "irene",
}

EXPECTED_BASELINE_REQUIREMENT_CODES = {
    "baseline_mfa_user_accounts",
    "baseline_mfa_privileged_accounts",
    "baseline_endpoint_protection",
    "baseline_patching",
    "baseline_device_encryption",
    "baseline_backups",
    "baseline_joiner_mover_leaver",
    "baseline_privileged_access_separation",
    "baseline_security_awareness_training",
    "baseline_incident_reporting_route",
    "baseline_email_phishing_protection",
    "baseline_remote_access_control",
}

EXPECTED_MILESTONE_REQUIREMENT_CODES = {
    "milestone_organisation_profile",
    "milestone_governance_roles",
    "milestone_workplace",
    "milestone_assets_review",
    "milestone_risks_review",
    "milestone_policy_approved",
}

# PID §11.4's weight table, verbatim, keyed by security_baseline.catalogue key.
EXPECTED_BASELINE_WEIGHTS = {
    "mfa_privileged_accounts": 5,
    "patching": 5,
    "backups": 5,
    "mfa_user_accounts": 3,
    "endpoint_protection": 3,
    "device_encryption": 3,
    "joiner_mover_leaver": 3,
    "privileged_access_separation": 3,
    "email_phishing_protection": 3,
    "remote_access_control": 3,
    "incident_reporting_route": 1,
    "security_awareness_training": 1,
}


class TestProductAreaSeed:
    def test_exact_row_count(self):
        # 16 original (M007-WI1) + 2 additive M010A rows (`tasks`, `irene`
        # - entitlements/migrations/0005_seed_tasks_and_irene_product_
        # areas.py). See that migration's own docstring for proof it never
        # alters any of the original 16.
        assert ProductArea.objects.count() == 18

    def test_exact_code_set(self):
        assert set(ProductArea.objects.values_list("code", flat=True)) == EXPECTED_PRODUCT_AREA_CODES

    def test_every_destination_view_name_resolves(self):
        organisation_id = uuid.uuid4()
        failures = []
        for area in ProductArea.objects.all():
            try:
                reverse(area.destination_view_name, kwargs={"organisation_id": organisation_id})
            except NoReverseMatch as exc:
                failures.append((area.code, area.destination_view_name, str(exc)))
        assert failures == [], f"destination_view_name values that do not resolve: {failures}"

    def test_security_children_parented_correctly(self):
        security = ProductArea.objects.get(code="security")
        children = set(
            ProductArea.objects.filter(parent=security).values_list("code", flat=True)
        )
        assert children == {
            "security_state",
            "baseline",
            "assets",
            "risks",
            "evidence",
            "remediation",
        }

    def test_company_children_parented_correctly(self):
        company = ProductArea.objects.get(code="company")
        children = set(ProductArea.objects.filter(parent=company).values_list("code", flat=True))
        assert children == {"profile", "governance", "workplace", "activity"}

    def test_min_package_tier_matches_pid_section_5_2(self):
        expected = {
            "home": 0,
            "foundations": 1,
            "security": 1,
            "security_state": 1,
            "baseline": 1,
            "assets": 1,
            "risks": 1,
            "evidence": 1,
            "remediation": 1,
            "policies": 1,
            "company": 1,
            "profile": 1,
            "governance": 1,
            "workplace": 1,
            "activity": 1,
            "customer_assurance": 2,
            # M010A additions - both Foundational tier (1), matching
            # M010-MASTER-ARCHITECTURE.md §9's "Foundational: ...safe task
            # management...".
            "tasks": 1,
            "irene": 1,
        }
        actual = dict(ProductArea.objects.values_list("code", "min_package_tier"))
        assert actual == expected

    def test_all_seeded_rows_are_active(self):
        assert not ProductArea.objects.filter(is_active=False).exists()

    def test_all_seeded_rows_shown_in_navigation_except_the_irene_placeholder(self):
        """M010A's `irene` row is a deliberate exception (docs/pids/
        M010A-TASK-SPINE.md §2's own "placeholder for the future IRENE
        modal entry point") - IRENE is a modal entry point, not a sidebar
        page, so it is seeded `show_in_navigation=False` on purpose. Every
        OTHER row, including the two M010A added, remains
        `show_in_navigation=True`."""
        hidden = set(ProductArea.objects.filter(show_in_navigation=False).values_list("code", flat=True))
        assert hidden == {"irene"}


class TestFoundationRequirementSeed:
    def test_exact_row_count(self):
        assert FoundationRequirement.objects.count() == 18

    def test_exact_code_set(self):
        assert set(FoundationRequirement.objects.values_list("code", flat=True)) == (
            EXPECTED_BASELINE_REQUIREMENT_CODES | EXPECTED_MILESTONE_REQUIREMENT_CODES
        )

    def test_twelve_baseline_control_rows(self):
        qs = FoundationRequirement.objects.filter(requirement_kind="BASELINE_CONTROL")
        assert qs.count() == 12
        assert set(qs.values_list("code", flat=True)) == EXPECTED_BASELINE_REQUIREMENT_CODES

    def test_six_derived_milestone_rows(self):
        qs = FoundationRequirement.objects.filter(requirement_kind="DERIVED_MILESTONE")
        assert qs.count() == 6
        assert set(qs.values_list("code", flat=True)) == EXPECTED_MILESTONE_REQUIREMENT_CODES

    def test_baseline_weights_match_pid_section_11_4_verbatim(self):
        actual = dict(
            FoundationRequirement.objects.filter(requirement_kind="BASELINE_CONTROL").values_list(
                "source_key", "security_weight"
            )
        )
        assert actual == EXPECTED_BASELINE_WEIGHTS

    def test_baseline_rows_count_toward_posture_and_completion(self):
        qs = FoundationRequirement.objects.filter(requirement_kind="BASELINE_CONTROL")
        assert all(qs.values_list("counts_toward_posture", flat=True))
        assert all(qs.values_list("counts_toward_completion", flat=True))

    def test_milestone_rows_do_not_count_toward_posture_but_do_toward_completion(self):
        qs = FoundationRequirement.objects.filter(requirement_kind="DERIVED_MILESTONE")
        assert not any(qs.values_list("counts_toward_posture", flat=True))
        assert all(qs.values_list("counts_toward_completion", flat=True))

    def test_baseline_source_keys_match_security_baseline_catalogue(self):
        """
        Not importing the catalogue from the migration itself (see 0003's
        module docstring), but the *content* landed must still genuinely
        match the current catalogue keys - proven here, in a test, which is
        allowed (and expected) to depend on application code.
        """
        from security_baseline.catalogue import CATALOGUE_KEYS

        actual_source_keys = set(
            FoundationRequirement.objects.filter(requirement_kind="BASELINE_CONTROL").values_list(
                "source_key", flat=True
            )
        )
        assert actual_source_keys == set(CATALOGUE_KEYS)

    def test_all_rows_share_the_current_methodology_version(self):
        from entitlements.models import FOUNDATION_METRIC_VERSION

        versions = set(FoundationRequirement.objects.values_list("methodology_version", flat=True))
        assert versions == {FOUNDATION_METRIC_VERSION}

    def test_every_requirement_points_at_an_active_product_area(self):
        assert not FoundationRequirement.objects.filter(product_area__is_active=False).exists()


class TestRerunningMigrateIsSafe:
    def test_seed_rows_are_not_duplicated_by_a_second_logical_check(self):
        """
        A real "run migrate twice" proof belongs at the ops/shell level
        (Django's migration executor already refuses to re-run an applied
        migration - see the WI1 report for the mechanical command used).
        This test instead pins the *observable* invariant migrate-twice
        depends on: `code` uniqueness makes any accidental double-seed
        mechanically impossible to land silently, since a second insert of
        the same seed rows would raise IntegrityError, not create
        duplicates.
        """
        from django.db import IntegrityError, transaction

        home = ProductArea.objects.get(code="home")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProductArea.objects.create(
                    code="home",
                    label="Duplicate Home",
                    destination_view_name=home.destination_view_name,
                    min_package_tier=0,
                )
