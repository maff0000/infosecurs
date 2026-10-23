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

        # WO-IRENE-001 Increment 2 (§3.2/§3.6): imports the real Stage 3
        # adapter so its own module-level `register_section(...)` call
        # (irene.question_engine.adapters.stage3_technology_data) always
        # runs before any real request can reach
        # `irene.question_engine.registry.SECTION_REGISTRY` - the exact
        # same "a system-check/ready()-time import guarantees this runs
        # at boot" precedent this method already establishes for
        # `irene.checks` directly above, not a new convention. Plain
        # import (no deferred `reverse()` call of its own at import
        # time), so - unlike `irene.checks` - it needs no system-check
        # indirection; importing it here, rather than relying on some
        # other module importing it incidentally, is what makes
        # registration genuinely boot-time rather than accidental.
        from irene.question_engine.adapters import stage3_technology_data  # noqa: F401
