import pytest
from django.db import connections
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


@pytest.mark.django_db
def test_healthz_returns_503_with_no_leakage_when_db_unavailable(client):
    """
    PID §13: "unavailable DB -> 503" - the one branch
    `core/tests/test_health.py` never actually proved (the pre-existing
    test above only proves the happy path). This genuinely breaks the real
    `connections["default"]` connection - closing it and repointing its
    settings_dict at an unreachable host/port - so `core.views.healthz`'s
    own `except Exception:` branch executes for real, against a real
    `psycopg`/`django.db.utils.OperationalError`, not a mock standing in
    for one. Also proves the endpoint stays unauthenticated on this branch
    too (no login/session setup here, same as the happy-path test above)
    and that no DB connection detail - host, port, credential, driver
    error text - leaks into the response, even though `core/views.py`'s
    `healthz` doesn't currently construct a response from the exception at
    all (this is a durable regression guard against that changing later,
    not just a check of today's code).
    """
    connection = connections["default"]
    original_settings = connection.settings_dict.copy()
    connection.close()
    unreachable_host = "prodconfig-health-deliberately-unreachable.invalid"
    connection.settings_dict["HOST"] = unreachable_host
    connection.settings_dict["PORT"] = 1
    try:
        response = client.get(reverse("healthz"))
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "database": False}

        raw = response.content
        sensitive_values = [
            unreachable_host.encode(),
            str(original_settings["HOST"]).encode(),
            str(original_settings["PORT"]).encode(),
            str(original_settings["NAME"]).encode(),
            str(original_settings["USER"]).encode(),
            str(original_settings["PASSWORD"]).encode(),
            b"OperationalError",
            b"psycopg",
            b"Traceback",
        ]
        for value in sensitive_values:
            if not value:
                continue
            assert value not in raw, f"sensitive DB detail leaked into /healthz/ response: {value!r}"
    finally:
        # Restore the real connection settings and drop the broken
        # connection object so Django transparently reconnects on next use
        # (including pytest-django's own end-of-test transaction rollback).
        connection.settings_dict.clear()
        connection.settings_dict.update(original_settings)
        connection.close()
