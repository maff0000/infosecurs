import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestUnauthenticatedAccessDenied:
    def test_organisation_list_requires_login(self, client):
        response = client.get(reverse("organisations:list"))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_organisation_create_requires_login(self, client):
        response = client.get(reverse("organisations:create"))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_organisation_detail_requires_login(self, client, org_a):
        response = client.get(reverse("organisations:detail", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_organisation_profile_requires_login(self, client, org_a):
        response = client.get(reverse("organisations:profile", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_organisation_profile_post_requires_login(self, client, org_a):
        response = client.post(
            reverse("organisations:profile", args=[org_a.id]),
            {"legal_trading_name": "Should not be saved"},
        )
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
