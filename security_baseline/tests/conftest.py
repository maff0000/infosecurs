# Reuse the organisations app's tenant/user fixtures (org_a/org_b, user_a/
# user_b, client_a/client_b, ...) rather than duplicating them -
# security_baseline tests exercise the same two-synthetic-organisation shape
# organisations/tests/conftest.py already establishes. Importing pytest
# fixtures re-exposes them to this directory's tests; this is the supported
# pytest pattern for fixture reuse across app test suites (pytest_plugins
# is restricted to the rootdir conftest).
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
