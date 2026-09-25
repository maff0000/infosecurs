import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from organisations.models import Organisation, OrganisationMembership


@pytest.mark.django_db
def test_no_missing_migrations():
    """
    Fails if the models have drifted from the committed migrations - i.e.
    if a fresh `migrate` would NOT leave the schema matching the models.
    (The test suite itself already proves migrations apply cleanly: every
    test run builds the test database from these migrations against an
    empty Postgres instance - see also the docker-compose clean-bootstrap
    proof in the engineering report.)
    """
    out = io.StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)


@pytest.mark.django_db
def test_create_customer_zero_is_idempotent(monkeypatch):
    """
    M006 PID §16/§I (Round 6): create_customer_zero must be genuinely safe
    to run twice against the same, already-bootstrapped state - the real
    release-artifact/fresh-reproducibility proof runs it once on a fresh
    database, and an operator could plausibly run it again (e.g. after a
    container restart) without meaning to create a duplicate tenant. This
    exercises the real management command (not a hand-rolled equivalent),
    twice, against a real Postgres row set - not just reading the source
    and asserting it "looks" idempotent.
    """
    monkeypatch.setenv("CUSTOMER_ZERO_USERNAME", "test_customerzero")
    monkeypatch.setenv("CUSTOMER_ZERO_EMAIL", "test_customerzero@example.test")
    monkeypatch.setenv("CUSTOMER_ZERO_PASSWORD", "a-synthetic-test-password-12345")
    monkeypatch.setenv("CUSTOMER_ZERO_ORGANISATION_NAME", "Test Customer Zero Org")

    out1 = io.StringIO()
    call_command("create_customer_zero", stdout=out1)

    User = get_user_model()
    assert User.objects.filter(username="test_customerzero").count() == 1
    assert Organisation.objects.filter(name="Test Customer Zero Org").count() == 1
    assert OrganisationMembership.objects.filter(
        organisation__name="Test Customer Zero Org",
        user__username="test_customerzero",
    ).count() == 1

    user_id_after_first_run = User.objects.get(username="test_customerzero").id
    org_id_after_first_run = Organisation.objects.get(name="Test Customer Zero Org").id

    # Run it again against the same already-bootstrapped state.
    out2 = io.StringIO()
    call_command("create_customer_zero", stdout=out2)

    assert User.objects.filter(username="test_customerzero").count() == 1
    assert Organisation.objects.filter(name="Test Customer Zero Org").count() == 1
    assert OrganisationMembership.objects.filter(
        organisation__name="Test Customer Zero Org",
        user__username="test_customerzero",
    ).count() == 1
    # Same underlying rows, not a delete+recreate that happens to net out
    # to the same counts.
    assert User.objects.get(username="test_customerzero").id == user_id_after_first_run
    assert Organisation.objects.get(name="Test Customer Zero Org").id == org_id_after_first_run
    assert "already exists" in out2.getvalue()
