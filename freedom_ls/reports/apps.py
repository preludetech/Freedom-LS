from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freedom_ls.reports"
    label = "freedom_ls_reports"
    verbose_name = "Reports"

    def ready(self) -> None:
        from freedom_ls.reports import checks, signals  # noqa: F401
