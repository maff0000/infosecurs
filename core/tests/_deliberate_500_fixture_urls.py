"""
Test-only urlconf, used exclusively by `core/tests/test_error_pages.py`'s
deliberate-500 test (M006 PID §10). It exists only to be swapped in via
`override_settings(ROOT_URLCONF=...)` for that one test - it is never
reachable from the product's real urlconf (`config.urls`), and the view it
defines raises on purpose. Not picked up by pytest's own test collection
(`pytest.ini`'s `python_files` only matches `tests.py`/`test_*.py`/
`*_tests.py`, none of which this filename matches).
"""
from django.urls import path


def deliberately_broken_view(request):
    raise RuntimeError(
        "deliberate test-only failure - exercises the customer-facing 500 "
        "page (M006 PID §10), never reachable in the real product urlconf"
    )


urlpatterns = [
    path("__test-only-deliberate-500__/", deliberately_broken_view, name="test_only_deliberate_500"),
]
