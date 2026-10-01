"""
M008A-WI1a: proves the `CustomerZeroFixture` marker is created exclusively
by `create_customer_zero`, and never by any user-facing write path.
"""
import io

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from organisations.models import CustomerZeroFixture, Organisation


@pytest.mark.django_db
def test_bootstrap_creates_exactly_one_fixture_row_for_the_new_organisation(monkeypatch):
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", "wi1a_customerzero")
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", "wi1a_customerzero@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "WI1a Customer Zero Org")

    call_command("create_customer_zero", stdout=io.StringIO())

    organisation = Organisation.objects.get(name="WI1a Customer Zero Org")
    assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1


@pytest.mark.django_db
def test_rerunning_bootstrap_does_not_duplicate_the_fixture_row(monkeypatch):
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", "wi1a_customerzero2")
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", "wi1a_customerzero2@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "WI1a Customer Zero Org 2")

    call_command("create_customer_zero", stdout=io.StringIO())
    call_command("create_customer_zero", stdout=io.StringIO())  # rerun, same state

    organisation = Organisation.objects.get(name="WI1a Customer Zero Org 2")
    assert CustomerZeroFixture.objects.filter(organisation=organisation).count() == 1


@pytest.mark.django_db
def test_an_ordinary_organisation_never_gets_a_fixture_row(client_a):
    """
    `organisations:create` (`OrganisationCreateForm` -> `organisation_create`
    view) is the one user-facing, authenticated write path that creates
    Organisation rows. It must never be the thing that makes "is this the
    trusted fixture" true for an attacker- or test-created organisation of
    the same display name as the real Customer Zero org.
    """
    response = client_a.post(reverse("organisations:create"), {"name": "New Synthetic Co"})
    assert response.status_code == 302

    organisation = Organisation.objects.get(name="New Synthetic Co")
    # `CustomerZeroFixture` has its own auto pk (a separate id space from
    # `Organisation`'s UUID pk, since it is not declared as the FK's
    # primary key) - the meaningful check is "no fixture row references
    # this organisation", i.e. filtering by the `organisation` FK, not by
    # `CustomerZeroFixture`'s own pk.
    assert not CustomerZeroFixture.objects.filter(organisation=organisation).exists()


@pytest.mark.django_db
def test_an_ordinary_organisation_with_the_same_name_is_still_not_the_fixture(monkeypatch):
    """
    Defeats a display-name-only identification: an attacker/test creating
    a second Organisation row that happens to share the real Customer
    Zero organisation's name must not thereby acquire a fixture row of
    its own - only the organisation `create_customer_zero` itself
    touches gets one.
    """
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", "wi1a_customerzero3")
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", "wi1a_customerzero3@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "WI1a Shared Name Org")

    call_command("create_customer_zero", stdout=io.StringIO())
    real_fixture_org = Organisation.objects.get(name="WI1a Shared Name Org")

    # A second, ordinary organisation created with the SAME display name
    # via the normal create path - get_or_create inside the command would
    # never do this itself, but a view/form has no such protection.
    impostor = Organisation.objects.create(name="WI1a Shared Name Org")

    assert CustomerZeroFixture.objects.filter(organisation=real_fixture_org).exists()
    assert not CustomerZeroFixture.objects.filter(organisation=impostor).exists()
