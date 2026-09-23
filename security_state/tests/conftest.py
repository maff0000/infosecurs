# Reuse the organisations app's tenant/user fixtures (org_a/org_b, user_a/
# user_b, client_a/client_b, ...) rather than duplicating them - same
# pattern security_baseline/tests/conftest.py already uses. Importing
# pytest fixtures re-exposes them to this directory's tests.
from organisations.tests.conftest import (  # noqa: F401
    client_a,
    client_b,
    make_user,
    member_a,
    member_b,
    org_a,
    org_b,
    user_a,
    user_b,
)
