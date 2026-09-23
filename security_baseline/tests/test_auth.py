import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestUnauthenticatedAccessDenied:
    def test_baseline_get_requires_login(self, client, org_a):
        response = client.get(reverse("security_baseline:baseline", args=[org_a.id]))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_baseline_post_requires_login(self, client, org_a):
        response = client.post(
            reverse("security_baseline:baseline", args=[org_a.id]),
            {"answer__backups": "yes"},
        )
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
