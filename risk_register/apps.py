from django.apps import AppConfig


class RiskRegisterConfig(AppConfig):
    """Risk domain + generation orchestration + review UI (M002 PID §8, §14-§21).

    This app is the consumer of the already-integrated `security_baseline`,
    `key_assets` and `ai_platform` apps - it owns the `Risk` model, the
    tenant-scoped `GroundingPayload` construction that ties M001 + Security
    Baseline + Key Assets together for AI generation, and the confirm/edit/
    dismiss review UI. It does not modify anything in those apps.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "risk_register"
