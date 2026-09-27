"""
PID §6.4/§25.2/§25.3: fail-closed validation, and that issuing a context
genuinely rotates the session key. Uses a real `django.contrib.sessions`
`SessionStore` (the db backend) rather than a mock, so "the session key
literally changes" and "the data is genuinely persisted" are proven against
real session machinery, not an assumption about it.
"""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore

from entitlements import session as session_module
from entitlements.tiers import (
    CODE_FOUNDATION,
    CODE_MONTHLY,
    CODE_PRO,
    TIER_FOUNDATION,
    TIER_MONTHLY,
    TIER_PRO,
)

pytestmark = pytest.mark.django_db


class FakeRequest:
    """A minimal stand-in exposing exactly the two attributes
    `entitlements.session` touches (`request.session`, `request.user`) -
    everything else about a real Django request is irrelevant to this
    service layer, which is the point of testing it in isolation."""

    def __init__(self, session, user):
        self.session = session
        self.user = user


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username="alice", password="not-a-real-password-123")


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(username="bob", password="not-a-real-password-123")


def valid_raw_context(user, *, tier=TIER_MONTHLY, code=CODE_MONTHLY, organisation_id="fixture-org", schema_version=None):
    return {
        "schema_version": session_module.SCHEMA_VERSION if schema_version is None else schema_version,
        "subject_id": str(user.pk),
        "organisation_id": organisation_id,
        "package_tier": tier,
        "package_code": code,
        "entitlement_version": session_module.ENTITLEMENT_VERSION,
        "issued_at": "2026-09-27T00:00:00+00:00",
        "auth_source": "test_fixture",
    }


class TestValidContextRoundTrips:
    def test_valid_context_returns_typed_context(self, user):
        raw = valid_raw_context(user)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.InfosecursContext)
        assert result.subject_id == str(user.pk)
        assert result.package_tier == TIER_MONTHLY
        assert result.package_code == CODE_MONTHLY
        assert result.organisation_id == "fixture-org"

    def test_valid_context_with_no_active_organisation(self, user):
        raw = valid_raw_context(user, organisation_id=None)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.InfosecursContext)
        assert result.organisation_id is None


class TestEachFailClosedCheckIsIndependent:
    """Every one of these must return Invalid - never a default-permissive
    tier, and never anything other than the `Invalid` deny signal."""

    def test_missing_context(self, user):
        result = session_module.validate_context(None, user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.MISSING

    def test_not_a_mapping(self, user):
        result = session_module.validate_context(["not", "a", "dict"], user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.NOT_A_MAPPING

    def test_missing_field(self, user):
        raw = valid_raw_context(user)
        del raw["package_tier"]
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.MISSING_FIELD

    def test_unsupported_schema_version(self, user):
        raw = valid_raw_context(user, schema_version=999)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.UNKNOWN_SCHEMA_VERSION

    def test_unauthenticated_user(self, user):
        raw = valid_raw_context(user)
        result = session_module.validate_context(raw, user=AnonymousUser())
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.UNAUTHENTICATED

    def test_subject_mismatch(self, user, other_user):
        raw = valid_raw_context(user)
        result = session_module.validate_context(raw, user=other_user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.SUBJECT_MISMATCH

    @pytest.mark.parametrize("bad_tier", [-1, 4, 100, True, False, "2", None, 2.0])
    def test_tier_out_of_range(self, user, bad_tier):
        raw = valid_raw_context(user)
        raw["package_tier"] = bad_tier
        # A bad tier may also fail the code/tier check first depending on
        # value, but it must never validate.
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)

    def test_code_tier_mismatch(self, user):
        raw = valid_raw_context(user, tier=TIER_FOUNDATION, code=CODE_PRO)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.CODE_TIER_MISMATCH

    def test_code_wrong_type(self, user):
        raw = valid_raw_context(user)
        raw["package_code"] = 2
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)

    @pytest.mark.parametrize("bad_org", ["", "   ", 12345, []])
    def test_organisation_id_malformed(self, user, bad_org):
        raw = valid_raw_context(user, organisation_id=bad_org)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.ORGANISATION_ID_MALFORMED

    def test_malformed_context_is_never_silently_pro(self, user):
        """The single most important invariant of this module: whatever
        goes wrong, the result is always an explicit deny, never any tier
        at all - and specifically never the most-privileged tier."""
        malformed_variants = [
            None,
            {},
            valid_raw_context(user, tier=99, code="NOT_A_CODE"),
            {**valid_raw_context(user), "subject_id": "someone-else"},
        ]
        for raw in malformed_variants:
            result = session_module.validate_context(raw, user=user)
            assert isinstance(result, session_module.Invalid)
            assert not isinstance(result, session_module.InfosecursContext)


class TestIssueContext:
    def test_issue_context_builds_the_documented_schema(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)

        context = session_module.issue_context(
            request, user, package_tier=TIER_PRO, auth_source="test_fixture"
        )

        assert context["schema_version"] == session_module.SCHEMA_VERSION
        assert context["subject_id"] == str(user.pk)
        assert context["organisation_id"] is None
        assert context["package_tier"] == TIER_PRO
        assert context["package_code"] == CODE_PRO
        assert context["entitlement_version"] == session_module.ENTITLEMENT_VERSION
        assert context["auth_source"] == "test_fixture"
        assert "issued_at" in context

    def test_issue_context_stores_under_the_canonical_session_key(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)

        session_module.issue_context(request, user, package_tier=TIER_MONTHLY, auth_source="x")

        assert store[session_module.SESSION_KEY]["package_code"] == CODE_MONTHLY

    def test_issue_context_rotates_the_session_key(self, user):
        store = SessionStore()
        store["marker"] = "pre-issue"
        store.save()
        old_key = store.session_key
        assert old_key is not None

        request = FakeRequest(store, user)
        session_module.issue_context(request, user, package_tier=TIER_FOUNDATION, auth_source="x")

        new_key = store.session_key
        assert new_key is not None
        assert new_key != old_key

    def test_old_session_key_is_gone_after_rotation(self, user):
        from django.contrib.sessions.models import Session

        store = SessionStore()
        store.save()
        old_key = store.session_key

        request = FakeRequest(store, user)
        session_module.issue_context(request, user, package_tier=TIER_PRO, auth_source="x")
        store.save()

        assert not Session.objects.filter(session_key=old_key).exists()
        assert Session.objects.filter(session_key=store.session_key).exists()

    def test_issued_context_is_genuinely_persisted_and_re_readable(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)

        session_module.issue_context(request, user, package_tier=TIER_MONTHLY, auth_source="x")
        store.save()

        reloaded = SessionStore(session_key=store.session_key)
        raw = reloaded.get(session_module.SESSION_KEY)
        result = session_module.validate_context(raw, user=user)
        assert isinstance(result, session_module.InfosecursContext)
        assert result.package_tier == TIER_MONTHLY

    def test_issue_context_rejects_a_deliberately_inconsistent_code_tier_pair(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)

        with pytest.raises(ValueError):
            session_module.issue_context(
                request, user, package_tier=TIER_FOUNDATION, package_code=CODE_PRO, auth_source="x"
            )


class TestGetValidatedContext:
    def test_reads_and_validates_in_one_step(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)
        session_module.issue_context(request, user, package_tier=TIER_PRO, auth_source="x")

        result = session_module.get_validated_context(request)
        assert isinstance(result, session_module.InfosecursContext)
        assert result.package_tier == TIER_PRO

    def test_missing_session_key_is_invalid_not_an_exception(self, user):
        store = SessionStore()
        store.save()
        request = FakeRequest(store, user)

        result = session_module.get_validated_context(request)
        assert isinstance(result, session_module.Invalid)
        assert result.reason == session_module.InvalidReason.MISSING
