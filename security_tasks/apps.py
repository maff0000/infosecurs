from django.apps import AppConfig


class SecurityTasksConfig(AppConfig):
    """Shared, tenant-isolated security task spine (M010A PID,
    docs/architecture/M010-DATA-WORKFLOW-CONTRACTS.md).

    Owns `SecurityTask`, `SecurityTaskDependency`, `SecurityTaskEvent`, the
    `security_tasks.services` transactional service layer, the Tasks
    sidebar page/detail views, and the allowlisted `source_locator`
    registry (`security_tasks.source_registry`) other apps' records are
    referenced through. Does not modify `questionnaire`, any
    `security_baseline.{catalogue,structured_catalogue,stage4,forms,
    services}` module, or any M009B contract - this app only ever READS
    those apps' models (via the registry), never writes them, and task
    completion never mutates anything outside this app's own tables (see
    `security_tasks/services.py`'s module docstring).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "security_tasks"
