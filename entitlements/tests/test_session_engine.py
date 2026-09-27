"""
PID §6.1/§41 item 13: prove the explicit SESSION_ENGINE setting really is
the database-backed session engine - introspecting the actual resolved
class and a real persisted row, not merely comparing the setting string.
"""
from importlib import import_module

import pytest
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore as DbSessionStore
from django.contrib.sessions.models import Session

pytestmark = pytest.mark.django_db


def test_session_engine_setting_is_explicit_and_correct():
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"


def test_configured_engine_resolves_to_the_real_db_backend_class():
    engine_module = import_module(settings.SESSION_ENGINE)
    assert engine_module.SessionStore is DbSessionStore


def test_a_saved_session_is_genuinely_a_database_row():
    store = DbSessionStore()
    store["proof"] = "db-backed"
    store.save()

    row = Session.objects.get(session_key=store.session_key)
    assert row.get_decoded()["proof"] == "db-backed"


def test_deleting_the_database_row_invalidates_the_session():
    """The property the signed-cookie backend cannot provide (PID §6.1's
    own stated reason for requiring the db backend): server-side deletion
    genuinely invalidates the session, because the data lives in the
    database, not only in a client-held signed blob."""
    store = DbSessionStore()
    store["proof"] = "will-be-deleted"
    store.save()
    key = store.session_key

    Session.objects.get(session_key=key).delete()

    reloaded = DbSessionStore(session_key=key)
    assert reloaded.get("proof") is None
