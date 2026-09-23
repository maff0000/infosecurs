from django.apps import AppConfig


class RemediationConfig(AppConfig):
    """Remediation Action domain (M003 PID §6.5, §13).

    Owns `RemediationAction` - a deliberately small tenant-owned lifecycle
    object that can optionally reference a `risk_register.Risk`, a
    `security_baseline` catalogue control key, and/or a `key_assets.KeyAsset`.
    This app is a consumer of those apps (reads their models/catalogue for
    reference and linking); it does not modify any of them.

    Explicitly out of scope for this app (M003 PID §6.6, §7, §12): evidence
    items, evidence links, the Current Security State projection, and the
    Activity timeline - those are separate, parallel or later dispatches.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "remediation"
