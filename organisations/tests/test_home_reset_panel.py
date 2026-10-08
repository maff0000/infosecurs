"""
M008E-WI1 (PID §E2/§E9, WO-M008E-WI1) - the Home dashboard's new DEV
Customer Zero reset panel. Proves the same three-gate visibility contract
`organisations/tests/test_reset_views.py` already proves for the reset
VIEW itself, this time for the Home TEMPLATE's own conditional rendering
(`organisations/views.py::_customer_zero_reset_enabled_for`, shared with
`organisation_hub` - see that function's own docstring): visible only
when DJANGO_ENV == "development" AND INFOSECURS_ENABLE_CUSTOMER_ZERO_RESET
is true AND the current organisation is the real `CustomerZeroFixture`;
absent if any one of those three does not hold. This file never re-tests
the reset view's own fail-closed authorization (that stays entirely
`test_reset_views.py`'s job) - it only proves what Home shows or hides.
"""
import pytest
from django.urls import reverse

from entitlements.tests.conftest import set_session_tier
from entitlements.tiers import TIER_FOUNDATION, TIER_PAUSED

pytestmark = pytest.mark.django_db

_DEV_PANEL_TAG = "DEV &middot; Customer Zero"
_DEV_PANEL_BUTTON_TEXT = "Reset test organisation"


class TestHomeResetPanelGating:
    def test_visible_when_all_three_gates_hold(
        self, customer_zero_client, customer_zero_user, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        set_session_tier(customer_zero_client, customer_zero_user, TIER_FOUNDATION)

        content = customer_zero_client.get(
            reverse("organisations:detail", args=[customer_zero_org.id])
        ).content.decode()

        assert _DEV_PANEL_TAG in content
        assert _DEV_PANEL_BUTTON_TEXT in content
        assert reverse("organisations:customer_zero_reset", args=[customer_zero_org.id]) in content

    def test_absent_when_flag_disabled(
        self, customer_zero_client, customer_zero_user, customer_zero_org, settings
    ):
        settings.CUSTOMER_ZERO_RESET_ENABLED = False
        set_session_tier(customer_zero_client, customer_zero_user, TIER_FOUNDATION)

        content = customer_zero_client.get(
            reverse("organisations:detail", args=[customer_zero_org.id])
        ).content.decode()

        assert _DEV_PANEL_TAG not in content
        assert _DEV_PANEL_BUTTON_TEXT not in content

    def test_absent_for_a_non_fixture_organisation(
        self, client_a, user_a, org_a, settings
    ):
        """`org_a` (organisations/tests/conftest.py) is an ordinary
        synthetic test organisation with no `CustomerZeroFixture` row -
        the real-world "any other customer's organisation" case."""
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        set_session_tier(client_a, user_a, TIER_FOUNDATION)

        content = client_a.get(reverse("organisations:detail", args=[org_a.id])).content.decode()

        assert _DEV_PANEL_TAG not in content
        assert _DEV_PANEL_BUTTON_TEXT not in content

    def test_visible_regardless_of_package_tier(
        self, customer_zero_client, customer_zero_user, customer_zero_org, settings
    ):
        """PID §E9: the dev affordance is a development-environment/
        fixture-identity gate, not an entitlement - a Paused session
        (which otherwise gets a deliberately minimal Home, PID §13.1)
        still sees it."""
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        set_session_tier(customer_zero_client, customer_zero_user, TIER_PAUSED)

        response = customer_zero_client.get(
            reverse("organisations:detail", args=[customer_zero_org.id])
        )
        content = response.content.decode()

        assert "Your Infosecurs subscription is currently paused." in content
        assert _DEV_PANEL_TAG in content
        assert _DEV_PANEL_BUTTON_TEXT in content

    def test_link_never_executes_the_reset_directly_only_links_to_confirmation(
        self, customer_zero_client, customer_zero_user, customer_zero_org, settings
    ):
        """The panel's own button is a plain GET link to the existing
        confirmation page, never a <form method="post"> of its own - the
        actual destructive POST only ever happens from that confirmation
        page's own form (organisations/templates/organisations/
        customer_zero_reset_confirm.html), completely untouched by this
        Work Order."""
        settings.CUSTOMER_ZERO_RESET_ENABLED = True
        set_session_tier(customer_zero_client, customer_zero_user, TIER_FOUNDATION)

        content = customer_zero_client.get(
            reverse("organisations:detail", args=[customer_zero_org.id])
        ).content.decode()

        reset_url = reverse("organisations:customer_zero_reset", args=[customer_zero_org.id])
        assert f'href="{reset_url}"' in content
        assert f'action="{reset_url}"' not in content
