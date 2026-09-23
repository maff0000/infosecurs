from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """
    Project-specific glue around django-allauth's Google/Microsoft OAuth2
    providers (ADR-0002 §2, M004-POLICY-FOUNDATION §5).

    This app owns:
      - identity.adapters.CustomSocialAccountAdapter (SOCIALACCOUNT_ADAPTER);
      - the deterministic fake-provider test/acceptance seam
        (identity/testing.py);
      - identity's own tests.

    It deliberately does not touch organisations/, config/settings.py or
    config/urls.py directly - see this app's tests and the FORGE dispatch
    report for the settings/urls blocks the PL wires in centrally.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "identity"
    verbose_name = "Identity (federated sign-in)"
