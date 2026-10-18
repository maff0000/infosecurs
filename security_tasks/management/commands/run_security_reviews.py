"""
M010D one-shot deterministic review scheduler dispatch
(docs/pids/M010D-REVIEW-RULES-SCHEDULER.md §3), mirroring
`risk_register.management.commands.run_ai_eval`/`policy.management.
commands.run_policy_ai_eval`/`questionnaire.management.commands.
run_questionnaire_ai_eval`'s established command structure (`Command`
class, `add_arguments`, `handle`, `self.stdout.write`/`CommandError` on a
genuine failure) - except this command makes NO AI/model call at all
(M010-MASTER-ARCHITECTURE.md §6 "no independent LLM scheduler
judgement").

    python manage.py run_security_reviews
    python manage.py run_security_reviews --organisation=<uuid>

Iterates organisations ONE AT A TIME, each in its own isolated
transaction boundary (via `security_tasks.review_scheduler.
run_for_organisation`, which itself processes each candidate in its own
sub-transaction) - a failure evaluating one organisation's rules is
caught and logged, and does NOT prevent the next organisation from being
processed (M010D PID §5 "One tenant failure must not prevent processing
subsequent tenants").

No OS-level cron/scheduler daemon is wired up by this package - per
M010-MASTER-ARCHITECTURE.md §10 this is a later deployment concern. This
command is safe to invoke by hand, by cron, or by any other external
scheduler, any number of times, including concurrently with itself
(security_tasks/tests/test_review_scheduler_concurrency.py proves the
concurrent case; security_tasks/tests/test_run_security_reviews_command.py
proves the repeated-sequential-run case) - every run is idempotent.

Logging discipline (M010D PID §5 "Prevent leakage in metrics, logs,
errors... log only IDs/counters"): every line this command prints names
an organisation ONLY by its UUID, never its name/title, and reports
counts only - never a task title, a source object's content, or any
other organisation's data in the same line as another organisation's.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from organisations.models import Organisation
from security_tasks.review_scheduler import run_for_organisation


class Command(BaseCommand):
    help = (
        "Run the M010D deterministic security review scheduler once, for every "
        "organisation (or one, with --organisation). Safe to invoke repeatedly and "
        "concurrently - every run is idempotent. Makes no AI/model call."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organisation",
            default=None,
            help="Optional organisation UUID. If omitted, every organisation is processed.",
        )

    def handle(self, *args, **options):
        organisation_filter = options.get("organisation")
        if organisation_filter:
            organisations = Organisation.objects.filter(pk=organisation_filter).order_by("pk")
        else:
            organisations = Organisation.objects.order_by("pk")

        organisations_processed = 0
        organisations_failed = 0
        totals = {"created": 0, "unchanged": 0, "superseded_and_recreated": 0, "candidate_errors": 0}

        for organisation in organisations.iterator():
            try:
                result = run_for_organisation(organisation)
            except Exception as exc:  # noqa: BLE001 - one organisation's failure must never stop the rest
                organisations_failed += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"security_tasks.run_security_reviews: organisation {organisation.id} "
                        f"failed ({type(exc).__name__}) - continuing to the next organisation."
                    )
                )
                continue

            organisations_processed += 1
            totals["created"] += result.created
            totals["unchanged"] += result.unchanged
            totals["superseded_and_recreated"] += result.superseded_and_recreated
            totals["candidate_errors"] += result.candidate_errors

            self.stdout.write(
                f"organisation={organisation.id} candidates={result.candidates_evaluated} "
                f"created={result.created} unchanged={result.unchanged} "
                f"superseded_and_recreated={result.superseded_and_recreated} "
                f"reconciliation_conflicts={result.reconciliation_conflicts} "
                f"candidate_errors={result.candidate_errors}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"run_security_reviews complete: organisations_processed={organisations_processed} "
                f"organisations_failed={organisations_failed} created={totals['created']} "
                f"unchanged={totals['unchanged']} "
                f"superseded_and_recreated={totals['superseded_and_recreated']} "
                f"candidate_errors={totals['candidate_errors']}"
            )
        )
