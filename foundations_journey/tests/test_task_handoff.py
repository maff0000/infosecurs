import uuid

import pytest
from django.urls import reverse

from foundations_journey import services
from foundations_journey.exceptions import NoFollowUpTaskAvailableError
from security_tasks.models import SecurityTask, TaskKind
from security_tasks.source_registry import SOURCE_KIND_BASELINE_ANSWER


@pytest.mark.django_db
class TestFollowUpTaskOfferedForUnknownAndPartialAndNo:
    def test_unknown_answer_offers_a_foundation_confirm_task(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="mfa_user_accounts", option_code="MFA_USER_NOT_SURE"
        )
        task = services.offer_foundations_followup_task(
            org_a, user_a, question_key="mfa_user_accounts", idempotency_key=str(uuid.uuid4())
        )
        assert task.task_kind == TaskKind.FOUNDATION_CONFIRM
        assert task.source_kind == SOURCE_KIND_BASELINE_ANSWER
        assert task.organisation_id == org_a.id

    def test_partial_answer_offers_a_foundation_remediate_task(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_RESTORE_UNTESTED"
        )
        task = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        assert task.task_kind == TaskKind.FOUNDATION_REMEDIATE

    def test_no_answer_offers_a_foundation_remediate_task(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        task = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        assert task.task_kind == TaskKind.FOUNDATION_REMEDIATE

    def test_yes_answer_offers_no_task(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_TESTED"
        )
        with pytest.raises(NoFollowUpTaskAvailableError):
            services.offer_foundations_followup_task(
                org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
            )

    def test_not_applicable_answer_offers_no_task(self, org_a, user_a, member_a):
        from organisations.models import OrganisationProfile

        OrganisationProfile.objects.create(
            organisation=org_a, legal_trading_name="X", people_with_system_access_count=1
        )
        services.submit_foundations_option(
            org_a, user_a, question_key="joiner_mover_leaver", option_code="JML_NOT_APPLICABLE",
            confirmation=True,
        )
        with pytest.raises(NoFollowUpTaskAvailableError):
            services.offer_foundations_followup_task(
                org_a, user_a, question_key="joiner_mover_leaver", idempotency_key=str(uuid.uuid4())
            )

    def test_unanswered_control_offers_no_task(self, org_a, user_a, member_a):
        with pytest.raises(NoFollowUpTaskAvailableError):
            services.offer_foundations_followup_task(
                org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
            )


@pytest.mark.django_db
class TestFollowUpTaskCreationIsExplicitAndDeduplicated:
    def test_merely_viewing_the_question_creates_no_task(self, client_a, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        client_a.get(reverse("foundations_journey:guided_question", args=[org_a.id, "backups"]))
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0

    def test_repeated_offer_with_same_underlying_answer_deduplicates(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        task_1 = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        task_2 = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        assert task_1.pk == task_2.pk
        assert SecurityTask.objects.filter(organisation=org_a).count() == 1

    def test_changing_the_answer_after_a_task_was_offered_allows_a_new_distinct_task(
        self, org_a, user_a, member_a
    ):
        """A new occurrence_key (because the answer/option genuinely
        changed) is a DIFFERENT real-world fact - a second task is
        correct here, not a duplicate of the first."""
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        task_1 = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_RESTORE_UNTESTED"
        )
        task_2 = services.offer_foundations_followup_task(
            org_a, user_a, question_key="backups", idempotency_key=str(uuid.uuid4())
        )
        assert task_1.pk != task_2.pk
        assert SecurityTask.objects.filter(organisation=org_a).count() == 2

    def test_offered_task_records_canonical_question_key_and_status(self, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="mfa_user_accounts", option_code="MFA_USER_NOT_SURE"
        )
        task = services.offer_foundations_followup_task(
            org_a, user_a, question_key="mfa_user_accounts", idempotency_key=str(uuid.uuid4())
        )
        assert "mfa_user_accounts" in task.summary
        assert "unknown" in task.summary
        assert "MFA_USER_NOT_SURE" in task.summary


@pytest.mark.django_db
class TestOfferFollowUpTaskViewRequiresPost:
    def test_get_redirects_without_creating_a_task(self, client_a, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        response = client_a.get(
            reverse("foundations_journey:offer_followup_task", args=[org_a.id, "backups"])
        )
        assert response.status_code == 302
        assert SecurityTask.objects.filter(organisation=org_a).count() == 0

    def test_post_creates_a_task_visible_on_the_tasks_page(self, client_a, org_a, user_a, member_a):
        services.submit_foundations_option(
            org_a, user_a, question_key="backups", option_code="BACKUPS_NONE"
        )
        idempotency_key = str(uuid.uuid4())
        response = client_a.post(
            reverse("foundations_journey:offer_followup_task", args=[org_a.id, "backups"]),
            {"idempotency_key": idempotency_key},
        )
        assert response.status_code == 302
        assert SecurityTask.objects.filter(organisation=org_a, task_kind=TaskKind.FOUNDATION_REMEDIATE).exists()

        tasks_page = client_a.get(reverse("security_tasks:list", args=[org_a.id]))
        assert tasks_page.status_code == 200
        assert "Remediate" in tasks_page.content.decode()
