from django.apps import AppConfig


class AuditLogAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.audit_log"
    label = "freedom_ls_audit_log"
    verbose_name = "Audit log"

    def ready(self) -> None:
        from freedom_ls.audit_log import checks  # noqa: F401
