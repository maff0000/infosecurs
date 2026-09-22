import io

import pytest
from django.core.management import call_command


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
