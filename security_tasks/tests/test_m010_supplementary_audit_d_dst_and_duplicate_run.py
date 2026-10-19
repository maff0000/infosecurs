"""
M010 Supplementary Audit D (2026-10-19), Scope D sub-cases 3a/3b:

    3a. "One review-scheduler DST boundary case: pick a UK clock-change
        date ... and run the scheduler across that boundary for a
        review-due calculation, confirming no fabricated/off-by-one date
        and the correct task results."

    3b. "One duplicate-run case: run `python manage.py
        run_security_reviews` TWICE in a row for the same organisation/
        window, confirming exactly one task results (not two) and no
        fabricated date."

Independent fixture written by this supplementary audit - deliberately
NOT a rerun of `security_tasks/tests/test_review_rules.py`'s own
spring-forward/autumn-back unit tests of the bare `due_at_from_local_date`
function. This test instead drives the REAL, shipped
`run_security_reviews` management command end to end against a real
`PolicyVersion` row, and inspects the real `SecurityTask` row the real
command produced - corroborating the full integration (ORM round-trip +
command + scheduler + task service), not just the pure date-arithmetic
function the existing unit tests already cover.

2026 UK autumn clock-change date independently confirmed (not assumed)
via `date -d "2026-10-18" +%A` / `date -d "2026-10-25" +%A`: both 18 and
25 October 2026 are Sundays; 25 October is the LAST Sunday of that month,
so that is the real 2026 transition date (clocks go back 02:00 BST ->
01:00 GMT).
"""
import datetime as dt

import pytest
from django.core.management import call_command
from django.utils import timezone as django_timezone

from policy.models import PolicyDocument, PolicyVersion
from security_tasks.models import SecurityTask, SourceOrigin, TaskKind
from security_tasks.review_rules import due_at_from_local_date

pytestmark = pytest.mark.django_db

UK_AUTUMN_2026_CLOCK_CHANGE_DATE = dt.date(2026, 10, 25)


def test_due_at_conversion_either_side_of_the_2026_autumn_transition():
    """Own, independently-reasoned corroboration of the pure conversion
    (not copied from the shipped unit test's own fixture values) -
    verified by first principles: BST is UTC+1, so local midnight on a
    BST date is 23:00 UTC the PREVIOUS calendar day; GMT is UTC+0, so
    local midnight on a GMT date is 00:00 UTC that same day. The
    transition instant itself (02:00 BST / 01:00 UTC) is after midnight,
    so midnight local on the transition day itself is still BST."""
    before = due_at_from_local_date(dt.date(2026, 10, 24))  # fully BST
    on_day = due_at_from_local_date(UK_AUTUMN_2026_CLOCK_CHANGE_DATE)  # still BST at midnight
    after = due_at_from_local_date(dt.date(2026, 10, 26))  # fully GMT

    assert before == dt.datetime(2026, 10, 23, 23, 0, 0, tzinfo=dt.timezone.utc)
    assert on_day == dt.datetime(2026, 10, 24, 23, 0, 0, tzinfo=dt.timezone.utc)
    assert after == dt.datetime(2026, 10, 26, 0, 0, 0, tzinfo=dt.timezone.utc)
    # `after` and `on_day` are two calendar days apart (Oct 26 vs Oct 24)
    # but only 25 real elapsed hours apart in UTC, not 48 or 24 - exactly
    # one calendar day (24h) plus the one hour the clocks fell back,
    # never an off-by-one in either direction.
    assert (after - on_day) == dt.timedelta(hours=25)


def test_run_security_reviews_dst_boundary_and_duplicate_run(org_a):
    document, _ = PolicyDocument.objects.get_or_create(organisation=org_a)
    version = PolicyVersion.objects.create(
        document=document,
        organisation=org_a,
        version_number=1,
        status=PolicyVersion.STATUS_APPROVED,
        title="M010 Supplementary Audit D - DST boundary fixture policy",
        next_review_date=UK_AUTUMN_2026_CLOCK_CHANGE_DATE,
        approved_at=django_timezone.now(),
    )

    expected_due_at = dt.datetime(2026, 10, 24, 23, 0, 0, tzinfo=dt.timezone.utc)

    # --- 3a: first real run of the shipped command, across the boundary ---
    call_command("run_security_reviews", organisation=str(org_a.id))

    tasks = list(
        SecurityTask.objects.filter(
            organisation=org_a,
            source_origin=SourceOrigin.RULES_ENGINE,
            task_kind=TaskKind.POLICY_REVIEW,
        )
    )
    assert len(tasks) == 1, "Exactly one task must be created for one candidate."
    task = tasks[0]
    assert task.due_at == expected_due_at, (
        "Task due_at must be the exact DST-correct UTC instant for midnight "
        "Europe/London on the 2026 clock-change day - no off-by-one, no "
        f"fabrication. Got {task.due_at!r}, expected {expected_due_at!r}."
    )
    assert task.occurrence_key == f"policy_review:{version.id}:2026-10-25"
    assert task.idempotency_key == f"rules_engine:policy_review:{version.id}:2026-10-25"

    first_task_id = task.id
    first_created_at = task.created_at

    # --- 3b: second run, immediately after, same organisation/window ---
    call_command("run_security_reviews", organisation=str(org_a.id))

    tasks_after = list(
        SecurityTask.objects.filter(
            organisation=org_a,
            source_origin=SourceOrigin.RULES_ENGINE,
            task_kind=TaskKind.POLICY_REVIEW,
        )
    )
    assert len(tasks_after) == 1, "A second run for the same organisation/window must not create a duplicate task."
    assert tasks_after[0].id == first_task_id, "The second run must reconcile onto the SAME task row, not a new one."
    assert tasks_after[0].created_at == first_created_at, "The existing task must not be re-created/touched."
    assert tasks_after[0].due_at == expected_due_at, "No fabricated/off-by-one date on the repeated run either."

    # --- Third run, for extra assurance - still exactly one task ---
    call_command("run_security_reviews", organisation=str(org_a.id))
    final_count = SecurityTask.objects.filter(
        organisation=org_a,
        source_origin=SourceOrigin.RULES_ENGINE,
        task_kind=TaskKind.POLICY_REVIEW,
    ).count()
    assert final_count == 1
