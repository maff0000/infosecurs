import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_is_unauthenticated_and_ok(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_redirects_anonymous_to_login(client):
    response = client.get(reverse("home"))
    assert response.status_code == 302
    assert response.url == reverse("login")
