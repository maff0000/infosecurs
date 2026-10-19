from django.apps import AppConfig


class FoundationsJourneyConfig(AppConfig):
    """M010B - the Foundations guided journey adapter
    (docs/pids/M010B-FOUNDATIONS-GUIDED-JOURNEY.md, docs/architecture/
    M010-DATA-WORKFLOW-CONTRACTS.md).

    A thin, validated server-side adapter over the existing, unmodified
    `security_baseline.{catalogue,structured_catalogue,stage4,forms,
    services,views}` and `entitlements.metrics` contracts - this app owns
    exactly two new models (`JourneyCheckpoint`, `UserJourneyPreference`)
    and never introduces a second Foundations question/answer/completion
    source of truth. Every canonical write this app performs goes through
    `security_baseline.services.record_structured_baseline_answer`, the
    exact same function the pre-existing manual
    `security_baseline.views.foundations_question` view already calls -
    see `foundations_journey/services.py`'s module docstring for the full
    reasoning.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "foundations_journey"
    verbose_name = "Foundations guided journey"
