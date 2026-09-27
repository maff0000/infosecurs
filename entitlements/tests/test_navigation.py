"""
PID §4.4 (database-driven navigation service) / §25.1 (tier matrix) /
§16.1 ("selected area clearly highlighted").

Proves `entitlements.navigation.build_navigation_tree` - never anything
about the shell TEMPLATE (see `core/tests/test_application_shell.py` for
that) - is built entirely from real seeded `ProductArea` rows filtered
through `entitlements.capabilities.has_capability`, with no re-derived/
hard-coded tier check of its own, and that the tier hierarchy is
mechanically cumulative (Monthly inherits Foundation, Pro inherits both -
never duplicated per-tier flags).
"""
import uuid

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.urls import resolve, reverse

from entitlements.models import ProductArea
from entitlements.navigation import build_navigation_tree
from entitlements.session import issue_context
from entitlements.tiers import TIER_FOUNDATION, TIER_MONTHLY, TIER_PAUSED, TIER_PRO

pytestmark = pytest.mark.django_db


class FakeRequest:
    """Same minimal seam `entitlements/tests/test_capabilities.py`'s own
    `FakeRequest` uses - a real `SessionStore` + a real user, no HTTP
    machinery, since `build_navigation_tree` (like `has_capability`) only
    ever reads `request.session`/`request.user`/`request.resolver_match`."""

    def __init__(self, session, user, resolver_match=None):
        self.session = session
        self.user = user
        self.resolver_match = resolver_match


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="nav_user", password="not-a-real-password-123")


def _request_at_tier(user, tier, resolver_match=None):
    store = SessionStore()
    store.save()
    request = FakeRequest(store, user, resolver_match=resolver_match)
    issue_context(request, user, package_tier=tier, auth_source="test_fixture")
    return request


def _codes(nav_items):
    return [item.code for item in nav_items]


class TestTierMatrixIsCumulative:
    """PID §25.1's exact tier matrix, proven against the tree-building
    function directly (the shell template's own rendering of this same
    tree is proven separately in core/tests/test_application_shell.py)."""

    def test_paused_sees_only_home(self, user):
        request = _request_at_tier(user, TIER_PAUSED)
        tree = build_navigation_tree(request, uuid.uuid4())
        assert _codes(tree) == ["home"]
        assert tree[0].children == ()

    def test_foundation_sees_home_foundations_security_policies_company_not_customer_assurance(self, user):
        request = _request_at_tier(user, TIER_FOUNDATION)
        tree = build_navigation_tree(request, uuid.uuid4())
        assert _codes(tree) == ["home", "foundations", "security", "policies", "company"]

        security = next(item for item in tree if item.code == "security")
        assert _codes(security.children) == [
            "security_state",
            "baseline",
            "assets",
            "risks",
            "evidence",
            "remediation",
        ]

        company = next(item for item in tree if item.code == "company")
        assert _codes(company.children) == ["profile", "governance", "workplace", "activity"]

    def test_monthly_adds_customer_assurance_without_losing_foundation(self, user):
        foundation_request = _request_at_tier(user, TIER_FOUNDATION)
        foundation_codes = set(_codes(build_navigation_tree(foundation_request, uuid.uuid4())))

        monthly_request = _request_at_tier(user, TIER_MONTHLY)
        monthly_tree = build_navigation_tree(monthly_request, uuid.uuid4())
        monthly_codes = set(_codes(monthly_tree))

        assert monthly_codes == foundation_codes | {"customer_assurance"}
        # Ordering: customer_assurance (display_order 30) sits between
        # foundations (20) and security (40) - the tree reflects seeded
        # display_order, never a hand-maintained list.
        assert _codes(monthly_tree) == [
            "home",
            "foundations",
            "customer_assurance",
            "security",
            "policies",
            "company",
        ]

    def test_pro_inherits_every_foundation_and_monthly_item(self, user):
        monthly_request = _request_at_tier(user, TIER_MONTHLY)
        monthly_codes = set(_codes(build_navigation_tree(monthly_request, uuid.uuid4())))

        pro_request = _request_at_tier(user, TIER_PRO)
        pro_tree = build_navigation_tree(pro_request, uuid.uuid4())
        pro_codes = {item.code for item in pro_tree} | {
            child.code for item in pro_tree for child in item.children
        }
        monthly_all_codes = monthly_codes | {
            child.code
            for item in build_navigation_tree(monthly_request, uuid.uuid4())
            for child in item.children
        }

        assert monthly_all_codes <= pro_codes
        # Pro sees every single seeded ProductArea - there is no Pro-only
        # area yet (PID §5.2's own "M007 does not need to invent a fake
        # Pro-only feature").
        assert pro_codes == set(ProductArea.objects.values_list("code", flat=True))

    def test_inactive_area_never_appears_regardless_of_tier(self, user):
        area = ProductArea.objects.get(code="policies")
        area.is_active = False
        area.save(update_fields=["is_active"])

        request = _request_at_tier(user, TIER_PRO)
        tree = build_navigation_tree(request, uuid.uuid4())
        assert "policies" not in _codes(tree)

    def test_show_in_navigation_false_hides_area_even_if_entitled(self, user):
        area = ProductArea.objects.get(code="activity")
        area.show_in_navigation = False
        area.save(update_fields=["show_in_navigation"])

        request = _request_at_tier(user, TIER_PRO)
        tree = build_navigation_tree(request, uuid.uuid4())
        company = next(item for item in tree if item.code == "company")
        assert "activity" not in _codes(company.children)


class TestNavigationLinksAreRealResolvedUrls:
    def test_urls_resolve_against_the_supplied_organisation_id(self, user):
        organisation_id = uuid.uuid4()
        request = _request_at_tier(user, TIER_PRO)
        tree = build_navigation_tree(request, organisation_id)

        home = next(item for item in tree if item.code == "home")
        assert home.url == reverse("organisations:detail", kwargs={"organisation_id": organisation_id})

        security = next(item for item in tree if item.code == "security")
        security_state = next(child for child in security.children if child.code == "security_state")
        assert security_state.url == reverse(
            "security_state:list", kwargs={"organisation_id": organisation_id}
        )


class TestActiveItemHighlighting:
    """PID §16.1 'selected area clearly highlighted'. Two of the sixteen
    seeded rows deliberately share a destination route with another row
    (see entitlements/navigation.py's `_pick_current_area` docstring for
    the full reasoning) - both collisions are exercised explicitly here,
    not just the non-colliding common case."""

    def test_baseline_page_marks_only_baseline_active(self, user):
        organisation_id = uuid.uuid4()
        path = reverse("security_baseline:baseline", kwargs={"organisation_id": organisation_id})
        resolver_match = resolve(path)
        request = _request_at_tier(user, TIER_PRO, resolver_match=resolver_match)

        tree = build_navigation_tree(request, organisation_id)
        security = next(item for item in tree if item.code == "security")
        baseline = next(child for child in security.children if child.code == "baseline")

        assert baseline.is_active is True
        assert baseline.has_active_descendant is True
        assert security.is_active is False
        assert security.has_active_descendant is True
        other_children = [child for child in security.children if child.code != "baseline"]
        assert all(child.is_active is False for child in other_children)

    def test_home_foundations_collision_prefers_home(self, user):
        """Both `home` and the WI5-pending `foundations` placeholder point
        at `organisations:detail` today. Visiting that route must mark
        exactly `home` active, not the placeholder."""
        organisation_id = uuid.uuid4()
        path = reverse("organisations:detail", kwargs={"organisation_id": organisation_id})
        resolver_match = resolve(path)
        request = _request_at_tier(user, TIER_PRO, resolver_match=resolver_match)

        tree = build_navigation_tree(request, organisation_id)
        home = next(item for item in tree if item.code == "home")
        foundations = next(item for item in tree if item.code == "foundations")

        assert home.is_active is True
        assert foundations.is_active is False

    def test_security_state_page_prefers_the_child_over_its_own_parent(self, user):
        """`security` (top-level) and `security_state` (its first child)
        both point at `security_state:list`. The more specific child must
        win, not the parent group header."""
        organisation_id = uuid.uuid4()
        path = reverse("security_state:list", kwargs={"organisation_id": organisation_id})
        resolver_match = resolve(path)
        request = _request_at_tier(user, TIER_PRO, resolver_match=resolver_match)

        tree = build_navigation_tree(request, organisation_id)
        security = next(item for item in tree if item.code == "security")
        security_state = next(child for child in security.children if child.code == "security_state")

        assert security_state.is_active is True
        assert security.is_active is False
        assert security.has_active_descendant is True

    def test_unmapped_subpage_marks_nothing_active(self, user):
        """`key_assets:create` (the create form) is not itself any seeded
        `ProductArea.destination_view_name` - only `key_assets:list` is.
        No sidebar item should claim to be "active" on a page that is not
        one of the sidebar's own canonical destinations."""
        organisation_id = uuid.uuid4()
        path = reverse("key_assets:create", kwargs={"organisation_id": organisation_id})
        resolver_match = resolve(path)
        request = _request_at_tier(user, TIER_PRO, resolver_match=resolver_match)

        tree = build_navigation_tree(request, organisation_id)

        def _all_items(items):
            for item in items:
                yield item
                yield from _all_items(item.children)

        assert all(item.is_active is False for item in _all_items(tree))

    def test_no_resolver_match_marks_nothing_active(self, user):
        request = _request_at_tier(user, TIER_PRO, resolver_match=None)
        tree = build_navigation_tree(request, uuid.uuid4())
        assert all(item.is_active is False for item in tree)
