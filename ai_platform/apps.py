from django.apps import AppConfig


class AiPlatformConfig(AppConfig):
    """AI adapter infrastructure layer (M002 PID §9-§17).

    This app owns the provider-neutral gateway boundary, the structured
    generation contracts, the invocation record, and the bounded
    execution/retry orchestration. It deliberately does NOT own the Risk
    domain (no Risk model, no confirm/dismiss UI, no risk register) - that
    is a later, separate module built on top of this adapter.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_platform"
