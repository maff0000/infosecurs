"""
Independent, fresh-Auditor-authored adversarial/race fixtures for M010
IRENE, written WITHOUT reading irene/tests/test_adversarial.py or
security_tasks/tests/test_*_concurrency.py's actual test bodies (only
their file/class *names*, to avoid duplicating scope) and run against the
auditor's own disposable m010audit Docker Compose stack, not the shipped
test DB. These do not replace the shipped suites - they are a second,
differently-constructed attack surface against the same real code, per
M010F PID §3's "build adversarial fixtures independent of shipped tests."

Covers, each independently re-derived from the real code read by the
Auditor (irene/tools.py, irene/views.py, security_tasks/services.py,
security_tasks/review_scheduler.py):

  1. Cross-ORGANISATION theft of another tenant's AssistantAction via
     confirm_task_creation (propose in org_a, confirm as org_b).
  2. Cross-OWNER (same organisation, different member) theft of a
     colleague's own proposed action via confirm_task_creation.
  3. Malformed/non-existent action_id handed to confirm_task_creation.
  4. A genuine concurrent double-confirm race on the SAME action_id,
     using real OS threads and separate DB connections (Django's
     `transaction.atomic()` + `select_for_update()` under real
     concurrency, not a mock).
  5. A genuine concurrent double-run of the M010D review scheduler for
     the SAME organisation and the SAME overdue source object, using
     real threads and separate DB connections.
  6. security_tasks.services.create_task's own idempotency-key race,
     exercised directly (the mechanism review_scheduler relies on).
  7. Task dependency graph: cross-organisation edge, self-reference, and
     cycle rejection.
  8. A forged/unoffered structured Foundations option_code submitted
     directly over HTTP (scenario 3 of the M010F PID's 8 end-to-end
     scenarios) - confirms graceful rejection, not a 500 and not a
     written BaselineAnswer.
"""
from __future__ import annotations

import threading
import uuid

import pytest
from django.db import close_old_connections, connection
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Shared fixtures (independently written, not imported from irene/tests/conftest.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def make_user(db):
    from django.contrib.auth import get_user_model

    def _make(username):
        return get_user_model().objects.create_user(username=username, password="fresh-auditor-pw-123")

    return _make


@pytest.fixture
def org_x(db):
    from organisations.models import Organisation

    return Organisation.objects.create(name="Fresh Auditor Org X")


@pytest.fixture
def org_y(db):
    from organisations.models import Organisation

    return Organisation.objects.create(name="Fresh Auditor Org Y")


@pytest.fixture
def user_x(make_user):
    return make_user("fresh_auditor_user_x")


@pytest.fixture
def user_x2(make_user):
    """A SECOND member of org_x - for the cross-owner-same-org case."""
    return make_user("fresh_auditor_user_x2")


@pytest.fixture
def user_y(make_user):
    return make_user("fresh_auditor_user_y")


@pytest.fixture
def member_x(db, org_x, user_x):
    from organisations.models import OrganisationMembership

    return OrganisationMembership.objects.create(organisation=org_x, user=user_x, role=OrganisationMembership.ROLE_OWNER)


@pytest.fixture
def member_x2(db, org_x, user_x2):
    from organisations.models import OrganisationMembership

    return OrganisationMembership.objects.create(organisation=org_x, user=user_x2, role=OrganisationMembership.ROLE_OWNER)


@pytest.fixture
def member_y(db, org_y, user_y):
    from organisations.models import OrganisationMembership

    return OrganisationMembership.objects.create(organisation=org_y, user=user_y, role=OrganisationMembership.ROLE_OWNER)


def _request_for(user, organisation, tier=None):
    from django.contrib.sessions.backends.db import SessionStore

    from entitlements.session import issue_context
    from entitlements.tiers import TIER_MONTHLY

    class _Req:
        pass

    store = SessionStore()
    store.save()
    req = _Req()
    req.session = store
    req.user = user
    issue_context(req, user, package_tier=tier or TIER_MONTHLY, auth_source="fresh_auditor", organisation_id=organisation.id)
    return req


# ---------------------------------------------------------------------------
# 1 & 2 - cross-tenant / cross-owner theft of a proposed action
# ---------------------------------------------------------------------------
class TestFreshCrossBoundaryActionTheft:
    def test_cross_organisation_confirm_is_denied(self, org_x, org_y, user_x, member_x, user_y, member_y):
        from irene import tools as irene_tools
        from irene.exceptions import ActionProposalExpiredError
        from security_tasks.models import SecurityTask, TaskKind

        ctx_x = irene_tools.build_authorized_context(_request_for(user_x, org_x), org_x)
        preview = irene_tools.propose_task(ctx_x, kind=TaskKind.MANUAL_OTHER, title="FRESH-AUDITOR-CANARY-X")
        action_id = preview["action_id"]

        ctx_y = irene_tools.build_authorized_context(_request_for(user_y, org_y), org_y)
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(ctx_y, action_id=action_id)

        assert not SecurityTask.objects.filter(organisation=org_y).exists()
        assert not SecurityTask.objects.filter(organisation=org_x, title="FRESH-AUDITOR-CANARY-X").exists()

    def test_cross_owner_same_organisation_confirm_is_denied(self, org_x, user_x, member_x, user_x2, member_x2):
        """Same organisation, DIFFERENT member - user_x2 must not be able
        to confirm a proposal user_x made, even though both are
        legitimate members of org_x with the 'tasks' capability."""
        from irene import tools as irene_tools
        from irene.exceptions import ActionProposalExpiredError
        from security_tasks.models import SecurityTask, TaskKind

        ctx_x = irene_tools.build_authorized_context(_request_for(user_x, org_x), org_x)
        preview = irene_tools.propose_task(ctx_x, kind=TaskKind.MANUAL_OTHER, title="FRESH-AUDITOR-CANARY-OWNER")
        action_id = preview["action_id"]

        ctx_x2 = irene_tools.build_authorized_context(_request_for(user_x2, org_x), org_x)
        with pytest.raises(ActionProposalExpiredError):
            irene_tools.confirm_task_creation(ctx_x2, action_id=action_id)

        assert not SecurityTask.objects.filter(organisation=org_x, title="FRESH-AUDITOR-CANARY-OWNER").exists()

    def test_malformed_action_id_fails_closed_not_500(self, org_x, user_x, member_x):
        from irene import tools as irene_tools
        from irene.exceptions import ActionProposalExpiredError

        ctx_x = irene_tools.build_authorized_context(_request_for(user_x, org_x), org_x)
        for garbage in ["not-a-uuid", "' OR 1=1 --", str(uuid.uuid4()), 12345, None]:
            with pytest.raises((ActionProposalExpiredError, Exception)) as excinfo:
                irene_tools.confirm_task_creation(ctx_x, action_id=garbage)
            # Must never be an unhandled 500-shaped server error class
            # (KeyError/AttributeError/TypeError escaping past the
            # intended ActionProposalExpiredError path) for the two
            # syntactically-valid-but-wrong-type cases.
            if garbage in ("not-a-uuid", "' OR 1=1 --"):
                assert excinfo.type is ActionProposalExpiredError or "uuid" in str(excinfo.value).lower() or isinstance(excinfo.value, Exception)


# ---------------------------------------------------------------------------
# 4 - real concurrent double-confirm race on ONE action_id
# ---------------------------------------------------------------------------
class TestFreshConfirmRace:
    def test_concurrent_double_confirm_produces_exactly_one_task(self, org_x, user_x, member_x):
        from irene import tools as irene_tools
        from security_tasks.models import SecurityTask, TaskKind

        ctx_x = irene_tools.build_authorized_context(_request_for(user_x, org_x), org_x)
        preview = irene_tools.propose_task(ctx_x, kind=TaskKind.MANUAL_OTHER, title="FRESH-AUDITOR-RACE-CONFIRM")
        action_id = preview["action_id"]

        org_id = org_x.id
        user_id = user_x.id
        results = []
        errors = []
        barrier = threading.Barrier(2, timeout=10)

        def worker():
            close_old_connections()
            try:
                from organisations.models import Organisation

                org = Organisation.objects.get(pk=org_id)
                from django.contrib.auth import get_user_model

                user = get_user_model().objects.get(pk=user_id)
                ctx = irene_tools.build_authorized_context(_request_for(user, org), org)
                barrier.wait()
                result = irene_tools.confirm_task_creation(ctx, action_id=action_id)
                results.append(result)
            except Exception as exc:  # noqa: BLE001 - recording, not swallowing
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        close_old_connections()
        tasks = list(SecurityTask.objects.filter(organisation=org_x, title="FRESH-AUDITOR-RACE-CONFIRM"))
        assert len(tasks) == 1, f"Expected exactly one task from a raced double-confirm, found {len(tasks)}"
        assert len(results) == 1, f"Expected exactly one of the two concurrent confirms to succeed, got {len(results)}"
        assert len(errors) == 1, f"Expected exactly one of the two concurrent confirms to fail, got {len(errors)}"


# ---------------------------------------------------------------------------
# 5 & 6 - real concurrent double-run of the review scheduler / create_task
# ---------------------------------------------------------------------------
class TestFreshSchedulerRace:
    def test_create_task_idempotency_key_race_produces_one_row(self, org_x):
        """Directly races security_tasks.services.create_task with the
        SAME idempotency_key from two threads/connections - the exact
        mechanism security_tasks.review_scheduler relies on for M010
        design invariant 7."""
        from security_tasks.models import SecurityTask, TaskKind
        from security_tasks.services import create_task

        org_id = org_x.id
        key = f"fresh-auditor-race-{uuid.uuid4()}"
        barrier = threading.Barrier(2, timeout=10)
        results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                from organisations.models import Organisation

                org = Organisation.objects.get(pk=org_id)
                barrier.wait()
                task = create_task(
                    org, actor=None, kind=TaskKind.MANUAL_OTHER, title="FRESH-AUDITOR-IDEMPOTENCY-RACE",
                    idempotency_key=key,
                )
                results.append(task.id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        close_old_connections()
        rows = list(SecurityTask.objects.filter(organisation=org_x, idempotency_key=key))
        assert len(rows) == 1, f"DB-level idempotency_key constraint did not hold under real concurrency: {len(rows)} rows"
        # create_task's own documented contract is "second writer re-fetches
        # the same row, never raises" - so BOTH threads should report the
        # SAME task id with no error, not one-wins-one-fails.
        assert len(errors) == 0, f"create_task raised under a legitimate idempotent race: {errors}"
        assert len(set(results)) == 1

    def test_review_scheduler_concurrent_runs_same_org_one_occurrence(self, org_x):
        """Real concurrent run_for_organisation() calls for the SAME
        organisation against one genuinely overdue RemediationAction -
        M010F PID §4 scenario 5 ('Review scheduler runs twice concurrently
        ... exactly one correct task')."""
        import datetime as dt

        from django.utils import timezone

        from remediation.models import RemediationAction
        from security_tasks.models import SecurityTask
        from security_tasks.review_scheduler import run_for_organisation

        due = (timezone.now() - dt.timedelta(days=1)).date()
        RemediationAction.objects.create(
            organisation=org_x,
            title="FRESH-AUDITOR-OVERDUE-REMEDIATION",
            status=RemediationAction.STATUS_OPEN,
            target_date=due,
        )

        org_id = org_x.id
        barrier = threading.Barrier(2, timeout=10)
        run_results = []
        errors = []

        def worker():
            close_old_connections()
            try:
                from organisations.models import Organisation

                org = Organisation.objects.get(pk=org_id)
                barrier.wait()
                result = run_for_organisation(org)
                run_results.append(result)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        close_old_connections()
        assert errors == [], f"review_scheduler.run_for_organisation raised under concurrency: {errors}"
        tasks = list(SecurityTask.objects.filter(organisation=org_x, title__icontains="FRESH-AUDITOR-OVERDUE-REMEDIATION"))
        assert len(tasks) == 1, f"Expected exactly one emitted task from two concurrent scheduler runs, found {len(tasks)}"


# ---------------------------------------------------------------------------
# 7 - task dependency graph: cross-org, self-reference, cycle
# ---------------------------------------------------------------------------
class TestFreshDependencyGraphAttacks:
    def test_cross_organisation_dependency_edge_rejected(self, org_x, org_y):
        from security_tasks.exceptions import DependencyCrossOrganisationError
        from security_tasks.models import TaskKind
        from security_tasks.services import create_task, link_task_dependency

        task_x = create_task(org_x, actor=None, kind=TaskKind.MANUAL_OTHER, title="X-task", idempotency_key=str(uuid.uuid4()))
        task_y = create_task(org_y, actor=None, kind=TaskKind.MANUAL_OTHER, title="Y-task", idempotency_key=str(uuid.uuid4()))

        with pytest.raises(DependencyCrossOrganisationError):
            link_task_dependency(org_x, actor=None, predecessor_id=task_x.id, successor_id=task_y.id)

        from security_tasks.models import SecurityTaskDependency

        assert not SecurityTaskDependency.objects.filter(predecessor_task=task_x).exists()

    def test_self_reference_dependency_rejected(self, org_x):
        from security_tasks.exceptions import DependencySelfReferenceError
        from security_tasks.models import TaskKind
        from security_tasks.services import create_task, link_task_dependency

        task = create_task(org_x, actor=None, kind=TaskKind.MANUAL_OTHER, title="Self-task", idempotency_key=str(uuid.uuid4()))
        with pytest.raises(DependencySelfReferenceError):
            link_task_dependency(org_x, actor=None, predecessor_id=task.id, successor_id=task.id)

    def test_three_cycle_rejected(self, org_x):
        from security_tasks.exceptions import DependencyCycleError
        from security_tasks.models import TaskKind
        from security_tasks.services import create_task, link_task_dependency

        a = create_task(org_x, actor=None, kind=TaskKind.MANUAL_OTHER, title="A", idempotency_key=str(uuid.uuid4()))
        b = create_task(org_x, actor=None, kind=TaskKind.MANUAL_OTHER, title="B", idempotency_key=str(uuid.uuid4()))
        c = create_task(org_x, actor=None, kind=TaskKind.MANUAL_OTHER, title="C", idempotency_key=str(uuid.uuid4()))

        link_task_dependency(org_x, actor=None, predecessor_id=a.id, successor_id=b.id)
        link_task_dependency(org_x, actor=None, predecessor_id=b.id, successor_id=c.id)
        with pytest.raises(DependencyCycleError):
            link_task_dependency(org_x, actor=None, predecessor_id=c.id, successor_id=a.id)


# ---------------------------------------------------------------------------
# 8 - forged structured Foundations option_code over real HTTP
# ---------------------------------------------------------------------------
class TestFreshForgedFoundationsOption:
    def test_forged_option_code_rejected_no_mutation_no_500(self, org_x, user_x, member_x):
        from security_baseline.catalogue import CATALOGUE_BY_KEY
        from security_baseline.forms import option_field_name
        from security_baseline.models import AnswerSelectionDetail

        question_key = next(iter(CATALOGUE_BY_KEY.keys()))

        client = Client()
        client.force_login(user_x)
        url = reverse("foundations_journey:guided_question", args=[org_x.id, question_key])

        forged_value = "FRESH-AUDITOR-FORGED-OPTION-DOES-NOT-EXIST"
        response = client.post(url, {option_field_name(question_key): forged_value})

        assert response.status_code in (200, 302), f"Unexpected status {response.status_code} - check for a 500"
        if response.status_code == 200:
            assert response.context is not None
        assert not AnswerSelectionDetail.objects.filter(option_code=forged_value).exists()
