"""
Django system checks - the "boot-time" half of M010C PID §2/§3's "Validate
every registered route/tool at boot/test" and "Boot with concise rules +
registry/version + skill manifest". `irene.apps.IreneConfig.ready()` wires
this module in; see that module's own docstring for why a system check
rather than a direct call from `ready()`.

Both checks run automatically on `manage.py check`, `manage.py runserver`
(any deploy/CI pipeline that calls `check` before serving), and
`manage.py test`/pytest-django (which calls Django's check framework as
part of test-runner setup) - so a broken registry or a broken skill
manifest fails the WHOLE application's checks, not merely one test file
that happens to import the validator directly. `irene/tests/
test_product_knowledge.py` and `irene/tests/test_skill_loader.py` ALSO
call the validators directly (belt and braces - a test file that
exercises the validator's exact error messages/behaviour, independent of
whether `manage.py check` happens to be wired into a given CI step).
"""
from __future__ import annotations

from django.core.checks import Error, register


@register()
def check_product_knowledge_map(app_configs, **kwargs):
    from irene.product_knowledge import ProductKnowledgeMapValidationError, validate_product_knowledge_map

    try:
        validate_product_knowledge_map()
    except ProductKnowledgeMapValidationError as exc:
        return [
            Error(
                f"irene Product Knowledge Map failed validation: {exc}",
                id="irene.E001",
            )
        ]
    return []


@register()
def check_skill_manifests(app_configs, **kwargs):
    from irene.skill_loader import SkillManifestValidationError, validate_all_skills

    try:
        validate_all_skills()
    except SkillManifestValidationError as exc:
        return [
            Error(
                f"irene skill manifest(s) failed validation: {exc}",
                id="irene.E002",
            )
        ]
    return []
