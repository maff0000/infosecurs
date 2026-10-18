from django.apps import AppConfig


class IreneConfig(AppConfig):
    """M010C (docs/pids/M010C-IRENE-MODAL-SKILLS-TOOLS.md): IRENE's own
    conversation/action models, Product Knowledge Map registry, bounded
    tool registry and Git-reviewed skill filesystem.

    `ready()` registers the boot-time registry/manifest validators as a
    Django system check (`irene.checks`) rather than calling them directly
    here: `django.urls.reverse()` (used by the Product Knowledge Map
    validator to prove every registered route name actually resolves)
    needs the URL resolver fully loaded, which is not guaranteed yet at
    `AppConfig.ready()` time (every app's `ready()` runs before Django
    finishes loading `ROOT_URLCONF`), whereas Django's checks framework
    runs AFTER the full app registry and URL configuration are ready -
    this is also what makes the validator run automatically on
    `manage.py check`/`runserver`/`manage.py test` (pytest-django's own
    runner invokes the same checks), i.e. genuinely "boot-time", without
    the fragility of calling `reverse()` from inside `ready()` itself."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "irene"
    verbose_name = "IRENE"

    def ready(self):
        from irene import checks  # noqa: F401  (registers via @register below)
