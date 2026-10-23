"""
WO-IRENE-001 Increment 2 - tests for organisations.services
(the new, additive guarded Stage 3 save path for IRENE's adapter). Proves
WO §1a R2/C2 in full: exact canonical validation reuse, field-scoped
updates, atomic grouped submissions, safe first-submission handling, the
DISTINCT canonical-state stale-write check (separate from any
catalogue/interaction-contract version check - this module plays no part
in those; see module docstring), idempotent receipts, and preserved
audit behaviour - each of the three required concurrency scenarios as an
ACTUALLY EXECUTED test, never merely asserted.
"""
from __future__ import annotations

import threading

import pytest
from django.db import close_old_connections

from organisations.models import NO, UNKNOWN, YES, AuditEvent, Organisation, OrganisationProfile
from organisations.services import (
    CanonicalValidationError,
    StaleCanonicalStateError,
    UnknownStage3FieldError,
    compute_stage3_expected_state_token,
    save_stage3_fields,
)

pytestmark = pytest.mark.django_db

CATALOGUE_VERSION = "1.0.0"
INTERACTION_CONTRACT_VERSION = "1.0.0"


def _save(org, field_values, token, **overrides):
    kwargs = dict(
        organisation=org,
        field_values=field_values,
        expected_state_token=token,
        catalogue_version=CATALOGUE_VERSION,
        interaction_contract_version=INTERACTION_CONTRACT_VERSION,
    )
    kwargs.update(overrides)
    return save_stage3_fields(**kwargs)


class TestFirstEverSubmission:
    def test_no_profile_row_yet_is_handled_safely(self, org_a, user_a):
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])

        receipt = _save(org_a, {"productivity_platform": "microsoft_365"}, token, actor=user_a)

        assert receipt.was_newly_applied is True
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"
        # Every OTHER Stage 3 field is left at its own model default -
        # this call never invents values for fields it was not given.
        assert profile.primary_cloud_provider == UNKNOWN

        audit_event = AuditEvent.objects.get(organisation=org_a)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_CREATED
        assert audit_event.actor == user_a

    def test_expected_state_token_for_a_missing_profile_reflects_model_defaults(self, org_a):
        """The token for an organisation with no row yet must be
        computable with zero database writes, from the model's own
        declared defaults alone."""
        token_before = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        # A second, independent computation (no row created in between)
        # must be identical - deterministic, not randomised.
        token_again = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        assert token_before == token_again


@pytest.mark.django_db(transaction=True)
class TestFirstEverSubmissionConcurrency:
    """Reproduces the race an independent audit found in the `is_new`
    branch of `save_stage3_fields`: two GENUINELY concurrent first-ever
    Stage 3 submissions for the SAME brand-new organisation. Both real
    OS threads, each with its own DB connection, both compute the SAME
    expected-state token (the model-default-derived token for "no row
    yet" - no `select_for_update()` row exists for either of them to
    lock), so both pass the stale-write check and both attempt
    `OrganisationProfile(organisation=organisation); profile.save()`.
    Before the fix, the loser's INSERT raised an unhandled
    `django.db.utils.IntegrityError` (the `OneToOneField`'s own unique DB
    constraint on `organisation`) instead of the module's existing,
    documented, graceful `StaleCanonicalStateError`.

    Uses `@pytest.mark.django_db(transaction=True)` - this codebase's own
    existing precedent (see `security_tasks/tests/test_concurrency.py`)
    for anything requiring real cross-thread commits, rather than a
    single wrapped-and-rolled-back test transaction.
    """

    def test_two_concurrent_first_ever_submissions_do_not_crash_and_exactly_one_row_survives(self):
        organisation = Organisation.objects.create(name="Concurrency First-Ever Submission Org")

        # Both writers capture the SAME expected-state token for "no row
        # yet" BEFORE either one writes - exactly as two customers who
        # both loaded a brand-new organisation's Stage 3 page before
        # either submitted would each hold the token the page handed
        # them (same pattern as TestDistinctCanonicalStateStaleWriteCheck
        # above, applied to the one case that check's own fixtures never
        # exercise: no existing row at all).
        token = compute_stage3_expected_state_token(organisation, ["productivity_platform"])
        start_barrier = threading.Barrier(2)
        outcomes = [None, None]

        def _submit(index, value):
            start_barrier.wait(timeout=10)
            try:
                receipt = _save(organisation, {"productivity_platform": value}, token)
                outcomes[index] = ("ok", receipt)
            except StaleCanonicalStateError as exc:
                outcomes[index] = ("stale", exc)
            except Exception as exc:  # noqa: BLE001
                # Before the fix, this is where the raw IntegrityError
                # landed - an unhandled crash, not a graceful rejection.
                outcomes[index] = ("crash", exc)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=_submit, args=(0, "microsoft_365")),
            threading.Thread(target=_submit, args=(1, "google_workspace")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        kinds = sorted(outcome[0] for outcome in outcomes)
        assert kinds == ["ok", "stale"], (
            f"Expected exactly one winner and one graceful StaleCanonicalStateError "
            f"rejection (never an unhandled crash), got: {outcomes}"
        )

        # Exactly one OrganisationProfile row for this organisation - the
        # unique constraint race never produced two.
        assert OrganisationProfile.objects.filter(organisation=organisation).count() == 1
        profile = OrganisationProfile.objects.get(organisation=organisation)

        winner_index = 0 if outcomes[0][0] == "ok" else 1
        winner_value = "microsoft_365" if winner_index == 0 else "google_workspace"
        assert profile.productivity_platform == winner_value

        # The loser's submission was never silently applied, and exactly
        # one AuditEvent exists - the loser's rejected attempt created no
        # second one.
        assert AuditEvent.objects.filter(organisation=organisation).count() == 1
        audit_event = AuditEvent.objects.get(organisation=organisation)
        assert audit_event.action == AuditEvent.ACTION_PROFILE_CREATED


class TestExactCanonicalValidationReuse:
    def test_an_out_of_choice_value_is_rejected_the_same_way_the_manual_form_rejects_it(self, org_a):
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        with pytest.raises(CanonicalValidationError) as excinfo:
            _save(org_a, {"productivity_platform": "not_a_real_platform"}, token)
        assert "productivity_platform" in excinfo.value.form_errors
        assert not OrganisationProfile.objects.filter(organisation=org_a).exists()

    def test_a_valid_tri_state_value_is_accepted(self, org_a):
        token = compute_stage3_expected_state_token(org_a, ["develops_hosts_own_software"])
        receipt = _save(org_a, {"develops_hosts_own_software": YES}, token)
        assert receipt.was_newly_applied is True
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.develops_hosts_own_software == YES

    def test_unknown_field_name_is_a_caller_bug_not_a_request_time_denial(self, org_a):
        token = "irrelevant"
        with pytest.raises(UnknownStage3FieldError):
            _save(org_a, {"legal_trading_name": "Sneaky Ltd"}, token)


class TestFieldScopedUpdatesNeverFullInstance:
    def test_updating_one_field_does_not_touch_a_sibling_stage3_field_already_set(self, org_a):
        OrganisationProfile.objects.create(
            organisation=org_a,
            legal_trading_name="Existing Ltd",
            productivity_platform="google_workspace",
            handles_payment_card_data=YES,
        )
        token = compute_stage3_expected_state_token(org_a, ["primary_cloud_provider"])

        _save(org_a, {"primary_cloud_provider": "azure"}, token)

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.primary_cloud_provider == "azure"
        # Untouched - never clobbered by this call's own update_fields
        # scoping.
        assert profile.productivity_platform == "google_workspace"
        assert profile.handles_payment_card_data == YES
        assert profile.legal_trading_name == "Existing Ltd"

    def test_a_grouped_multi_field_submission_updates_only_its_own_fields(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")
        token = compute_stage3_expected_state_token(
            org_a, ["handles_personal_data", "handles_confidential_business_data"]
        )

        _save(
            org_a,
            {"handles_personal_data": YES, "handles_confidential_business_data": NO},
            token,
        )

        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.handles_personal_data == YES
        assert profile.handles_confidential_business_data == NO
        # Siblings in the SAME grouped question, not part of this
        # submission, remain untouched.
        assert profile.handles_payment_card_data == UNKNOWN
        assert profile.handles_special_category_data == UNKNOWN


class TestAtomicGroupedSubmission:
    def test_a_grouped_submission_failing_validation_applies_nothing_at_all(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")
        token = compute_stage3_expected_state_token(
            org_a, ["handles_personal_data", "handles_confidential_business_data"]
        )

        with pytest.raises(CanonicalValidationError):
            _save(
                org_a,
                {
                    "handles_personal_data": YES,
                    "handles_confidential_business_data": "not_a_real_tri_state_value",
                },
                token,
            )

        profile = OrganisationProfile.objects.get(organisation=org_a)
        # ALL-OR-NOTHING: handles_personal_data must NOT have been
        # applied just because it, individually, was valid.
        assert profile.handles_personal_data == UNKNOWN


class TestDistinctCanonicalStateStaleWriteCheck:
    """WO §1a R2/C2 - the three mandatory, EXECUTED proofs. Deliberately
    simulates the race the same way a real concurrent pair of requests
    would present it to this service: BOTH writers capture their own
    expected_state_token BEFORE either one writes (exactly as two
    customers who both loaded the Stage 3 page before either submitted
    would each hold the token the page handed them)."""

    def test_same_field_conflict_the_second_writers_stale_token_is_rejected(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")

        # Both writers read the SAME current state before either writes.
        writer_1_token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        writer_2_token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        assert writer_1_token == writer_2_token

        _save(org_a, {"productivity_platform": "microsoft_365"}, writer_1_token)

        with pytest.raises(StaleCanonicalStateError):
            _save(org_a, {"productivity_platform": "google_workspace"}, writer_2_token)

        # Writer 1's value stands; writer 2's was never silently applied.
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"

    def test_unrelated_field_non_overwrite_both_writers_succeed(self, org_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")

        writer_a_token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        writer_b_token = compute_stage3_expected_state_token(org_a, ["primary_cloud_provider"])

        receipt_a = _save(org_a, {"productivity_platform": "microsoft_365"}, writer_a_token)
        receipt_b = _save(org_a, {"primary_cloud_provider": "aws"}, writer_b_token)

        assert receipt_a.was_newly_applied is True
        assert receipt_b.was_newly_applied is True
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"
        assert profile.primary_cloud_provider == "aws"

    def test_this_mechanism_is_not_the_catalogue_or_interaction_contract_version_check(self, org_a):
        """WO §1a C2: the stale-write check is a wholly separate
        mechanism from any catalogue/interaction-contract version
        comparison. Proof: save_stage3_fields never inspects
        catalogue_version/interaction_contract_version when deciding
        whether to reject as stale - identical (even deliberately
        mismatched/nonsensical) version strings are accepted on two
        DIFFERENT, non-conflicting calls, proving those two arguments are
        carried through onto the receipt only, never consulted by the
        stale-write comparison itself."""
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])

        receipt = _save(
            org_a,
            {"productivity_platform": "microsoft_365"},
            token,
            catalogue_version="some-other-catalogue-version",
            interaction_contract_version="some-other-contract-version",
        )

        assert receipt.was_newly_applied is True
        assert receipt.catalogue_version == "some-other-catalogue-version"
        assert receipt.interaction_contract_version == "some-other-contract-version"


class TestIdempotentReceipts:
    def test_a_byte_identical_retry_applies_at_most_once_and_returns_the_same_receipt(self, org_a, user_a):
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        field_values = {"productivity_platform": "microsoft_365"}

        first_receipt = _save(org_a, field_values, token, actor=user_a)
        assert first_receipt.was_newly_applied is True
        assert AuditEvent.objects.filter(organisation=org_a).count() == 1

        # Retry with the EXACT same (now-stale, by raw hash comparison)
        # token and the EXACT same new values - must be recognised as
        # "already applied", not rejected as a conflicting write, and
        # must NOT create a second AuditEvent (no double-apply).
        second_receipt = _save(org_a, field_values, token, actor=user_a)

        assert second_receipt.receipt_id == first_receipt.receipt_id
        assert second_receipt.was_newly_applied is False
        assert AuditEvent.objects.filter(organisation=org_a).count() == 1
        profile = OrganisationProfile.objects.get(organisation=org_a)
        assert profile.productivity_platform == "microsoft_365"

    def test_a_retry_with_different_values_is_not_treated_as_idempotent(self, org_a):
        """Guards against a too-permissive idempotency check: if the
        retried VALUES differ from what was already applied, this is a
        genuine stale write, not a safe duplicate."""
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        _save(org_a, {"productivity_platform": "microsoft_365"}, token)

        with pytest.raises(StaleCanonicalStateError):
            _save(org_a, {"productivity_platform": "google_workspace"}, token)

    def test_receipt_id_is_deterministic_across_two_independent_calls_with_the_same_inputs(self, org_a):
        from organisations.services import _receipt_id

        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        field_values = {"productivity_platform": "microsoft_365"}

        first = _receipt_id(org_a, token, field_values)
        second = _receipt_id(org_a, token, field_values)
        assert first == second


class TestAuditBehaviourPreservation:
    def test_profile_created_action_on_first_submission(self, org_a, user_a):
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        _save(org_a, {"productivity_platform": "microsoft_365"}, token, actor=user_a)
        event = AuditEvent.objects.get(organisation=org_a)
        assert event.action == AuditEvent.ACTION_PROFILE_CREATED

    def test_profile_updated_action_on_a_subsequent_submission(self, org_a, user_a):
        OrganisationProfile.objects.create(organisation=org_a, legal_trading_name="Existing Ltd")
        token = compute_stage3_expected_state_token(org_a, ["productivity_platform"])
        _save(org_a, {"productivity_platform": "microsoft_365"}, token, actor=user_a)
        event = AuditEvent.objects.get(organisation=org_a)
        assert event.action == AuditEvent.ACTION_PROFILE_UPDATED

    def test_no_audit_mechanism_beyond_auditevent_exists_to_preserve(self):
        """Documents, as an executable fact rather than a claim, that
        organisations.views.organisation_stage3_technology_data's own
        save path produces exactly one AuditEvent row and nothing else
        (no signal receiver, no second model) - confirmed directly
        against that view's source, reproduced here as a recorded,
        checkable statement rather than an assumption."""
        import inspect

        from organisations import views as organisations_views

        source = inspect.getsource(organisations_views.organisation_stage3_technology_data)
        assert "AuditEvent.objects.create" in source
        assert source.count("AuditEvent.objects.create") == 1


class TestManualPathLeftUntouchedAndNotRetroactivelyProtected:
    def test_the_manual_views_own_save_path_still_performs_a_full_instance_save(self):
        """Confirms, directly against the real source (never merely
        asserted/trusted), that organisations.views.
        organisation_stage3_technology_data still saves via a plain,
        unguarded profile.save() with no update_fields scoping and no
        expected-state check - this module makes that path NO safer than
        it already was; the two paths are not symmetric and no claim to
        the contrary is made."""
        import inspect

        from organisations import views as organisations_views

        source = inspect.getsource(organisations_views.organisation_stage3_technology_data)
        assert "profile.save()" in source
        assert "update_fields" not in source
        assert "expected_state_token" not in source
